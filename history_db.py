"""Database persistence for scan history and cleaned items."""
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
import os
from typing import List, Dict, Any

log = logging.getLogger(__name__)

DB_DIR = Path(os.getenv('LOCALAPPDATA')) / 'PCCleaner'
DB_FILE = DB_DIR / 'history.db'


class HistoryDatabase:
    """SQLite database for storing scan and clean history."""

    def __init__(self):
        self.db_file = DB_FILE
        self._init_db()

    def _init_db(self):
        """Initialize database tables if not exists."""
        try:
            DB_DIR.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            # Scan history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    scan_type TEXT,
                    duration_seconds REAL,
                    items_found INTEGER,
                    total_size_bytes INTEGER,
                    status TEXT
                )
            ''')

            # Cleaned items table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cleaned_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    category TEXT,
                    item_path TEXT,
                    size_bytes INTEGER,
                    status TEXT,
                    FOREIGN KEY (scan_id) REFERENCES scans(id)
                )
            ''')

            # Vault restore history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vault_restores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    item_path TEXT,
                    file_size_bytes INTEGER,
                    restore_location TEXT,
                    status TEXT
                )
            ''')

            # Operation errors log
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS error_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    operation TEXT,
                    error_message TEXT,
                    error_traceback TEXT,
                    severity TEXT
                )
            ''')

            conn.commit()
            conn.close()
            log.info(f"History database initialized at {self.db_file}")
        except Exception as e:
            log.error(f"Failed to initialize database: {e}")

    def record_scan(
        self,
        scan_type: str,
        duration_seconds: float,
        items_found: int,
        total_size_bytes: int,
        status: str = 'completed'
    ) -> int:
        """Record a scan operation. Returns scan_id."""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO scans (scan_type, duration_seconds, items_found, total_size_bytes, status) '
                'VALUES (?, ?, ?, ?, ?)',
                (scan_type, duration_seconds, items_found, total_size_bytes, status)
            )
            scan_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return scan_id
        except Exception as e:
            log.error(f"Failed to record scan: {e}")
            return -1

    def record_cleaned_item(
        self,
        scan_id: int,
        category: str,
        item_path: str,
        size_bytes: int,
        status: str = 'cleaned'
    ):
        """Record a cleaned item."""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO cleaned_items (scan_id, category, item_path, size_bytes, status) '
                'VALUES (?, ?, ?, ?, ?)',
                (scan_id, category, item_path, size_bytes, status)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            log.error(f"Failed to record cleaned item: {e}")

    def record_vault_restore(
        self,
        item_path: str,
        file_size_bytes: int,
        restore_location: str,
        status: str = 'restored'
    ):
        """Record a vault restore operation."""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO vault_restores (item_path, file_size_bytes, restore_location, status) '
                'VALUES (?, ?, ?, ?)',
                (item_path, file_size_bytes, restore_location, status)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            log.error(f"Failed to record vault restore: {e}")

    def record_error(
        self,
        operation: str,
        error_message: str,
        error_traceback: str = '',
        severity: str = 'error'
    ):
        """Record an error for debugging."""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO error_log (operation, error_message, error_traceback, severity) '
                'VALUES (?, ?, ?, ?)',
                (operation, error_message, error_traceback, severity)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            log.error(f"Failed to record error: {e}")

    def get_recent_scans(self, limit=50) -> List[Dict[str, Any]]:
        """Get recent scan history."""
        try:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM scans ORDER BY timestamp DESC LIMIT ?',
                (limit,)
            )
            rows = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            log.error(f"Failed to get scan history: {e}")
            return []

    def get_cleaned_items_by_scan(self, scan_id: int) -> List[Dict[str, Any]]:
        """Get cleaned items for a specific scan."""
        try:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM cleaned_items WHERE scan_id = ? ORDER BY timestamp DESC',
                (scan_id,)
            )
            rows = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            log.error(f"Failed to get cleaned items: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics."""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM scans')
            total_scans = cursor.fetchone()[0]

            cursor.execute('SELECT SUM(total_size_bytes) FROM scans WHERE status = "completed"')
            total_cleaned = cursor.fetchone()[0] or 0

            cursor.execute('SELECT COUNT(*) FROM error_log')
            total_errors = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM vault_restores WHERE status = "restored"')
            total_restores = cursor.fetchone()[0]

            conn.close()

            return {
                'total_scans': total_scans,
                'total_cleaned_bytes': total_cleaned,
                'total_errors': total_errors,
                'total_vault_restores': total_restores,
            }
        except Exception as e:
            log.error(f"Failed to get stats: {e}")
            return {}

    def clear_old_history(self, days=30):
        """Clear history older than specified days."""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute(
                'DELETE FROM cleaned_items WHERE scan_id IN '
                '(SELECT id FROM scans WHERE datetime(timestamp) < datetime("now", "-" || ? || " days"))',
                (days,)
            )
            cursor.execute(
                'DELETE FROM scans WHERE datetime(timestamp) < datetime("now", "-" || ? || " days")',
                (days,)
            )
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            log.info(f"Deleted {deleted} old history entries")
            return deleted
        except Exception as e:
            log.error(f"Failed to clear history: {e}")
            return 0


# Global instance
history_db = HistoryDatabase()
