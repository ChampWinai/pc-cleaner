"""Core scanning/cleaning logic for PC Cleaner, shared by the web UI.

Pure Python, no UI toolkit imports here — this module is called from the
pywebview JS bridge (api.py) and could equally be unit-tested standalone.
"""

import ctypes
import glob
import json
import os
import re
import shutil
import subprocess
import uuid
import winreg
from datetime import datetime, timedelta

import psutil
import pythoncom
import win32com.client


def human_size(num_bytes):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"


def dir_size(path):
    total = 0
    for root, _dirs, files in os.walk(path, onerror=lambda e: None):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


# ---------------------------------------------------------------------------
# Scan targets + impact notes
# ---------------------------------------------------------------------------
IMPACT_NOTES = [
    ("Windows Update Cache", "safe", "ปลอดภัย — Windows จะดาวน์โหลดใหม่อัตโนมัติเมื่อมีอัปเดตครั้งถัดไป"),
    ("Delivery Optimization", "safe", "ปลอดภัย — เป็นแค่ไฟล์อัปเดตที่แชร์ให้เครื่องอื่นในเครือข่าย"),
    ("CBS/DISM", "safe", "ปลอดภัย — เป็น log การติดตั้ง/ซ่อมระบบเก่า ไม่กระทบการทำงาน"),
    ("Crash Dumps", "safe", "ปลอดภัย — ไฟล์วิเคราะห์การแครชที่ไม่ได้ใช้งานแล้ว"),
    ("Windows Installer Patch", "medium", "ระวัง — บางโปรแกรมอาจต้องใช้ไฟล์นี้ตอน uninstall/repair"),
    ("Prefetch", "safe", "ปลอดภัย — Windows จะสร้างใหม่เองเพื่อเร่งการเปิดโปรแกรม"),
    ("Thumbnail", "safe", "ปลอดภัย — รูปตัวอย่างจะถูกสร้างใหม่เมื่อเปิดโฟลเดอร์อีกครั้ง"),
    ("Windows Error Reports", "safe", "ปลอดภัย — รายงานข้อผิดพลาดเก่าที่ไม่จำเป็นแล้ว"),
    ("Internet Cache", "low", "เว็บไซต์บางเว็บอาจโหลดช้าลงเล็กน้อยในครั้งถัดไป ไม่กระทบรหัสผ่าน/ประวัติ"),
    ("Chrome Cache", "low", "เว็บโหลดช้าลงชั่วคราว ไม่กระทบรหัสผ่านหรือการล็อกอิน"),
    ("Edge Cache", "low", "เว็บโหลดช้าลงชั่วคราว ไม่กระทบรหัสผ่านหรือการล็อกอิน"),
    ("Firefox Cache", "low", "เว็บโหลดช้าลงชั่วคราว ไม่กระทบรหัสผ่านหรือการล็อกอิน"),
    ("Temp", "low", "โปรแกรมที่กำลังเปิดอยู่และใช้ไฟล์ temp ค้างไว้อาจทำงานผิดพลาดชั่วคราว"),
    ("Visual Studio Component Cache", "low", "Visual Studio จะสร้างใหม่เองตอนเปิดครั้งถัดไป อาจช้าขึ้นเล็กน้อยครั้งแรก"),
    ("NuGet HTTP Cache", "low", "โปรเจกต์ .NET จะดาวน์โหลด package ใหม่ตอน build ครั้งถัดไป"),
    ("Unreal Engine DDC", "medium", "ระวัง — Unreal ต้องคำนวณ Derived Data ใหม่ตอนเปิดโปรเจกต์ครั้งถัดไป อาจใช้เวลานานมาก"),
    ("Adobe Media Cache", "medium", "ระวัง — คลิปที่ตัดไว้ใน Premiere Pro/After Effects จะต้อง re-index/re-render cache ใหม่"),
    ("Shader Cache", "safe", "ปลอดภัย — การ์ดจอจะ compile shader ใหม่เองตอนเปิดเกม/โปรแกรมครั้งแรก อาจกระตุกสั้นๆ ครั้งเดียว"),
    ("OneDrive", "low", "ไฟล์ log ของ OneDrive ปลอดภัยที่จะลบ ไม่กระทบไฟล์ที่ sync อยู่"),
    ("Dropbox Cache", "low", "Dropbox เก็บไฟล์ที่ลบ/แก้ล่าสุดไว้กู้คืนชั่วคราว ลบแล้วกู้คืนผ่าน Dropbox เองไม่ได้ชั่วคราว"),
    ("Google Drive Cache", "low", "Google Drive จะดาวน์โหลดไฟล์ใหม่ตามต้องการเมื่อเปิดใช้งานอีกครั้ง"),
]


