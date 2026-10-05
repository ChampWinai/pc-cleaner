import subprocess
import winreg
import logging

log = logging.getLogger(__name__)

def remove_bloatware():
    # Remove common pre-installed Windows 10/11 bloatware
    apps_to_remove = [
        'Microsoft.BingNews', 'Microsoft.BingWeather', 'Microsoft.GamingApp', 
        'Microsoft.GetHelp', 'Microsoft.Getstarted', 'Microsoft.MicrosoftOfficeHub', 
        'Microsoft.MicrosoftSolitaireCollection', 'Microsoft.People', 
        'Microsoft.SkypeApp', 'Microsoft.WindowsAlarms', 'Microsoft.WindowsCamera',
        'Microsoft.windowscommunicationsapps', 'Microsoft.WindowsFeedbackHub', 
        'Microsoft.WindowsMaps', 'Microsoft.WindowsSoundRecorder', 
        'Microsoft.Xbox.TCUI', 'Microsoft.XboxApp', 'Microsoft.XboxGameOverlay', 
        'Microsoft.XboxGamingOverlay', 'Microsoft.XboxIdentityProvider', 
        'Microsoft.XboxSpeechToTextOverlay', 'Microsoft.ZuneMusic', 
        'Microsoft.ZuneVideo', 'TikTok'
    ]
    
    results = []
    for app in apps_to_remove:
        cmd = f'Get-AppxPackage -Name {app} | Remove-AppxPackage'
        try:
            res = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True, timeout=30)
            success = res.returncode == 0
            results.append({"app": app, "success": success})
        except Exception as e:
            results.append({"app": app, "success": False, "error": str(e)})
            
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
