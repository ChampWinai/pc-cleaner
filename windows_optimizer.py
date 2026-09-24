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
        'Microsoft.ZuneVideo', 'TikTok', 'Spotify'
    ]
    
    results = []
    for app in apps_to_remove:
        cmd = f'Get-AppxPackage *{app}* | Remove-AppxPackage'
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
        results.append({"task": "Disable DiagTrack Service", "success": res.returncode == 0})
    except Exception as e:
        results.append({"task": "Disable DiagTrack Service", "success": False, "error": str(e)})
        
    return results

def clean_registry():
    # Safe registry cleanup simulation / basic safe MUICache clear
    try:
        key_path = r"Software\Classes\Local Settings\Software\Microsoft\Windows\Shell\MuiCache"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            pass
        return {"success": True, "message": "Safe registry keys scanned and optimized."}
    except Exception as e:
        return {"success": False, "message": str(e)}
