"""Advanced features: benchmarking, cost analysis, keyboard shortcuts."""
import concurrent.futures
import logging
import time
from typing import Dict, Optional, Tuple, List
import psutil

log = logging.getLogger(__name__)


class PerformanceBenchmark:
    """Benchmark PC performance before/after cleaning."""

    def __init__(self):
        self.baseline = None
        self.current = None

    def capture_baseline(self) -> Dict[str, float]:
        """Capture baseline performance metrics."""
        try:
            self.baseline = {
                'timestamp': time.time(),
                'cpu_percent': psutil.cpu_percent(interval=1),
                'ram_used': psutil.virtual_memory().used,
                'ram_percent': psutil.virtual_memory().percent,
                'disk_io_read': psutil.disk_io_counters().read_bytes,
                'disk_io_write': psutil.disk_io_counters().write_bytes,
            }
            log.info("Baseline performance captured")
            return self.baseline
        except Exception as e:
            log.error(f"Failed to capture baseline: {e}")
            return {}

    def capture_current(self) -> Dict[str, float]:
        """Capture current performance metrics."""
        try:
            self.current = {
                'timestamp': time.time(),
                'cpu_percent': psutil.cpu_percent(interval=1),
                'ram_used': psutil.virtual_memory().used,
                'ram_percent': psutil.virtual_memory().percent,
                'disk_io_read': psutil.disk_io_counters().read_bytes,
                'disk_io_write': psutil.disk_io_counters().write_bytes,
            }
            log.info("Current performance captured")
            return self.current
        except Exception as e:
            log.error(f"Failed to capture current metrics: {e}")
            return {}

    def get_improvement(self) -> Dict[str, Dict[str, float]]:
        """Calculate performance improvements."""
        if not self.baseline or not self.current:
            return {}

        try:
            ram_freed = self.baseline['ram_used'] - self.current['ram_used']
            ram_percent_improvement = self.baseline['ram_percent'] - self.current['ram_percent']

            disk_io_read_improvement = self.current['disk_io_read'] - self.baseline['disk_io_read']
            disk_io_write_improvement = self.current['disk_io_write'] - self.baseline['disk_io_write']

            return {
                'ram': {
                    'freed_bytes': max(0, ram_freed),
                    'percent_improvement': max(0, ram_percent_improvement),
                },
                'cpu': {
                    'baseline_percent': self.baseline['cpu_percent'],
                    'current_percent': self.current['cpu_percent'],
                    'improvement_percent': max(0, self.baseline['cpu_percent'] - self.current['cpu_percent']),
                },
                'disk_io': {
                    'read_bytes_since': disk_io_read_improvement,
                    'write_bytes_since': disk_io_write_improvement,
                },
                'duration_seconds': self.current['timestamp'] - self.baseline['timestamp'],
            }
        except Exception as e:
            log.error(f"Failed to calculate improvements: {e}")
            return {}


class CostAnalysis:
    """Analyze monetary value of freed disk space."""

    # Typical disk costs per TB (adjust for different markets)
    DISK_COSTS = {
        'thailand': 400,  # Baht per TB (approximate HDD cost)
        'us': 50,  # USD per TB
        'eu': 45,  # EUR per TB
    }

    # Typical disk cost per GB in different regions (baht)
    COST_PER_GB_THB = 0.4  # ฿0.40 per GB

    @staticmethod
    def calculate_saved_cost(freed_bytes: int, region: str = 'thailand') -> Dict[str, float]:
        """Calculate monetary value of freed space."""
        try:
            freed_gb = freed_bytes / (1024 ** 3)
            freed_tb = freed_gb / 1024

            if region == 'thailand':
                # Cost based on typical HDD prices in Thailand
                cost_thb = freed_gb * CostAnalysis.COST_PER_GB_THB
                return {
                    'currency': 'THB',
                    'symbol': '฿',
                    'freed_gb': freed_gb,
                    'cost': round(cost_thb, 2),
                    'per_gb': CostAnalysis.COST_PER_GB_THB,
                }
            elif region == 'us':
                cost_usd = freed_tb * CostAnalysis.DISK_COSTS['us']
                return {
                    'currency': 'USD',
                    'symbol': '$',
                    'freed_gb': freed_gb,
                    'cost': round(cost_usd, 2),
                    'per_tb': CostAnalysis.DISK_COSTS['us'],
                }
            else:
                # Generic calculation
                cost_per_gb = 0.05  # USD per GB
                return {
                    'currency': 'USD',
                    'symbol': '$',
                    'freed_gb': freed_gb,
                    'cost': round(freed_gb * cost_per_gb, 2),
                }
        except Exception as e:
            log.error(f"Failed to calculate cost: {e}")
            return {}


