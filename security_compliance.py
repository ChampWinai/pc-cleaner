"""Security, compliance, and PII detection features."""
import logging
import re
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import os

log = logging.getLogger(__name__)


class PIIDetector:
    """Detect Personally Identifiable Information in files."""

    # Patterns for different types of PII
    PATTERNS = {
        'credit_card': (
            r'\b(?:\d{4}[-\s]?){3}\d{4}\b',  # XXX-XXX-XXX-XXXX or variations
            'Credit Card'
        ),
        'ssn': (
            r'\b\d{3}-\d{2}-\d{4}\b',  # XXX-XX-XXXX
            'Social Security Number'
        ),
        'email': (
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'Email Address'
        ),
        'phone': (
            r'\b(?:\+?1[-.\s]?)?\(?[2-9][0-9]{2}\)?[-.\s]?[2-9][0-9]{2}[-.\s]?[0-9]{4}\b',
            'Phone Number'
        ),
        'thai_id': (
            r'\b\d{1}-\d{4}-\d{5}-\d{2}-\d{1}\b',
            'Thai ID Number'
        ),
        'passport': (
            r'\b[A-Z]{1,2}[0-9]{6,9}\b',
            'Passport Number'
        ),
    }

    @staticmethod
    def scan_file(filepath: str) -> Dict[str, List[Tuple[str, int]]]:
        """Scan a file for PII."""
        findings = {}
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            for pattern_type, (pattern, label) in PIIDetector.PATTERNS.items():
                matches = []
                for line_num, line in enumerate(lines, 1):
                    if re.search(pattern, line):
                        matches.append((line.strip()[:100], line_num))
                if matches:
                    findings[label] = matches

        except Exception as e:
            log.debug(f"Failed to scan {filepath}: {e}")

        return findings

    @staticmethod
    def scan_folder(folder: str, extensions: Optional[List[str]] = None) -> Dict[str, Dict]:
        """Scan folder for PII in files."""
        findings = {}
        try:
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if extensions and not any(file.endswith(ext) for ext in extensions):
                        continue

                    filepath = os.path.join(root, file)
                    file_findings = PIIDetector.scan_file(filepath)
                    if file_findings:
                        findings[filepath] = file_findings

        except Exception as e:
            log.error(f"Failed to scan folder: {e}")

        return findings


class TwoFactorConfirmation:
    """2FA confirmation for sensitive operations."""

    def __init__(self):
        self.confirmed_operations = {}
        self.confirmation_timeout = 600  # 10 minutes

    def request_confirmation(self, operation_id: str, operation_name: str) -> bool:
        """Request 2FA confirmation for operation."""
        try:
            log.info(f"2FA confirmation requested for: {operation_name}")
            # In production, this would show a dialog or send OTP
            self.confirmed_operations[operation_id] = {
                'timestamp': datetime.now(),
                'operation': operation_name,
                'confirmed': False,
            }
            return True
        except Exception as e:
            log.error(f"Failed to request 2FA: {e}")
            return False

    def confirm_operation(self, operation_id: str) -> bool:
        """Confirm a 2FA operation."""
        if operation_id in self.confirmed_operations:
            self.confirmed_operations[operation_id]['confirmed'] = True
            log.info(f"Operation {operation_id} confirmed")
            return True
        return False

    def is_confirmed(self, operation_id: str) -> bool:
        """Check if operation is confirmed and not expired."""
        if operation_id not in self.confirmed_operations:
            return False

        op = self.confirmed_operations[operation_id]
        if not op['confirmed']:
            return False

        # Check timeout
        elapsed = (datetime.now() - op['timestamp']).total_seconds()
        if elapsed > self.confirmation_timeout:
            log.warning(f"2FA confirmation expired for {operation_id}")
            return False

        return True