def get_impact(label):
    for key, risk, note in IMPACT_NOTES:
        if key.lower() in label.lower():
            return risk, note
    return "medium", "ไม่ทราบผลกระทบแน่ชัด ตรวจสอบก่อนลบหากไม่แน่ใจ"


def get_targets(deep=False):
    env = os.environ
    candidates = [
        ("Temp ผู้ใช้ (%TEMP%)", env.get("TEMP")),
        ("Temp ระบบ (Windows\\Temp)", os.path.join(env.get("WINDIR", r"C:\Windows"), "Temp")),
        ("Prefetch", os.path.join(env.get("WINDIR", r"C:\Windows"), "Prefetch")),
        ("Internet Cache (INetCache)",
         os.path.join(env.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "INetCache")),
        ("Chrome Cache",
         os.path.join(env.get("LOCALAPPDATA", ""), "Google", "Chrome", "User Data",
                       "Default", "Cache")),
        ("Edge Cache",
         os.path.join(env.get("LOCALAPPDATA", ""), "Microsoft", "Edge", "User Data",
                       "Default", "Cache")),
        ("Windows Error Reports",
         os.path.join(env.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "WER")),
        ("Thumbnail Cache",
         os.path.join(env.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Explorer")),
    ]
    if deep:
        candidates += [
            ("Firefox Cache",
             os.path.join(env.get("LOCALAPPDATA", ""), "Mozilla", "Firefox", "Profiles")),
            ("Windows Update Cache",
             os.path.join(env.get("WINDIR", r"C:\Windows"), "SoftwareDistribution", "Download")),
            ("Delivery Optimization Cache",
             os.path.join(env.get("WINDIR", r"C:\Windows"), "ServiceProfiles", "NetworkService",
                           "AppData", "Local", "Microsoft", "Windows", "DeliveryOptimization",
                           "Cache")),
            ("CBS/DISM Logs",
             os.path.join(env.get("WINDIR", r"C:\Windows"), "Logs", "CBS")),
            ("Windows Installer Patch Cache",
             os.path.join(env.get("WINDIR", r"C:\Windows"), "Installer", "$PatchCache$")),
            ("Crash Dumps",
             os.path.join(env.get("LOCALAPPDATA", ""), "CrashDumps")),
        ]
        candidates += _expand_dev_tool_targets(env)
        candidates += _expand_shader_cloud_targets(env)
    return [(label, path) for label, path in candidates if path and os.path.isdir(path)]


def _expand_dev_tool_targets(env):
    """Specialized cache locations for dev/creative tools, which stock
    cleaners usually miss even though they can eat tens of GB. Patterns with
    a `*` are expanded per-installed-version via glob.
    """
    local = env.get("LOCALAPPDATA", "")
    patterns = [
        ("Visual Studio Component Cache", os.path.join(local, "Microsoft", "VisualStudio", "*", "ComponentModelCache")),
        ("NuGet HTTP Cache", os.path.join(local, "NuGet", "v3-cache")),
        ("Unreal Engine DDC (Global)", os.path.join(local, "UnrealEngine", "Common", "DerivedDataCache")),
        ("Adobe Media Cache", os.path.join(local, "Adobe", "Common", "Media Cache Files")),
        ("Adobe Media Cache (DB)", os.path.join(local, "Adobe", "Common", "Media Cache")),
    ]
    out = []
    for label, pattern in patterns:
        if "*" in pattern:
            matches = glob.glob(pattern)
            for m in matches:
                suffix = f" ({os.path.basename(os.path.dirname(m))})" if len(matches) > 1 else ""
                out.append((label + suffix, m))
        else:
            out.append((label, pattern))
    return out


def _expand_shader_cloud_targets(env):
    """GPU shader caches and local cloud-sync cache folders — both safe to
    clear (regenerate/redownload automatically) but overlooked by most
    cleaners because they live in vendor-specific, easy-to-miss paths.
    """
    local = env.get("LOCALAPPDATA", "")
    appdata = env.get("APPDATA", "")
    userprofile = env.get("USERPROFILE", "")

    fixed = [
        ("Shader Cache (NVIDIA DX)", os.path.join(local, "NVIDIA", "DXCache")),
        ("Shader Cache (NVIDIA GL)", os.path.join(local, "NVIDIA", "GLCache")),
        ("Shader Cache (AMD Dx)", os.path.join(local, "AMD", "DxCache")),
        ("Shader Cache (AMD Dxc)", os.path.join(local, "AMD", "DxcCache")),
        ("Shader Cache (Intel)", os.path.join(local, "Intel", "ShaderCache")),
        ("Shader Cache (DirectX)", os.path.join(local, "D3DSCache")),
        ("OneDrive Logs", os.path.join(local, "Microsoft", "OneDrive", "logs")),
        ("Dropbox Cache", os.path.join(userprofile, "Dropbox", ".dropbox.cache")),
    ]
    out = [(label, path) for label, path in fixed]

    for m in glob.glob(os.path.join(local, "Google", "DriveFS", "*", "content_cache")):
        out.append(("Google Drive Cache", m))

    return out


def list_children(path, limit=24):
    """Return the immediate children of `path` sorted by size, for treemap
    drill-down. Each child's size is computed on demand (full walk for
    directories), so this is meant to be called lazily per click rather than
    eagerly for the whole tree.
    """
    try:
        names = os.listdir(path)
    except OSError:
        return []

    items = []
    for name in names:
        full = os.path.join(path, name)
        try:
            if os.path.isdir(full):
                size = dir_size(full)
                is_dir = True
            else:
                size = os.path.getsize(full)
                is_dir = False
        except OSError:
            continue
        if size > 0:
            items.append({"name": name, "path": full, "size": size, "is_dir": is_dir})

    items.sort(key=lambda x: x["size"], reverse=True)
    if len(items) > limit:
        rest = items[limit:]
        rest_total = sum(i["size"] for i in rest)
        items = items[:limit]
        items.append({
            "name": f"อื่นๆ ({len(rest)} รายการ)",
            "path": None,
            "size": rest_total,
            "is_dir": False,
        })
    return items


def scan(deep=False):
    """Return a list of {label, path, size, risk, note} for non-empty targets."""
    found = []
    for label, path in get_targets(deep=deep):
        size = dir_size(path)
        if size > 0:
            risk, note = get_impact(label)
            found.append({"label": label, "path": path, "size": size, "risk": risk, "note": note})
    found.sort(key=lambda it: it["size"], reverse=True)
    return found


# ---------------------------------------------------------------------------
# Recycle Bin
# ---------------------------------------------------------------------------
def empty_recycle_bin():
    SHERB_NOCONFIRMATION = 0x00000001
    SHERB_NOPROGRESSUI = 0x00000002
    SHERB_NOSOUND = 0x00000004
    flags = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
    result = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
    return result in (0, -2147418113, 0x8000FFFF) or result == 0x80070002


# ---------------------------------------------------------------------------
# RAM
# ---------------------------------------------------------------------------
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_SET_QUOTA = 0x0100

TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008
SE_PRIVILEGE_ENABLED = 0x0002
SE_DEBUG_NAME = "SeDebugPrivilege"


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", ctypes.c_uint32), ("HighPart", ctypes.c_int32)]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Luid", LUID), ("Attributes", ctypes.c_uint32)]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [("PrivilegeCount", ctypes.c_uint32), ("Privileges", LUID_AND_ATTRIBUTES * 1)]


