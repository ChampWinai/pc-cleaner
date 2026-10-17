"""System tools behind the non-cleaning tabs: app uninstaller, startup
manager, Game Mode, sensitive-data scanner, hardware/driver check, and the
network / winget / large-file / context-menu helpers.

Split out of backend.py, which keeps the scan/clean/vault/Auto Clean core.
backend re-exports these names so api.py and older callers keep working.
"""

import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import winreg
from datetime import datetime

import psutil
import pythoncom
import win32com.client

from logging_setup import get_logger

log = get_logger(__name__)

# Same folder as backend.VAULT_DIR (can't import it: backend re-exports us).
VAULT_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "PCCleanerVault")

# ---------------------------------------------------------------------------
# App Uninstaller — reads the same registry Uninstall keys that Windows'
# own "Apps & Features" panel reads from.
# ---------------------------------------------------------------------------
UNINSTALL_ROOTS = [
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
]


def _read_reg_value(key, name, default=None):
    try:
        value, _ = winreg.QueryValueEx(key, name)
        return value
    except FileNotFoundError:
        return default


def list_installed_apps():
    apps = []
    seen = set()
    for root, subpath in UNINSTALL_ROOTS:
        try:
            root_key = winreg.OpenKey(root, subpath)
        except OSError:
            continue
        with root_key:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(root_key, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(root_key, subkey_name) as key:
                        name = _read_reg_value(key, "DisplayName")
                        if not name:
                            continue
                        if _read_reg_value(key, "SystemComponent", 0) == 1:
                            continue
                        uninstall_string = _read_reg_value(key, "UninstallString")
                        if not uninstall_string:
                            continue
                        dedupe_key = (name, _read_reg_value(key, "Publisher", ""))
                        if dedupe_key in seen:
                            continue
                        seen.add(dedupe_key)

                        size_kb = _read_reg_value(key, "EstimatedSize", 0) or 0
                        apps.append({
                            "id": subkey_name,
                            "name": name,
                            "publisher": _read_reg_value(key, "Publisher", "ไม่ทราบผู้พัฒนา"),
                            "version": _read_reg_value(key, "DisplayVersion", ""),
                            "size": int(size_kb) * 1024,
                            "install_location": _read_reg_value(key, "InstallLocation", ""),
                            "uninstall_string": uninstall_string,
                            "quiet_uninstall_string": _read_reg_value(key, "QuietUninstallString", ""),
                        })
                except OSError:
                    continue
    apps.sort(key=lambda a: a["size"], reverse=True)
    return apps


def uninstall_app(app_id):
    """Launch the app's own uninstaller (same command Windows would run).

    Takes the registry key id, not a command: the command is read from the
    registry here, so the UI can never make us run an arbitrary string.
    Launched without a shell; CreateProcess parses the command line.
    """
    app = next((a for a in list_installed_apps() if a["id"] == app_id), None)
    if not app:
        return False
    cmd = app["quiet_uninstall_string"] or app["uninstall_string"]
    try:
        subprocess.Popen(cmd)
        return True
    except OSError:
        log.warning("Failed to launch uninstaller: %s", cmd, exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Startup Manager — Registry Run keys + Startup folder shortcuts.
# Disabling an item moves its data into our own backup index (rather than
# Windows' undocumented StartupApproved binary flags) so re-enabling is a
# plain, reliable reversal we fully control.
# ---------------------------------------------------------------------------
STARTUP_BACKUP_DIR = os.path.join(VAULT_DIR, "StartupBackup")
STARTUP_BACKUP_INDEX = os.path.join(STARTUP_BACKUP_DIR, "index.json")

RUN_KEY_ROOTS = [
    (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKCU"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run", "HKLM"),
    (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "HKLM32"),
]


def _startup_folders():
    env = os.environ
    return [
        os.path.join(env.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup"),
        os.path.join(env.get("PROGRAMDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "StartUp"),
    ]


def _load_startup_backup():
    if not os.path.isfile(STARTUP_BACKUP_INDEX):
        return []
    try:
        with open(STARTUP_BACKUP_INDEX, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _save_startup_backup(entries):
    os.makedirs(STARTUP_BACKUP_DIR, exist_ok=True)
    with open(STARTUP_BACKUP_INDEX, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def _delayed_task_names():
    try:
        result = subprocess.run(
            ["schtasks", "/query", "/fo", "csv"], capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    names = []
    for line in result.stdout.splitlines()[1:]:
        cells = line.split('","')
        if not cells:
            continue
        task_name = cells[0].strip('"')
        base = task_name.rsplit("\\", 1)[-1]
        if base.startswith("PCCleaner_Delay_"):
            names.append(base)
    return names


def list_startup_items():
    items = []

    for root, subpath, hive_label in RUN_KEY_ROOTS:
        try:
            key = winreg.OpenKey(root, subpath)
        except OSError:
            continue
        with key:
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                except OSError:
                    break
                i += 1
                items.append({
                    "id": f"reg::{hive_label}::{name}",
                    "name": name,
                    "command": value,
                    "source": "registry",
                    "hive": hive_label,
                    "keypath": subpath,
                    "status": "enabled",
                })

    for folder in _startup_folders():
        if not os.path.isdir(folder):
            continue
        for entry in os.listdir(folder):
            full = os.path.join(folder, entry)
            if os.path.isfile(full):
                items.append({
                    "id": f"folder::{full}",
                    "name": entry,
                    "command": full,
                    "source": "folder",
                    "hive": "",
                    "keypath": folder,
                    "status": "enabled",
                })

    for entry in _load_startup_backup():
        items.append({**entry, "status": "disabled"})

    for task_name in _delayed_task_names():
        items.append({
            "id": f"delayed::{task_name}",
            "name": task_name.replace("PCCleaner_Delay_", ""),
            "command": "",
            "source": "task",
            "hive": "",
            "keypath": "",
            "status": "delayed",
        })

    return items


def disable_startup_item(item_id):
    """Remove a Run-key value / move a Startup-folder shortcut into our
    backup index so it stops launching, but can be restored exactly.
    """
    if item_id.startswith("reg::"):
        _, hive_label, name = item_id.split("::", 2)
        root, subpath, _ = next(r for r in RUN_KEY_ROOTS if r[2] == hive_label)
        try:
            with winreg.OpenKey(root, subpath, 0, winreg.KEY_ALL_ACCESS) as key:
                value, _ = winreg.QueryValueEx(key, name)
                winreg.DeleteValue(key, name)
        except OSError:
            log.warning("Failed to disable registry startup item %s", item_id, exc_info=True)
            return False, "ต้องรันโปรแกรมแบบ Administrator เพื่อปิดรายการนี้"

        backups = _load_startup_backup()
        backups.append({
            "id": item_id, "name": name, "command": value,
            "source": "registry", "hive": hive_label, "keypath": subpath,
        })
        _save_startup_backup(backups)
        return True, ""

    if item_id.startswith("folder::"):
        original_path = item_id.split("::", 1)[1]
        os.makedirs(STARTUP_BACKUP_DIR, exist_ok=True)
        backup_path = os.path.join(STARTUP_BACKUP_DIR, os.path.basename(original_path))
        try:
            shutil.move(original_path, backup_path)
        except OSError:
            log.warning("Failed to move startup shortcut %s", original_path, exc_info=True)
            return False, "ย้ายไฟล์ shortcut ไม่สำเร็จ"

        backups = _load_startup_backup()
        backups.append({
            "id": item_id, "name": os.path.basename(original_path), "command": backup_path,
            "source": "folder", "hive": "", "keypath": os.path.dirname(original_path),
            "_original_path": original_path,
        })
        _save_startup_backup(backups)
        return True, ""

    return False, "ไม่รองรับรายการประเภทนี้"


def enable_startup_item(item_id):
    backups = _load_startup_backup()
    match = next((b for b in backups if b["id"] == item_id), None)
    if not match:
        return False, "ไม่พบข้อมูลสำรองของรายการนี้"

    if match["source"] == "registry":
        root, subpath, _ = next(r for r in RUN_KEY_ROOTS if r[2] == match["hive"])
        try:
            with winreg.OpenKey(root, subpath, 0, winreg.KEY_ALL_ACCESS) as key:
                winreg.SetValueEx(key, match["name"], 0, winreg.REG_SZ, match["command"])
        except OSError:
            log.warning("Failed to enable registry startup item %s", item_id, exc_info=True)
            return False, "ต้องรันโปรแกรมแบบ Administrator เพื่อเปิดรายการนี้"
    elif match["source"] == "folder":
        original_path = match.get("_original_path", os.path.join(match["keypath"], match["name"]))
        try:
            shutil.move(match["command"], original_path)
        except OSError:
            log.warning("Failed to restore startup shortcut for %s", item_id, exc_info=True)
            return False, "ย้ายไฟล์ shortcut กลับไม่สำเร็จ"

    backups.remove(match)
    _save_startup_backup(backups)
    return True, ""


def delay_startup_item(item_id, delay_minutes=2):
    """Convert a Run-key startup entry into a Scheduled Task that fires a
    couple of minutes after logon, so it doesn't compete with boot I/O.
    """
    if not item_id.startswith("reg::"):
        return False, "หน่วงเวลาได้เฉพาะรายการจาก Registry Run key เท่านั้น"

    _, hive_label, name = item_id.split("::", 2)
    root, subpath, _ = next(r for r in RUN_KEY_ROOTS if r[2] == hive_label)
    try:
        with winreg.OpenKey(root, subpath, 0, winreg.KEY_ALL_ACCESS) as key:
            command, _ = winreg.QueryValueEx(key, name)
            winreg.DeleteValue(key, name)
    except OSError:
        log.warning("Failed to remove Run key for delayed startup item %s", item_id, exc_info=True)
        return False, "ต้องรันโปรแกรมแบบ Administrator เพื่อหน่วงเวลารายการนี้"

    task_name = f"PCCleaner_Delay_{name}"
    delay_str = f"{delay_minutes:04d}:00"
    try:
        subprocess.run(
            ["schtasks", "/create", "/tn", task_name, "/tr", command,
             "/sc", "onlogon", "/delay", delay_str, "/rl", "limited", "/f"],
            capture_output=True, text=True, timeout=15, check=True,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # Put the original Run entry back so we didn't just delete it for nothing.
        log.warning("Failed to create delayed-start scheduled task %s", task_name, exc_info=True)
        try:
            with winreg.OpenKey(root, subpath, 0, winreg.KEY_ALL_ACCESS) as key:
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
        except OSError:
            log.error("Failed to restore Run key %s after scheduled task creation failed", name, exc_info=True)
        return False, "สร้าง Scheduled Task ไม่สำเร็จ"

    return True, ""


def undo_delay_startup_item(task_name):
    """Cancel a delayed-start scheduled task (does not restore the original
    Run key — the app can be re-added manually, or this simply frees the
    user from the delay if they'd rather it not start automatically at all).
    """
    full_task_name = f"PCCleaner_Delay_{task_name}" if not task_name.startswith("PCCleaner_Delay_") else task_name
    try:
        subprocess.run(
            ["schtasks", "/delete", "/tn", full_task_name, "/f"],
            capture_output=True, text=True, timeout=15,
        )
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


# ---------------------------------------------------------------------------
# Game Mode — manual, user-picked "freeze these background apps" toggle.
# Deliberately NOT an automatic "detect a game and freeze everything else"
# system: silently suspending arbitrary processes is exactly the kind of
# thing that causes phantom crashes users can't diagnose, so the user picks
# the exact list every time and can resume it with one click.
# ---------------------------------------------------------------------------
GAME_MODE_EXCLUDE = {
    "system", "system idle process", "registry", "secure system",
    "memcompression", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
    "services.exe", "lsass.exe", "svchost.exe", "explorer.exe", "dwm.exe",
    "fontdrvhost.exe", "sihost.exe", "ctfmon.exe", "taskhostw.exe",
    "pccleaner.exe", "python.exe",
    # Security software — suspending your own AV is the kind of thing that
    # looks identical to what malware does right before it does something bad.
    "msmpeng.exe", "nissrv.exe", "securityhealthservice.exe", "smartscreen.exe",
}
PROCESS_SUSPEND_RESUME = 0x0800

_suspended_pids = []  # module-level: tracks what *this* Game Mode session paused


def list_freezable_processes():
    """Group running processes by name (Chrome/Discord/etc. spawn many PIDs)
    so the user picks an app once instead of ticking 10 chrome.exe rows.
    """
    current_pid = os.getpid()
    grouped = {}
    for p in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            name = p.info["name"]
            pid = p.info["pid"]
            if not name or pid == current_pid or name.lower() in GAME_MODE_EXCLUDE:
                continue
            mem = p.info["memory_info"].rss if p.info["memory_info"] else 0
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        g = grouped.setdefault(name, {"name": name, "pids": [], "memory": 0})
        g["pids"].append(pid)
        g["memory"] += mem
    items = list(grouped.values())
    items.sort(key=lambda x: x["memory"], reverse=True)
    return items


def is_game_mode_active():
    return len(_suspended_pids) > 0


def enable_game_mode(process_names):
    global _suspended_pids
    ntdll = ctypes.windll.ntdll
    kernel32 = ctypes.windll.kernel32
    names = set(process_names)
    suspended = []
    for p in psutil.process_iter(["pid", "name"]):
        if p.info["name"] not in names:
            continue
        handle = kernel32.OpenProcess(PROCESS_SUSPEND_RESUME, False, p.info["pid"])
        if not handle:
            continue
        try:
            if ntdll.NtSuspendProcess(handle) == 0:
                suspended.append(p.info["pid"])
        finally:
            kernel32.CloseHandle(handle)
    _suspended_pids = suspended
    return len(suspended)


def disable_game_mode():
    global _suspended_pids
    ntdll = ctypes.windll.ntdll
    kernel32 = ctypes.windll.kernel32
    total = len(_suspended_pids)
    resumed = 0
    for pid in _suspended_pids:
        handle = kernel32.OpenProcess(PROCESS_SUSPEND_RESUME, False, pid)
        if not handle:
            continue
        try:
            if ntdll.NtResumeProcess(handle) == 0:
                resumed += 1
        finally:
            kernel32.CloseHandle(handle)
    _suspended_pids = []
    return resumed, total


# ---------------------------------------------------------------------------
# Sensitive Data Scanner — heuristic (regex-based, not "AI") scan of a
# user-chosen folder for likely Thai national ID numbers, credit card
# numbers, and plaintext "password = ..." style lines. Bounded to plain-text
# file types and a folder the user explicitly picks, never the whole disk.
# ---------------------------------------------------------------------------
TEXT_EXTENSIONS = {".txt", ".csv", ".log", ".json", ".xml", ".ini", ".md", ".cfg", ".conf"}
MAX_SCAN_FILES = 1500
MAX_FILE_BYTES = 2_000_000

THAI_ID_RE = re.compile(r"\b\d{1}[- ]?\d{4}[- ]?\d{5}[- ]?\d{2}[- ]?\d{1}\b")
CARD_RE = re.compile(r"\b(?:\d[ -]?){13,16}\b")
PASSWORD_RE = re.compile(r"(password|pwd|passwd|รหัสผ่าน)\s*[:=]\s*\S+", re.IGNORECASE)


def _valid_thai_id(digits):
    if len(digits) != 13 or not digits.isdigit():
        return False
    total = sum(int(d) * (13 - i) for i, d in enumerate(digits[:12]))
    check = (11 - (total % 11)) % 10
    return check == int(digits[12])


def _luhn_valid(digits):
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def _mask(value):
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


def scan_sensitive_data(folder):
    findings = []
    scanned = 0
    for root, _dirs, files in os.walk(folder, onerror=lambda e: None):
        for name in files:
            if scanned >= MAX_SCAN_FILES:
                return findings
            ext = os.path.splitext(name)[1].lower()
            if ext not in TEXT_EXTENSIONS:
                continue
            full = os.path.join(root, name)
            scanned += 1
            try:
                if os.path.getsize(full) > MAX_FILE_BYTES:
                    continue
                with open(full, "r", encoding="utf-8", errors="ignore") as f:
                    for lineno, line in enumerate(f, start=1):
                        for m in THAI_ID_RE.finditer(line):
                            digits = re.sub(r"[- ]", "", m.group())
                            if _valid_thai_id(digits):
                                findings.append({
                                    "path": full, "line": lineno, "category": "thai_id",
                                    "snippet": _mask(digits),
                                })
                        for m in CARD_RE.finditer(line):
                            digits = re.sub(r"[ -]", "", m.group())
                            if len(digits) in (13, 15, 16) and _luhn_valid(digits):
                                findings.append({
                                    "path": full, "line": lineno, "category": "credit_card",
                                    "snippet": _mask(digits),
                                })
                        for m in PASSWORD_RE.finditer(line):
                            findings.append({
                                "path": full, "line": lineno, "category": "password",
                                "snippet": _mask(m.group()),
                            })
            except OSError:
                continue
    return findings


def shred_file(path):
    """Best-effort secure delete: overwrite with random bytes before removing.
    Not a match for forensic-grade tools on SSDs with wear-leveling, but far
    better than a normal delete for casual recovery attempts.
    """
    try:
        length = os.path.getsize(path)
        with open(path, "r+b") as f:
            f.write(os.urandom(length))
            f.flush()
            os.fsync(f.fileno())
        os.remove(path)
        return True
    except OSError:
        log.warning("Failed to shred file %s", path, exc_info=True)
        return False


# ---------------------------------------------------------------------------
# Hardware & Driver update check.
#
# Driver INSTALLATION is deliberately not automated here: a bad driver push
# can blue-screen a machine, and doing it silently is exactly the kind of
# thing that makes "PC optimizer" tools untrustworthy. Instead this reads
# what's currently installed (WMI) and asks the real Windows Update Agent
# what driver updates it has staged, then hands the user off to the native
# Windows Update UI to actually apply them.
# ---------------------------------------------------------------------------
def _parse_wmi_date(value):
    """WMI CIM_DATETIME looks like '20230114000000.000000+000'."""
    if not value or len(value) < 8:
        return None
    try:
        return datetime.strptime(value[:8], "%Y%m%d")
    except ValueError:
        return None


def list_drivers():
    pythoncom.CoInitialize()
    try:
        wmi = win32com.client.GetObject("winmgmts:")
        rows = wmi.ExecQuery(
            "SELECT DeviceName, DriverVersion, DriverDate, Manufacturer, DeviceClass "
            "FROM Win32_PnPSignedDriver WHERE DeviceName IS NOT NULL"
        )
        drivers = []
        for d in rows:
            date = _parse_wmi_date(d.DriverDate)
            age_days = (datetime.now() - date).days if date else None
            drivers.append({
                "name": d.DeviceName,
                "version": d.DriverVersion or "",
                "manufacturer": d.Manufacturer or "",
                "device_class": d.DeviceClass or "",
                "date": date.strftime("%Y-%m-%d") if date else "ไม่ทราบ",
                "age_days": age_days,
            })
        drivers.sort(key=lambda x: (x["age_days"] is None, -(x["age_days"] or 0)))
        return drivers
    finally:
        pythoncom.CoUninitialize()


def check_driver_updates():
    """Ask the Windows Update Agent for pending driver updates.

    Returns {"success": bool, "updates": [...], "message": str}. This is a
    real network call to Windows Update and can take a while, so callers
    should run it off the UI thread.
    """
    pythoncom.CoInitialize()
    try:
        session = win32com.client.Dispatch("Microsoft.Update.Session")
        searcher = session.CreateUpdateSearcher()
        result = searcher.Search("IsInstalled=0 and Type='Driver'")
        updates = []
        for i in range(result.Updates.Count):
            u = result.Updates.Item(i)
            updates.append({
                "title": u.Title,
                "description": (u.Description or "")[:220],
                "size_mb": round((u.MaxDownloadSize or 0) / (1024 * 1024), 1),
            })
        return {"success": True, "updates": updates, "message": ""}
    except Exception as e:  # noqa: BLE001 — COM errors surface as generic Exception
        return {"success": False, "updates": [], "message": str(e)}
    finally:
        pythoncom.CoUninitialize()


def open_windows_update():
    try:
        os.startfile("ms-settings:windowsupdate")
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Network Flush - Clear DNS and winsock
# ---------------------------------------------------------------------------
def network_flush():
    results = []
    commands = [
        ("ipconfig /flushdns", "Flush DNS"),
        ("netsh winsock reset", "Winsock Reset")
    ]
    for cmd, name in commands:
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            results.append({"name": name, "success": res.returncode == 0, "output": res.stdout.strip()[:100]})
        except Exception as e:
            results.append({"name": name, "success": False, "output": str(e)})
    return results

# ---------------------------------------------------------------------------
# Winget - Software Updater
# ---------------------------------------------------------------------------
def update_software_winget():
    try:
        res = subprocess.run(["winget", "upgrade", "--all", "--silent", "--accept-package-agreements", "--accept-source-agreements"], 
                             capture_output=True, text=True, timeout=300)
        return {"success": res.returncode == 0, "output": res.stdout.strip()[-500:]}
    except Exception as e:
        return {"success": False, "output": str(e)}

# ---------------------------------------------------------------------------
# Disk Analyzer (Large Files)
# ---------------------------------------------------------------------------
def scan_large_files(drive="C:\\", limit=50, min_size_mb=100):
    large_files = []
    min_bytes = min_size_mb * 1024 * 1024
    start_time = datetime.now()
    try:
        for root, dirs, files in os.walk(drive):
            if (datetime.now() - start_time).seconds > 15:
                break
            for name in files:
                full = os.path.join(root, name)
                try:
                    size = os.path.getsize(full)
                    if size >= min_bytes:
                        large_files.append({"path": full, "size": size})
                except OSError:
                    continue
    except Exception:
        pass
        
    large_files.sort(key=lambda x: x["size"], reverse=True)
    return large_files[:limit]

# ---------------------------------------------------------------------------
# Context Menu Integration
# ---------------------------------------------------------------------------
def add_context_menu():
    try:
        key_path = r"Directory\shell\PCCleaner"
        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, key_path) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, "Clean with PC Cleaner")
            winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, f'"{sys.executable}",0')
        
        command_path = rf"{key_path}\command"
        with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, command_path) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, f'"{sys.executable}" "%1"')
        return True
    except PermissionError:
        return False

def remove_context_menu():
    try:
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"Directory\shell\PCCleaner\command")
        winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"Directory\shell\PCCleaner")
        return True
    except FileNotFoundError:
        return True
    except PermissionError:
        return False
