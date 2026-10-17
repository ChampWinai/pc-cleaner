"""Core scanning/cleaning logic for PC Cleaner, shared by the web UI.

Pure Python, no UI toolkit imports here — this module is called from the
pywebview JS bridge (api.py) and could equally be unit-tested standalone.
"""

import concurrent.futures
import contextlib
import ctypes
import glob
import json
import msvcrt
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta

import psutil

from logging_setup import get_logger
from history_db import history_db
from operation_context import RetryConfig

log = get_logger(__name__)

# Default retry config for I/O operations
IO_RETRY_CONFIG = RetryConfig(max_attempts=3, initial_delay=0.5, max_delay=5)


def human_size(num_bytes):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} PB"


def dir_size(path):
    """Sum file sizes under `path`. Uses os.scandir (not os.walk +
    os.path.getsize) so each file is stat'd once instead of twice -- matters
    a lot for cache folders with tens of thousands of small files.
    """
    total = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        else:
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        pass
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
    ("npm Cache", "safe", "ปลอดภัย — npm จะดาวน์โหลด package ใหม่ตอน install ครั้งถัดไป"),
    ("Yarn Cache", "safe", "ปลอดภัย — Yarn จะดาวน์โหลด package ใหม่ตอน install ครั้งถัดไป"),
    ("pip Cache", "safe", "ปลอดภัย — pip จะดาวน์โหลด package ใหม่ตอนติดตั้งครั้งถัดไป"),
    ("Discord Cache", "low", "Discord โหลดรูป/สติกเกอร์ช้าลงชั่วคราว ไม่กระทบการล็อกอิน"),
    ("Slack Cache", "low", "Slack โหลดรูป/ไฟล์แนบช้าลงชั่วคราว ไม่กระทบการล็อกอิน"),
    ("Spotify Cache", "low", "เพลงที่เคยฟังจะโหลดใหม่จากอินเทอร์เน็ตอีกครั้ง ไม่กระทบเพลย์ลิสต์"),
    ("VS Code Cache", "safe", "ปลอดภัย — VS Code จะสร้างแคชใหม่เองตอนเปิดครั้งถัดไป"),
    ("JetBrains Cache", "medium", "ระวัง — IDE อาจ re-index โปรเจกต์ใหม่ตอนเปิดครั้งถัดไป อาจใช้เวลาสักครู่"),
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
        ("Windows Error Reports",
         os.path.join(env.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "WER")),
        ("Thumbnail Cache",
         os.path.join(env.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Explorer")),
    ]
    candidates += _browser_profile_caches(env)
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
        candidates += _expand_app_cache_targets(env)
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


def _browser_profile_caches(env):
    """Cache folders for every Chrome/Edge profile, not just "Default"
    (people with work + personal profiles were only getting one cleaned)."""
    local = env.get("LOCALAPPDATA", "")
    out = []
    for name, base in (("Chrome Cache", os.path.join(local, "Google", "Chrome", "User Data")),
                       ("Edge Cache", os.path.join(local, "Microsoft", "Edge", "User Data"))):
        for profile in sorted(glob.glob(os.path.join(base, "*"))):
            prof = os.path.basename(profile)
            if prof != "Default" and not prof.startswith("Profile "):
                continue
            suffix = "" if prof == "Default" else f" ({prof})"
            for sub in ("Cache", "Code Cache", "GPUCache"):
                label = name if sub == "Cache" else f"{name} – {sub}"
                out.append((label + suffix, os.path.join(profile, sub)))
    return out


def _expand_app_cache_targets(env):
    """Package-manager and Chromium-based desktop-app caches -- another
    category of "deep clean" folders that routinely grow into multiple GB
    but aren't covered by the standard temp/browser targets above.
    """
    local = env.get("LOCALAPPDATA", "")
    appdata = env.get("APPDATA", "")

    fixed = [
        ("npm Cache", os.path.join(appdata, "npm-cache")),
        ("Yarn Cache", os.path.join(local, "Yarn", "Cache")),
        ("pip Cache", os.path.join(local, "pip", "Cache")),
        ("Discord Cache", os.path.join(appdata, "discord", "Cache")),
        ("Slack Cache", os.path.join(appdata, "Slack", "Cache")),
        ("Spotify Cache", os.path.join(local, "Spotify", "Storage")),
        ("VS Code Cache", os.path.join(appdata, "Code", "Cache")),
    ]
    out = [(label, path) for label, path in fixed]

    for m in glob.glob(os.path.join(local, "JetBrains", "*", "caches")):
        suffix = f" ({os.path.basename(os.path.dirname(m))})"
        out.append(("JetBrains Cache" + suffix, m))

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


def scan(deep=False, on_progress=None):
    """Return a list of {label, path, size, risk, note} for non-empty targets.

    Targets are measured concurrently (dir_size is I/O-bound and releases the
    GIL during syscalls) instead of one at a time -- with a dozen-plus deep
    targets, several of which are slow multi-thousand-file caches, scanning
    them serially means the slowest folder gates every other one instead of
    overlapping with them.

    on_progress(label), if given, is called as each target finishes -- lets
    the UI show which folder was just measured instead of a static
    "scanning..." with no feedback during a slow folder.
    """
    targets = get_targets(deep=deep)
    found = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_target = {executor.submit(dir_size, path): (label, path) for label, path in targets}
        for future in concurrent.futures.as_completed(future_to_target):
            label, path = future_to_target[future]
            if on_progress:
                on_progress(label)
            size = future.result()
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
# Single instance
# ---------------------------------------------------------------------------
_ERROR_ALREADY_EXISTS = 183


def acquire_single_instance(name):
    """Return a mutex handle if we're the only holder of `name`, else None.

    Keep the handle alive for the process lifetime; Windows releases it on exit.
    """
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    handle = kernel32.CreateMutexW(None, False, "Local\\" + name)
    if not handle:
        return None
    if kernel32.GetLastError() == _ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        return None
    return handle


def focus_existing_window(title="PC Cleaner"):
    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, title)
    if hwnd:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
    return bool(hwnd)