class KeyboardShortcuts:
    """Manage keyboard shortcuts."""

    SHORTCUTS = {
        'scan': ('ctrl', 's'),
        'clean': ('ctrl', 'shift', 'c'),
        'settings': ('ctrl', ','),
        'open': ('ctrl', 'o'),
        'exit': ('alt', 'f4'),
        'help': ('f1'),
        'undo': ('ctrl', 'z'),
        'refresh': ('f5'),
    }

    SHORT_DESCRIPTIONS = {
        'scan': 'Start scanning',
        'clean': 'Start cleaning',
        'settings': 'Open settings',
        'open': 'Open file',
        'exit': 'Close application',
        'help': 'Show help',
        'undo': 'Undo last action',
        'refresh': 'Refresh data',
    }

    @staticmethod
    def get_shortcut(action: str) -> Optional[Tuple[str, ...]]:
        """Get keyboard shortcut for action."""
        return KeyboardShortcuts.SHORTCUTS.get(action)

    @staticmethod
    def get_all_shortcuts() -> Dict[str, Dict[str, any]]:
        """Get all shortcuts with descriptions."""
        return {
            action: {
                'keys': KeyboardShortcuts.SHORTCUTS[action],
                'description': KeyboardShortcuts.SHORT_DESCRIPTIONS.get(action, ''),
            }
            for action in KeyboardShortcuts.SHORTCUTS
        }

    @staticmethod
    def format_shortcut(shortcut: Tuple[str, ...]) -> str:
        """Format shortcut for display."""
        if isinstance(shortcut, tuple):
            # Windows style: Ctrl+S, Ctrl+Shift+C
            return '+'.join(key.capitalize() for key in shortcut)
        return str(shortcut)

    @staticmethod
    def get_help_text() -> str:
        """Get formatted help text for all shortcuts."""
        lines = ["PC Cleaner Keyboard Shortcuts:\n"]
        for action, shortcut in KeyboardShortcuts.SHORTCUTS.items():
            desc = KeyboardShortcuts.SHORT_DESCRIPTIONS.get(action, '')
            formatted = KeyboardShortcuts.format_shortcut(shortcut)
            lines.append(f"  {formatted:20} — {desc}")
        return "\n".join(lines)


class DuplicateFinderAdvanced:
    """Advanced duplicate file finder with filters."""

    def __init__(self):
        self.duplicates = {}

    def find_by_hash(self, folder: str, extensions: Optional[List[str]] = None) -> Dict:
        """Find duplicates by content hash."""
        import os
        import hashlib
        from pathlib import Path

        try:
            hash_map = {}
            duplicates = {}

            # Group by size first: a file with a unique size can't have a
            # duplicate, so it never needs to be read. This skips most I/O.
            by_size = {}
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if extensions and not any(file.lower().endswith(ext) for ext in extensions):
                        continue
                    filepath = os.path.join(root, file)
                    try:
                        size = os.path.getsize(filepath)
                    except OSError:
                        continue
                    if size > 0:
                        by_size.setdefault(size, []).append((filepath, file))

            candidates = [(p, n, s) for s, grp in by_size.items() if len(grp) > 1 for p, n in grp]
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                hashes = list(ex.map(lambda c: self._hash_file(c[0]), candidates))
            for (filepath, file, size), file_hash in zip(candidates, hashes):
                if file_hash:
                    hash_map.setdefault(file_hash, []).append(
                        {'path': filepath, 'size': size, 'name': file})

            # Find duplicates (hash with >1 file)
            for file_hash, files in hash_map.items():
                if len(files) > 1:
                    duplicates[file_hash] = files

            self.duplicates = duplicates
            log.info(f"Found {len(duplicates)} duplicate groups")
            return {
                'total_groups': len(duplicates),
                'total_files': sum(len(files) for files in duplicates.values()),
                'duplicates': duplicates,
            }
        except Exception as e:
            log.error(f"Failed to find duplicates: {e}")
            return {}

    def find_by_name(self, folder: str) -> Dict:
        """Find duplicates by filename."""
        import os
        from pathlib import Path

        try:
            name_map = {}
            duplicates = {}

            for root, dirs, files in os.walk(folder):
                for file in files:
                    if file not in name_map:
                        name_map[file] = []
                    name_map[file].append({
                        'path': os.path.join(root, file),
                        'size': os.path.getsize(os.path.join(root, file)),
                    })

            # Find duplicates
            for filename, locations in name_map.items():
                if len(locations) > 1:
                    duplicates[filename] = locations

            log.info(f"Found {len(duplicates)} files with duplicate names")
            return {
                'total_duplicate_names': len(duplicates),
                'total_duplicate_locations': sum(len(locs) for locs in duplicates.values()),
                'duplicates': duplicates,
            }
        except Exception as e:
            log.error(f"Failed to find duplicates by name: {e}")
            return {}

    @staticmethod
    def _hash_file(filepath: str, block_size: int = 65536) -> Optional[str]:
        """Calculate SHA256 hash of file."""
        try:
            import hashlib
            hasher = hashlib.sha256()
            with open(filepath, 'rb') as f:
                while True:
                    data = f.read(block_size)
                    if not data:
                        break
                    hasher.update(data)
            return hasher.hexdigest()
        except Exception as e:
            log.debug(f"Failed to hash file: {e}")
            return None


# Global instances
benchmark = PerformanceBenchmark()
cost_analysis = CostAnalysis()
keyboard_shortcuts = KeyboardShortcuts()
duplicate_finder = DuplicateFinderAdvanced()

__all__ = [
    'PerformanceBenchmark',
    'CostAnalysis',
    'KeyboardShortcuts',
    'DuplicateFinderAdvanced',
    'benchmark',
    'cost_analysis',
    'keyboard_shortcuts',
    'duplicate_finder',
]
