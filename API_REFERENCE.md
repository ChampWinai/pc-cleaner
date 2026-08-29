# PC Cleaner API Reference

Complete documentation of PC Cleaner backend functions and modules.

## Core Backend (backend.py)

### Scanning Functions

#### `get_targets(deep=False) -> List[Tuple[str, str]]`
Get list of cleanup target folders and their paths.

**Parameters:**
- `deep` (bool): If True, include dev tool caches and Windows system caches (slower, more thorough)

**Returns:** List of (label, path) tuples

**Example:**
```python
from backend import get_targets
targets = get_targets(deep=False)  # Basic targets
targets_deep = get_targets(deep=True)  # All targets
```

---

#### `scan_temp(whitelist=None) -> Dict`
Scan temporary files in system and user temp folders.

**Parameters:**
- `whitelist` (List[str]): Folder paths to exclude from scan

**Returns:** Dictionary with:
- `items`: List of file paths found
- `total_size`: Total size in bytes
- `count`: Number of items

**Example:**
```python
result = scan_temp(whitelist=[r'C:\Important\Folder'])
print(f"Found {result['count']} temp files, {result['total_size']} bytes")
```

---

#### `scan_drivers() -> Dict`
Scan for outdated drivers using Windows API.

**Returns:** Dictionary with driver info including:
- `outdated_drivers`: List of (device_name, current_version, latest_version)
- `count`: Number of outdated drivers

**Example:**
```python
result = scan_drivers()
for device, current, latest in result['outdated_drivers']:
    print(f"{device}: {current} -> {latest}")
```

---

#### `scan_registry_temp() -> Dict`
Scan Windows Registry for leftover entries from uninstalled programs.

**Returns:** List of registry paths to clean

**Example:**
```python
result = scan_registry_temp()
print(f"Found {len(result)} orphaned registry entries")
```

---

### Cleaning Functions

#### `clean_items(selected: List[str]) -> Dict`
Delete selected files/folders after confirmation.

**Parameters:**
- `selected`: List of file/folder paths to delete

**Returns:** Dictionary with:
- `succeeded`: List of successfully deleted paths
- `failed`: List of (path, error_message) tuples
- `total_freed`: Total bytes freed

**Example:**
```python
items_to_clean = [r'C:\Windows\Temp\file1.tmp', r'C:\Temp\cache\']
result = clean_items(items_to_clean)
print(f"Freed {result['total_freed']} bytes")
```

---

#### `clean_registry_temp(entries: List[str]) -> Dict`
Delete selected registry entries (admin required).

**Parameters:**
- `entries`: List of registry paths to delete

**Returns:** Dictionary with success/failure info

**Example:**
```python
entries = [r'HKEY_LOCAL_MACHINE\Software\...\old_entry']
result = clean_registry_temp(entries)
```

---

### Vault Functions

#### `vault_ls() -> List[Dict]`
List all files in the vault (recycle bin).

**Returns:** List of file entries with metadata

**Example:**
```python
vault_files = vault_ls()
for f in vault_files:
    print(f"{f['name']} - {f['size_bytes']} bytes - {f['deleted_at']}")
```

---

#### `vault_restore(file_id: str, restore_location: str = None) -> bool`
Restore a file from vault.

**Parameters:**
- `file_id`: ID of file in vault
- `restore_location`: Optional custom location (defaults to original location)

**Returns:** True if successful

**Example:**
```python
success = vault_restore('file_uuid_here', restore_location=r'C:\Restored\')
```

---

### Utility Functions

#### `human_size(num_bytes: int) -> str`
Convert bytes to human-readable format.

**Example:**
```python
print(human_size(1536))  # "1.5 KB"
print(human_size(5368709120))  # "5.0 GB"
```

---

#### `validate_thai_id(id_str: str) -> bool`
Validate Thai ID number using Luhn checksum.

**Example:**
```python
if validate_thai_id('1234567890123'):
    print("Valid Thai ID")
```

---

## Configuration Management (config_manager.py)

### `ConfigManager` Class

Configuration is persisted to `%LOCALAPPDATA%/PCCleaner/settings.json`.

#### `get(key: str, default=None) -> Any`
Get config value using dot notation.

**Example:**
```python
from config_manager import config
auto_clean = config.get('cleaning.auto_clean_enabled', False)
dark_mode = config.get('ui.dark_mode', False)
```

---

#### `set(key: str, value: Any) -> bool`
Set config value.