def enable_debug_privilege():
    """Enable SeDebugPrivilege on our own process token.

    Running "as Administrator" alone is not enough to open SYSTEM-owned
    processes (System, Registry, csrss.exe, ...) — that additionally
    requires this privilege to be explicitly turned on, which Windows does
    not do automatically even for elevated admin processes. Without it,
    OpenProcess silently fails for those PIDs and they get reported as
    "skipped" no matter how the app was launched.
    """
    advapi32 = ctypes.windll.advapi32
    kernel32 = ctypes.windll.kernel32

    h_token = ctypes.c_void_p()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, ctypes.byref(h_token)
    ):
        return False

    try:
        luid = LUID()
        if not advapi32.LookupPrivilegeValueW(None, SE_DEBUG_NAME, ctypes.byref(luid)):
            return False

        tp = TOKEN_PRIVILEGES()
        tp.PrivilegeCount = 1
        tp.Privileges[0].Luid = luid
        tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED

        if not advapi32.AdjustTokenPrivileges(h_token, False, ctypes.byref(tp), 0, None, None):
            return False
        # AdjustTokenPrivileges can "succeed" but not actually grant the
        # privilege (e.g. not running elevated) — GetLastError distinguishes.
        return kernel32.GetLastError() == 0
    finally:
        kernel32.CloseHandle(h_token)


