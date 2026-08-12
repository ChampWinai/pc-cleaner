"""Whitelisted remote "fix" actions.

Deliberately NOT a generic remote-shell / script-runner: a controller can
only trigger one of the fixed actions below, each of which either calls an
existing, audited `backend.py` function or runs a hardcoded OS command with
no attacker-controlled arguments. Nothing here accepts free-form input.
"""

import subprocess

import backend

ACTIONS = {
    "trim_ram": "Trim RAM (empty working sets)",
    "empty_recycle_bin": "Empty Recycle Bin",
    "flush_dns": "Flush DNS cache",
    "restart_explorer": "Restart Windows Explorer",
    "docker_prune": "Prune Docker resources",
}


def list_actions():
    return [{"id": k, "label": v} for k, v in ACTIONS.items()]


def run_action(action_id: str) -> dict:
    if action_id not in ACTIONS:
        return {"success": False, "message": f"Unknown action: {action_id}"}

    try:
        if action_id == "trim_ram":
            before = backend.ram_status()
            trimmed, skipped = backend.trim_process_working_sets()
            after = backend.ram_status()
            freed = max(0, before["used"] - after["used"])
            return {"success": True, "message": f"Trimmed {trimmed} processes, freed {backend.human_size(freed)}"}

        if action_id == "empty_recycle_bin":
            ok = backend.empty_recycle_bin()
            return {"success": ok, "message": "Recycle Bin emptied" if ok else "Failed to empty Recycle Bin"}

        if action_id == "flush_dns":
            result = subprocess.run(
                ["ipconfig", "/flushdns"], capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return {"success": result.returncode == 0, "message": result.stdout.strip() or result.stderr.strip()}

        if action_id == "restart_explorer":
            subprocess.run(["taskkill", "/F", "/IM", "explorer.exe"], capture_output=True, timeout=10,
                            creationflags=subprocess.CREATE_NO_WINDOW)
            subprocess.Popen(["explorer.exe"])
            return {"success": True, "message": "Explorer restarted"}

        if action_id == "docker_prune":
            result = backend.docker_prune()
            return {"success": True, "message": str(result)}

    except Exception as exc:
        return {"success": False, "message": f"Action failed: {exc}"}

    return {"success": False, "message": "Not implemented"}
