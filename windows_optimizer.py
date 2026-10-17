import subprocess
import winreg
import logging

log = logging.getLogger(__name__)

# (package name, display name, pre-checked). Apps many people actually use
# start unchecked so a careless click doesn't remove the Camera.
BLOATWARE = [
    ("Microsoft.BingNews", "Microsoft News", True),
    ("Microsoft.BingWeather", "Weather", True),
    ("Microsoft.GamingApp", "Xbox App", True),
    ("Microsoft.GetHelp", "Get Help", True),
    ("Microsoft.Getstarted", "Tips", True),
    ("Microsoft.MicrosoftOfficeHub", "Office Hub", True),
    ("Microsoft.MicrosoftSolitaireCollection", "Solitaire Collection", True),
    ("Microsoft.People", "People", True),
    ("Microsoft.SkypeApp", "Skype", True),
    ("Microsoft.windowscommunicationsapps", "Mail & Calendar", False),
    ("Microsoft.WindowsFeedbackHub", "Feedback Hub", True),
    ("Microsoft.Xbox.TCUI", "Xbox TCUI", True),
    ("Microsoft.XboxApp", "Xbox Console Companion", True),
    ("Microsoft.XboxGameOverlay", "Xbox Game Overlay", False),
    ("Microsoft.XboxGamingOverlay", "Xbox Game Bar", False),
    ("Microsoft.XboxIdentityProvider", "Xbox Identity Provider", False),
    ("Microsoft.XboxSpeechToTextOverlay", "Xbox Speech To Text", True),
    ("Microsoft.ZuneMusic", "Media Player / Groove", False),
    ("Microsoft.ZuneVideo", "Movies & TV", True),
    ("Microsoft.WindowsAlarms", "Alarms & Clock", False),
    ("Microsoft.WindowsCamera", "Camera", False),
    ("Microsoft.WindowsMaps", "Maps", False),
    ("Microsoft.WindowsSoundRecorder", "Sound Recorder", False),
    ("TikTok", "TikTok", True),
]
_KNOWN = {pkg for pkg, _, _ in BLOATWARE}


def _ps(command, timeout=60):
    return subprocess.run(["powershell", "-NoProfile", "-Command", command],
                          capture_output=True, text=True, timeout=timeout)


def list_bloatware():
    """Return only the BLOATWARE entries actually installed on this PC."""
    try:
        res = _ps("Get-AppxPackage | Select-Object -ExpandProperty Name")
        installed = set(res.stdout.split())
    except Exception as e:
        log.warning("Failed to list Appx packages: %s", e)
        return []
    return [{"package": pkg, "name": name, "checked": checked}
            for pkg, name, checked in BLOATWARE if pkg in installed]


def create_restore_point():
    """Best effort. Fails if System Protection is off; Windows also silently
    skips it if another restore point was made in the last 24h."""
    try:
        res = _ps('Checkpoint-Computer -Description "PC Cleaner Debloat" '
                  '-RestorePointType MODIFY_SETTINGS -WarningAction Stop', timeout=180)
        if res.returncode == 0:
            return True, "สร้าง restore point แล้ว"
        return False, "สร้าง restore point ไม่ได้ (System Protection อาจปิดอยู่ หรือเพิ่งสร้างไปภายใน 24 ชม.)"
    except Exception as e:
        return False, f"สร้าง restore point ไม่ได้: {e}"


def remove_bloatware(packages):
    """Remove the selected packages. Names come from the UI, so anything not
    in our own list is rejected before it gets near a PowerShell command."""
    results = []
    for pkg in packages:
        if pkg not in _KNOWN:
            results.append({"app": pkg, "success": False, "error": "not allowed"})
            continue
        try:
            res = _ps(f"Get-AppxPackage -Name '{pkg}' | Remove-AppxPackage", timeout=60)
            results.append({"app": pkg, "success": res.returncode == 0})
        except Exception as e:
            results.append({"app": pkg, "success": False, "error": str(e)})
    return results

def disable_telemetry():
    results = []
    
    # 1. Disable AllowTelemetry in Registry
    try:
        key_path = r"SOFTWARE\Policies\Microsoft\Windows\DataCollection"
        with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            winreg.SetValueEx(key, "AllowTelemetry", 0, winreg.REG_DWORD, 0)
        results.append({"task": "Disable AllowTelemetry", "success": True})
    except Exception as e:
        results.append({"task": "Disable AllowTelemetry", "success": False, "error": str(e)})

    # 2. Disable DiagTrack service
    try:
        res = subprocess.run(["sc", "config", "DiagTrack", "start=", "disabled"], capture_output=True, text=True)
        res2 = subprocess.run(["sc", "stop", "DiagTrack"], capture_output=True, text=True)
        results.append({"task": "Disable DiagTrack Service", "success": res.returncode == 0 and res2.returncode in (0, 1062)})  # 1062 = already stopped
    except Exception as e:
        results.append({"task": "Disable DiagTrack Service", "success": False, "error": str(e)})
        
    return results

def clean_registry():
    # Clears MuiCache only: Windows regenerates it, so this is safe.
    key_path = r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
            names = []
            i = 0
            while True:
                try:
                    names.append(winreg.EnumValue(key, i)[0])
                    i += 1
                except OSError:
                    break
            for n in names:
                winreg.DeleteValue(key, n)
        return {"success": True, "message": f"Cleared {len(names)} MuiCache entries."}
    except Exception as e:
        return {"success": False, "message": str(e)}