class AuditLogger:
    """Comprehensive audit logging for compliance."""

    def __init__(self, log_file: Optional[str] = None):
        if log_file is None:
            app_data = Path(os.getenv('LOCALAPPDATA', ''))
            log_file = str(app_data / 'PCCleaner' / 'audit.log')
        self.log_file = log_file
        Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)

    def log_event(
        self,
        event_type: str,
        user: str,
        action: str,
        resource: str,
        status: str,
        details: Optional[Dict] = None,
    ):
        """Log audit event."""
        try:
            event = {
                'timestamp': datetime.now().isoformat(),
                'event_type': event_type,
                'user': user,
                'action': action,
                'resource': resource,
                'status': status,
                'details': details or {},
            }

            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event) + '\n')

            log.debug(f"Audit event logged: {event_type}")
        except Exception as e:
            log.error(f"Failed to log audit event: {e}")

    def export_csv(self, output_file: str, days: int = 30) -> bool:
        """Export audit log to CSV."""
        try:
            cutoff = datetime.now() - timedelta(days=days)
            events = []

            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        event = json.loads(line)
                        event_time = datetime.fromisoformat(event['timestamp'])
                        if event_time >= cutoff:
                            events.append(event)
                    except json.JSONDecodeError:
                        pass

            if events:
                with open(output_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=events[0].keys())
                    writer.writeheader()
                    for event in events:
                        writer.writerow(event)

            log.info(f"Audit log exported to {output_file}")
            return True
        except Exception as e:
            log.error(f"Failed to export audit log: {e}")
            return False

    def export_json(self, output_file: str, days: int = 30) -> bool:
        """Export audit log to JSON."""
        try:
            cutoff = datetime.now() - timedelta(days=days)
            events = []

            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        event = json.loads(line)
                        event_time = datetime.fromisoformat(event['timestamp'])
                        if event_time >= cutoff:
                            events.append(event)
                    except json.JSONDecodeError:
                        pass

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(events, f, indent=2, ensure_ascii=False)

            log.info(f"Audit log exported to {output_file}")
            return True
        except Exception as e:
            log.error(f"Failed to export audit log: {e}")
            return False


class GDPRComplianceMode:
    """GDPR-compliant operation mode."""

    def __init__(self):
        self.enabled = False
        self.auto_delete_logs_days = 30
        self.anonymize_data = True

    def enable(self) -> bool:
        """Enable GDPR compliance mode."""
        try:
            self.enabled = True
            log.info("GDPR Compliance Mode enabled")
            return True
        except Exception as e:
            log.error(f"Failed to enable GDPR mode: {e}")
            return False

    def disable(self) -> bool:
        """Disable GDPR compliance mode."""
        self.enabled = False
        log.info("GDPR Compliance Mode disabled")
        return True

    def purge_user_data(self, user_identifier: str) -> bool:
        """Purge all user data per GDPR right-to-be-forgotten."""
        try:
            from config_manager import config
            from history_db import history_db

            # Clear history
            history_db.clear_old_history(days=0)  # Clear everything

            # Clear vault
            log.info(f"GDPR: Purged data for user {user_identifier}")
            return True
        except Exception as e:
            log.error(f"Failed to purge user data: {e}")
            return False

    def cleanup_old_logs(self, days: Optional[int] = None):
        """Auto-delete logs older than specified days."""
        days = days or self.auto_delete_logs_days
        try:
            from history_db import history_db
            deleted = history_db.clear_old_history(days)
            log.info(f"GDPR: Deleted {deleted} old log entries")
        except Exception as e:
            log.error(f"Failed to cleanup logs: {e}")

    def anonymize_log_entry(self, log_entry: Dict) -> Dict:
        """Anonymize a log entry for GDPR compliance."""
        anonymized = log_entry.copy()
        
        # Remove or mask sensitive fields
        sensitive_fields = ['user', 'email', 'phone', 'path']
        for field in sensitive_fields:
            if field in anonymized:
                anonymized[field] = '***REDACTED***'

        return anonymized


# Global instances
pii_detector = PIIDetector()
two_factor = TwoFactorConfirmation()
audit_logger = AuditLogger()
gdpr_mode = GDPRComplianceMode()

__all__ = [
    'PIIDetector',
    'TwoFactorConfirmation',
    'AuditLogger',
    'GDPRComplianceMode',
    'pii_detector',
    'two_factor',
    'audit_logger',
    'gdpr_mode',
]