**Example:**
```python
config.set('ui.dark_mode', True)
config.set('cleaning.auto_clean_hour', 3)
```

---

#### `get_whitelist_folders() -> List[str]`
Get list of folders excluded from cleaning.

**Example:**
```python
whitelist = config.get_whitelist_folders()
for folder in whitelist:
    print(f"Whitelisted: {folder}")
```

---

#### `add_whitelist_folder(folder: str) -> bool`
Add folder to whitelist.

**Example:**
```python
config.add_whitelist_folder(r'C:\MyImportantFiles')
```

---

## Update Checking (update_checker.py)

### `UpdateChecker` Class

#### `check_and_notify(interval_days=7) -> Dict | None`
Check for updates if interval has passed.

**Example:**
```python
from update_checker import UpdateChecker
update_info = UpdateChecker.check_and_notify(interval_days=7)
if update_info:
    print(f"New version available: {update_info['version']}")
    print(f"Download: {update_info['download_url']}")
```

---

#### `is_newer_available() -> bool`
Quick check if newer version exists.

**Example:**
```python
if UpdateChecker.is_newer_available():
    print("Please update PC Cleaner!")
```

---

## Auto-Clean Scheduling (task_scheduler.py)

### `TaskSchedulerManager` Class

#### `create_task(hour=2, minute=0, frequency='daily') -> bool`
Create Windows Task Scheduler task for auto-clean.

**Example:**
```python
from task_scheduler import TaskSchedulerManager
# Schedule auto-clean daily at 2:30 AM
success = TaskSchedulerManager.create_task(hour=2, minute=30, frequency='daily')
```

---

#### `delete_task() -> bool`
Remove auto-clean task.

**Example:**
```python
TaskSchedulerManager.delete_task()
```

---

#### `task_exists() -> bool`
Check if task is scheduled.

**Example:**
```python
if TaskSchedulerManager.task_exists():
    print("Auto-clean is scheduled")
```

---

## History & Analytics (history_db.py)

### `HistoryDatabase` Class

Persistent SQLite database at `%LOCALAPPDATA%/PCCleaner/history.db`.

#### `record_scan(scan_type: str, duration_seconds: float, items_found: int, total_size_bytes: int) -> int`
Record a scan operation.

**Returns:** Scan ID for later reference

**Example:**
```python
from history_db import history_db
scan_id = history_db.record_scan(
    scan_type='temp_files',
    duration_seconds=15.5,
    items_found=234,
    total_size_bytes=1073741824  # 1 GB
)
```

---

#### `record_cleaned_item(scan_id: int, category: str, item_path: str, size_bytes: int)`
Record an item that was cleaned.

**Example:**
```python
history_db.record_cleaned_item(
    scan_id=1,
    category='temp_files',
    item_path=r'C:\Windows\Temp\file.tmp',
    size_bytes=1024
)
```

---

#### `get_stats() -> Dict`
Get aggregate statistics.

**Returns:**
```python
{
    'total_scans': 42,
    'total_cleaned_bytes': 10737418240,  # 10 GB
    'total_errors': 2,
    'total_vault_restores': 5,
}
```

---

#### `get_recent_scans(limit=50) -> List[Dict]`
Get recent scan history.

**Example:**
```python
recent = history_db.get_recent_scans(limit=10)
for scan in recent:
    print(f"{scan['timestamp']}: {scan['scan_type']}")
```

---

## Operation Context & Retry Logic (operation_context.py)

### Cancellable Operations

#### `OperationContext` Class

Thread-safe way to monitor and cancel long-running operations.

**Example:**
```python
from operation_context import OperationContext

context = OperationContext('my_scan_123')

# In worker thread, periodically check:
while processing:
    context.check_cancelled()  # Raises OperationCancelled if cancelled
    
# From UI thread, cancel operation:
context.cancel()
```

---

#### `@retry` Decorator

Automatic retry with exponential backoff.

**Example:**
```python
from operation_context import retry, RetryConfig

config = RetryConfig(max_attempts=3, initial_delay=1)

@retry(config)
def fetch_drivers():
    # Will retry up to 3 times on exception
    return requests.get('https://example.com/drivers').json()
```

---

## Plugin System (plugin_system.py)

### Creating a Plugin

Create file at `%USERPROFILE%/.pccleaner/plugins/my-plugin/plugin.py`:

```python
from plugin_system import PluginInterface

class Plugin(PluginInterface):
    metadata = {
        'name': 'My Plugin',
        'version': '1.0.0',
        'author': 'Your Name',
        'description': 'Does something cool',
        'enabled': True,
    }

    def on_init(self):
        print("Plugin initialized!")

    def register_hooks(self):
        return {
            'on_scan_complete': self.handle_scan_complete,
        }

    def handle_scan_complete(self, results):
        print(f"Scan done: {results}")
```

---

### `PluginManager` Class

#### `load_all_plugins()`
Discover and load all available plugins.

**Example:**
```python
from plugin_system import plugin_manager
plugin_manager.load_all_plugins()
```

---

#### `call_hook(hook_name: str, *args, **kwargs) -> List`
Call all callbacks registered for a hook.

**Example:**
```python
results = plugin_manager.call_hook('on_scan_complete', scan_results)
```

---

## Web API (api.py)

Web API endpoints are exposed via the pywebview JS bridge.

### Scanning

```javascript
// JavaScript in web UI
api.scan_temp().then(result => {
    console.log(`Found ${result.count} temp files`);
});
```

---

### Configuration

```javascript
// Get setting
api.get_config('ui.dark_mode').then(enabled => {
    if (enabled) document.body.classList.add('dark-mode');
});

// Set setting
api.set_config('cleaning.auto_clean_enabled', true);
```

---

### History

```javascript
// Get stats
api.get_history_stats().then(stats => {
    console.log(`Total cleaned: ${stats.total_cleaned_bytes} bytes`);
});
```

---

## Error Handling

All operations are wrapped with error reporting to history database:

```python
from history_db import history_db

try:
    result = some_operation()
except Exception as e:
    history_db.record_error(
        operation='some_operation',
        error_message=str(e),
        error_traceback=traceback.format_exc(),
        severity='error'
    )
```

---

## Threading & Concurrency

For long-running operations:

```python
from operation_context import OperationContext
from concurrent.futures import ThreadPoolExecutor

def scan_in_background(scan_func):
    context = OperationContext('scan_id')
    
    def worker():
        return scan_func(_operation_context=context)
    
    with ThreadPoolExecutor() as pool:
        future = pool.submit(worker)
        # Main thread can check context.get_progress()
        return future.result()
```

---

## Configuration File Format

Settings are stored in JSON at `%LOCALAPPDATA%/PCCleaner/settings.json`:

```json
{
  "general": {
    "auto_start_on_login": false,
    "check_for_updates": true,
    "update_check_interval_days": 7,
    "enable_logging": true
  },
  "cleaning": {
    "auto_clean_enabled": false,
    "auto_clean_schedule": "daily",
    "auto_clean_hour": 2,
    "auto_clean_minute": 0,
    "enable_confirmations": true,
    "skip_system_files": true
  },
  "ui": {
    "dark_mode": false,
    "startup_minimized": false,
    "auto_dismiss_scan_complete": false
  },
  "whitelist": {
    "folders": ["C:\\MyFolder", "D:\\Preserve\\This"]
  },
  "features": {
    "enable_drivers_cleanup": true,
    "enable_temp_cleanup": true,
    "enable_startup_optimize": true,
    "enable_registry_cleanup": true,
    "enable_vault": true,
    "enable_duplicate_finder": true,
    "enable_large_files": true
  }
}
```

---

## Logging

Logs are written to `%LOCALAPPDATA%/PCCleaner/logs/pccleaner.log` (rotating, 1MB max × 3 backups).

Log levels:
- `DEBUG`: Detailed diagnostic info
- `INFO`: Normal operation milestones
- `WARNING`: Recoverable issues (with retry)
- `ERROR`: Failed operations (included in history)

---

## Database Schema

### Scans Table
```sql
CREATE TABLE scans (
  id INTEGER PRIMARY KEY,
  timestamp DATETIME,
  scan_type TEXT,           -- 'temp_files', 'drivers', etc.
  duration_seconds REAL,
  items_found INTEGER,
  total_size_bytes INTEGER,
  status TEXT               -- 'completed', 'failed', 'cancelled'
);
```

### Cleaned Items Table
```sql
CREATE TABLE cleaned_items (
  id INTEGER PRIMARY KEY,
  scan_id INTEGER,
  timestamp DATETIME,
  category TEXT,            -- 'temp_files', 'cache', etc.
  item_path TEXT,
  size_bytes INTEGER,
  status TEXT               -- 'cleaned', 'failed'
);
```

---