# ---------------------------------------------------------------------------
# Safety Vault
# ---------------------------------------------------------------------------
VAULT_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "PCCleanerVault")
VAULT_INDEX_PATH = os.path.join(VAULT_DIR, "index.json")
VAULT_RETENTION_DAYS = 14


_vault_thread_lock = threading.RLock()
_vault_lock_depth = 0


@contextlib.contextmanager
def _vault_locked(timeout=30):
    """Serialize every read-modify-write of the vault index.

    The window app, its background purge thread, and the headless
    --auto-clean process all touch index.json; without this two writers
    can silently drop each other's entries. RLock covers threads in this
    process, an msvcrt byte lock on index.json.lock covers other processes.
    Re-entrant, so helpers can nest.
    """
    global _vault_lock_depth
    with _vault_thread_lock:
        fh = None
        if _vault_lock_depth == 0:
            os.makedirs(VAULT_DIR, exist_ok=True)
            fh = open(VAULT_INDEX_PATH + ".lock", "a+b")
            deadline = time.monotonic() + timeout
            while True:
                try:
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        fh.close()
                        raise TimeoutError("vault index is locked by another process")
                    time.sleep(0.1)
        _vault_lock_depth += 1
        try:
            yield
        finally:
            _vault_lock_depth -= 1
            if fh is not None:
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                fh.close()


def _load_vault_index():
    if not os.path.isfile(VAULT_INDEX_PATH):
        return []
    try:
        with open(VAULT_INDEX_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except ValueError:
        # Keep the damaged file instead of letting the next save overwrite it.
        backup = f"{VAULT_INDEX_PATH}.corrupt-{datetime.now():%Y%m%d_%H%M%S}"
        try:
            os.replace(VAULT_INDEX_PATH, backup)
            log.error("Vault index was corrupt; moved to %s", backup)
        except OSError:
            pass
        return []
    except OSError:
        return []


def _save_vault_index(entries):
    """Atomic write: a crash mid-save leaves the previous index intact."""
    os.makedirs(VAULT_DIR, exist_ok=True)
    tmp = VAULT_INDEX_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, VAULT_INDEX_PATH)