def ram_status():
    vm = psutil.virtual_memory()
    return {"total": vm.total, "used": vm.used, "available": vm.available, "percent": vm.percent}


def trim_process_working_sets():
    enable_debug_privilege()
    psapi = ctypes.windll.psapi
    kernel32 = ctypes.windll.kernel32
    trimmed = 0
    skipped = 0
    for proc in psutil.process_iter(["pid"]):
        pid = proc.info["pid"]
        if pid == 0:
            continue
        handle = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_SET_QUOTA, False, pid
        )
        if not handle:
            skipped += 1
            continue
        try:
            if psapi.EmptyWorkingSet(handle):
                trimmed += 1
            else:
                skipped += 1
        finally:
            kernel32.CloseHandle(handle)
    return trimmed, skipped


# ---------------------------------------------------------------------------
# Safety Vault
# ---------------------------------------------------------------------------
VAULT_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "PCCleanerVault")
VAULT_INDEX_PATH = os.path.join(VAULT_DIR, "index.json")
VAULT_RETENTION_DAYS = 14


def _load_vault_index():
    if not os.path.isfile(VAULT_INDEX_PATH):
        return []
    try:
        with open(VAULT_INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def _save_vault_index(entries):
    os.makedirs(VAULT_DIR, exist_ok=True)
    with open(VAULT_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def vault_list():
    return sorted(_load_vault_index(), key=lambda e: e["deleted_at"], reverse=True)


def move_to_vault(original_path, batch_id, label):
    os.makedirs(os.path.join(VAULT_DIR, batch_id), exist_ok=True)
    size = os.path.getsize(original_path) if os.path.isfile(original_path) else dir_size(original_path)
    vault_name = f"{uuid.uuid4().hex}_{os.path.basename(original_path)}"
    vault_path = os.path.join(VAULT_DIR, batch_id, vault_name)
    shutil.move(original_path, vault_path)

    entry = {
        "id": uuid.uuid4().hex,
        "label": label,
        "original_path": original_path,
        "vault_path": vault_path,
        "size": size,
        "deleted_at": datetime.now().isoformat(),
    }
    entries = _load_vault_index()
    entries.append(entry)
    _save_vault_index(entries)
    return entry


def restore_from_vault(entry_id):
    entries = _load_vault_index()
    match = next((e for e in entries if e["id"] == entry_id), None)
    if not match:
        return False
    os.makedirs(os.path.dirname(match["original_path"]), exist_ok=True)
    if os.path.exists(match["original_path"]):
        return False
    shutil.move(match["vault_path"], match["original_path"])
    entries.remove(match)
    _save_vault_index(entries)
    return True


def purge_vault_entry(entry_id):
    entries = _load_vault_index()
    match = next((e for e in entries if e["id"] == entry_id), None)
    if not match:
        return
    if os.path.isdir(match["vault_path"]):
        shutil.rmtree(match["vault_path"], ignore_errors=True)
    elif os.path.isfile(match["vault_path"]):
        try:
            os.remove(match["vault_path"])
        except OSError:
            pass
    entries.remove(match)
    _save_vault_index(entries)


def purge_expired_vault_entries():
    cutoff = datetime.now() - timedelta(days=VAULT_RETENTION_DAYS)
    entries = _load_vault_index()
    still_valid = []
    for entry in entries:
        try:
            deleted_at = datetime.fromisoformat(entry["deleted_at"])
        except (KeyError, ValueError):
            still_valid.append(entry)
            continue
        if deleted_at < cutoff:
            path = entry["vault_path"]
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.isfile(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        else:
            still_valid.append(entry)
    _save_vault_index(still_valid)
    return still_valid


def clean_items(selected):
    """Move the contents of each selected target folder into the vault.

    `selected` is a list of {label, path} dicts (as sent from the UI).
    Returns (freed_bytes, errors, batch_id).
    """
    errors = []
    freed = 0
    batch_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    for it in selected:
        path = it["path"]
        if not os.path.isdir(path):
            continue
        for entry in os.listdir(path):
            full = os.path.join(path, entry)
            try:
                size_before = os.path.getsize(full) if os.path.isfile(full) else dir_size(full)
                move_to_vault(full, batch_id, it["label"])
                freed += size_before
            except OSError as e:
                errors.append(f"{full}: {e}")
    return freed, errors, batch_id


# ---------------------------------------------------------------------------
# Docker cache — deleting Docker's internal files directly can corrupt the
# WSL2 disk image, so this shells out to the official `docker` CLI instead
# (same as running `docker system prune` yourself).
# ---------------------------------------------------------------------------
def docker_available():
    return shutil.which("docker") is not None


def docker_prune():
    if not docker_available():
        return {"success": False, "message": "ไม่พบ Docker บนเครื่องนี้", "freed_human": "0 B"}
    try:
        result = subprocess.run(
            ["docker", "system", "prune", "-f"],
            capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"success": False, "message": str(e), "freed_human": "0 B"}

    if result.returncode != 0:
        return {"success": False, "message": result.stderr.strip()[:300], "freed_human": "0 B"}

    freed_human = "0 B"
    for line in result.stdout.splitlines():
        if "reclaimed space" in line.lower():
            freed_human = line.split(":")[-1].strip()
    return {"success": True, "message": result.stdout.strip()[:500], "freed_human": freed_human}


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


def uninstall_app(uninstall_string):
    """Launch the app's own uninstaller (same command Windows would run).

    We can't safely automate away vendor confirmation dialogs, so this just
    kicks off the native uninstaller and lets the user finish the flow.
    """
    try:
        subprocess.Popen(uninstall_string, shell=True)
        return True
    except OSError:
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
            return False, "ต้องรันโปรแกรมแบบ Administrator เพื่อเปิดรายการนี้"
    elif match["source"] == "folder":
        original_path = match.get("_original_path", os.path.join(match["keypath"], match["name"]))
        try:
            shutil.move(match["command"], original_path)
        except OSError:
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
        try:
            with winreg.OpenKey(root, subpath, 0, winreg.KEY_ALL_ACCESS) as key:
                winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)
        except OSError:
            pass
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