def vault_list():
    with _vault_locked():
        return sorted(_load_vault_index(), key=lambda e: e["deleted_at"], reverse=True)


def _move_to_vault_no_index(original_path, batch_id, label):
    """Move a file/folder into the vault and build its index entry, without
    touching the index file. Callers that move many items in one batch
    (clean_items) use this and write the index once at the end instead of
    once per item -- reading + rewriting the whole JSON index per file turns
    an N-file clean into an O(N^2) operation, which is painfully slow once a
    cache folder has tens of thousands of small files.
    """
    os.makedirs(os.path.join(VAULT_DIR, batch_id), exist_ok=True)
    size = os.path.getsize(original_path) if os.path.isfile(original_path) else dir_size(original_path)
    vault_name = f"{uuid.uuid4().hex}_{os.path.basename(original_path)}"
    vault_path = os.path.join(VAULT_DIR, batch_id, vault_name)
    shutil.move(original_path, vault_path)

    return {
        "id": uuid.uuid4().hex,
        "label": label,
        "original_path": original_path,
        "vault_path": vault_path,
        "size": size,
        "deleted_at": datetime.now().isoformat(),
    }


def move_to_vault(original_path, batch_id, label):
    with _vault_locked():
        entry = _move_to_vault_no_index(original_path, batch_id, label)
        entries = _load_vault_index()
        entries.append(entry)
        _save_vault_index(entries)
        return entry


def restore_from_vault(entry_id):
    with _vault_locked():
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
    with _vault_locked():
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
                log.warning("Failed to remove vault file %s", match["vault_path"], exc_info=True)
        entries.remove(match)
        _save_vault_index(entries)


def purge_expired_vault_entries():
    """Drop entries older than the retention window. The index is updated
    under the lock; the (possibly slow) file deletion happens after release
    so a big purge never blocks the UI or Auto Clean."""
    cutoff = datetime.now() - timedelta(days=VAULT_RETENTION_DAYS)
    with _vault_locked():
        still_valid, expired = [], []
        for entry in _load_vault_index():
            try:
                old = datetime.fromisoformat(entry["deleted_at"]) < cutoff
            except (KeyError, ValueError):
                old = False
            (expired if old else still_valid).append(entry)
        if expired:
            _save_vault_index(still_valid)
    for entry in expired:
        path = entry["vault_path"]
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        elif os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                log.warning("Failed to remove expired vault entry %s", path, exc_info=True)
    return still_valid


clean_progress = {"done": 0, "total": 0}


def record_clean_history(kind, items, freed):
    """One history row per clean; per-target rows use the scan-time size
    estimate (the vault index holds the exact per-file sizes)."""
    scan_id = history_db.record_scan(kind, 0, len(items), freed)
    for it in items:
        history_db.record_cleaned_item(scan_id, it["label"], it["path"], it.get("size", 0))


def open_storage_cleanup():
    """Windows.old / previous installs are owned by TrustedInstaller and are
    tens of GB -- moving them into our 14-day vault would free nothing. Hand
    off to Windows' own Storage Sense "Temporary files" page instead."""
    try:
        os.startfile("ms-settings:storagesense")
        return True
    except OSError:
        return False


def windows_old_present():
    return os.path.isdir(os.path.join(os.environ.get("SystemDrive", "C:") + os.sep, "Windows.old"))


def clean_history(limit=10):
    return {"stats": history_db.get_stats(), "recent": history_db.get_recent_scans(limit)}


def clean_items(selected):
    """Move the contents of each selected target folder into the vault.

    `selected` is a list of {label, path} dicts (as sent from the UI).
    Returns (freed_bytes, errors, batch_id).
    """
    errors = []
    freed = 0
    new_entries = []
    batch_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    
    MOVEFILE_DELAY_UNTIL_REBOOT = 0x4
    kernel32 = ctypes.windll.kernel32

    def _process_file(full_path, label):
        try:
            return _move_to_vault_no_index(full_path, batch_id, label), None
        except PermissionError:
            # Schedule for deletion on reboot if locked
            success = kernel32.MoveFileExW(full_path, None, MOVEFILE_DELAY_UNTIL_REBOOT)
            if success:
                return None, f"Scheduled for deletion on reboot: {full_path}"
            return None, f"Locked and cannot be scheduled: {full_path}"
        except OSError as e:
            return None, f"{full_path}: {e}"

    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        for it in selected:
            path = it["path"]
            if not os.path.isdir(path):
                continue
            try:
                for entry in os.listdir(path):
                    full = os.path.join(path, entry)
                    tasks.append(executor.submit(_process_file, full, it["label"]))
            except OSError:
                continue

        clean_progress.update(done=0, total=len(tasks))
        for future in concurrent.futures.as_completed(tasks):
            clean_progress["done"] += 1
            vault_entry, err = future.result()
            if vault_entry:
                new_entries.append(vault_entry)
                freed += vault_entry["size"]
            if err:
                log.warning(err)
                errors.append(err)

    if new_entries:
        with _vault_locked():
            entries = _load_vault_index()
            entries.extend(new_entries)
            _save_vault_index(entries)

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
# Auto Clean — recurring background clean via a native Windows Scheduled
# Task, so it keeps running even when the app window is closed. The task
# re-launches this same app with an --auto-clean flag (see app_web.py),
# which runs headlessly (no window) and exits.
#
# Auto-run only ever touches risk == "safe" targets. Anything the app itself
# flags as "low"/"medium"/"high" impact needs a human looking at the list,
# so those are left for the user to clear manually in the normal scan UI.
# ---------------------------------------------------------------------------
AUTO_CLEAN_TASK_NAME = "PCCleaner_AutoClean"
AUTO_CLEAN_SETTINGS_PATH = os.path.join(VAULT_DIR, "auto_clean_settings.json")
AUTO_CLEAN_LOG_PATH = os.path.join(VAULT_DIR, "auto_clean_log.json")


def _load_json(path, default):
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _auto_clean_launch_command():
    """Build the command line the Scheduled Task should run to re-launch
    this app headlessly. Handles both the frozen PyInstaller exe (normal
    install) and running straight from source (dev).
    """
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --auto-clean'

    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_web.py")
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    interpreter = pythonw if os.path.isfile(pythonw) else sys.executable
    return f'"{interpreter}" "{script}" --auto-clean'


def run_auto_clean(deep=False):
    """Scan and clean only "safe"-impact targets, then record the result to
    the auto-clean log. Called both from the scheduled headless run and
    (optionally) as an on-demand "run now" from the UI.
    """
    found = scan(deep=deep)
    safe_items = [it for it in found if it["risk"] == "safe"]
    review_bytes = sum(it["size"] for it in found if it["risk"] != "safe")
    freed, errors, _batch_id = clean_items(safe_items) if safe_items else (0, [], None)
    if safe_items:
        record_clean_history("auto", safe_items, freed)

    entry = {
        "ran_at": datetime.now().isoformat(),
        "deep": deep,
        "items_cleaned": len(safe_items),
        "freed": freed,
        "freed_human": human_size(freed),
        "errors": errors,
        "review_bytes": review_bytes,
        "review_human": human_size(review_bytes),
    }
    _save_json(AUTO_CLEAN_LOG_PATH, entry)
    return entry


JUNK_NOTIFY_BYTES = 1024 ** 3  # 1 GB of junk Auto Clean isn't allowed to touch
JUNK_NOTIFY_EVERY = timedelta(hours=24)


def should_notify_junk(entry):
    """True at most once a day, when non-safe junk worth reviewing piles up."""
    if entry.get("review_bytes", 0) < JUNK_NOTIFY_BYTES:
        return False
    settings = auto_clean_settings()
    last = settings.get("last_junk_notice")
    if last and datetime.now() - datetime.fromisoformat(last) < JUNK_NOTIFY_EVERY:
        return False
    settings["last_junk_notice"] = datetime.now().isoformat()
    _save_json(AUTO_CLEAN_SETTINGS_PATH, settings)
    return True


def auto_clean_last_run():
    return _load_json(AUTO_CLEAN_LOG_PATH, None)


def auto_clean_settings():
    return _load_json(AUTO_CLEAN_SETTINGS_PATH, {"enabled": False, "interval_hours": 1, "deep": False})


def auto_clean_task_exists():
    try:
        result = subprocess.run(
            ["schtasks", "/query", "/tn", AUTO_CLEAN_TASK_NAME],
            capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def auto_clean_status():
    settings = auto_clean_settings()
    settings["task_active"] = auto_clean_task_exists()
    settings["last_run"] = auto_clean_last_run()
    return settings


def auto_clean_enable(interval_hours=1, deep=False):
    """Register (or update) the hourly-by-default Scheduled Task.

    /rl highest matches this app's own uac_admin manifest -- without it the
    task would run at standard rights and silently fail to touch anything
    under C:\\Windows.
    """
    interval_hours = max(1, min(24, int(interval_hours)))
    command = _auto_clean_launch_command()
    if deep:
        command += " --deep"
    try:
        subprocess.run(
            ["schtasks", "/create", "/tn", AUTO_CLEAN_TASK_NAME, "/tr", command,
             "/sc", "hourly", "/mo", str(interval_hours), "/rl", "highest", "/f"],
            capture_output=True, text=True, timeout=15, check=True,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False, "สร้าง Scheduled Task ไม่สำเร็จ — ต้องรันโปรแกรมแบบ Administrator"

    _save_json(AUTO_CLEAN_SETTINGS_PATH, {
        "enabled": True, "interval_hours": interval_hours, "deep": deep,
    })
    return True, ""


def auto_clean_disable():
    try:
        subprocess.run(
            ["schtasks", "/delete", "/tn", AUTO_CLEAN_TASK_NAME, "/f"],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass

    settings = auto_clean_settings()
    settings["enabled"] = False
    _save_json(AUTO_CLEAN_SETTINGS_PATH, settings)
    return True


# Re-export the system tools that used to live here (see system_tools.py).
from system_tools import (  # noqa: E402,F401
    CARD_RE,
    GAME_MODE_EXCLUDE,
    MAX_FILE_BYTES,
    MAX_SCAN_FILES,
    PASSWORD_RE,
    PROCESS_SUSPEND_RESUME,
    RUN_KEY_ROOTS,
    STARTUP_BACKUP_DIR,
    STARTUP_BACKUP_INDEX,
    TEXT_EXTENSIONS,
    THAI_ID_RE,
    UNINSTALL_ROOTS,
    _delayed_task_names,
    _load_startup_backup,
    _luhn_valid,
    _mask,
    _parse_wmi_date,
    _read_reg_value,
    _save_startup_backup,
    _startup_folders,
    _suspended_pids,
    _valid_thai_id,
    add_context_menu,
    check_driver_updates,
    delay_startup_item,
    disable_game_mode,
    disable_startup_item,
    enable_game_mode,
    enable_startup_item,
    is_game_mode_active,
    list_drivers,
    list_freezable_processes,
    list_installed_apps,
    list_startup_items,
    network_flush,
    open_windows_update,
    remove_context_menu,
    scan_large_files,
    scan_sensitive_data,
    shred_file,
    undo_delay_startup_item,
    uninstall_app,
    update_software_winget,
)
