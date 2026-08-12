"""Read-only system telemetry for the Remote Assistance panel.

Everything here is a snapshot read -- no mutation of system state.
"""

import shutil
import subprocess
import time

import psutil

_last_disk_check = 0.0
_disk_cache = None


def snapshot():
    cpu = psutil.cpu_percent(interval=0.2)
    vm = psutil.virtual_memory()
    disk = shutil.disk_usage("C:\\")
    procs = sorted(
        (
            {"pid": p.pid, "name": p.info["name"], "memory": p.info["memory_info"].rss if p.info["memory_info"] else 0}
            for p in psutil.process_iter(["name", "memory_info"])
        ),
        key=lambda p: p["memory"],
        reverse=True,
    )[:15]
    return {
        "cpu_percent": cpu,
        "ram": {"total": vm.total, "used": vm.used, "percent": vm.percent},
        "disk": {"total": disk.total, "used": disk.used, "free": disk.free},
        "gpu": _gpu_snapshot(),
        "top_processes": procs,
        "timestamp": time.time(),
    }


def _gpu_snapshot():
    """Best-effort NVIDIA GPU stats via nvidia-smi; omitted if unavailable."""
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return None
        util, mem_used, mem_total, temp = [x.strip() for x in out.stdout.strip().splitlines()[0].split(",")]
        return {
            "util_percent": float(util),
            "memory_used_mb": float(mem_used),
            "memory_total_mb": float(mem_total),
            "temperature_c": float(temp),
        }
    except Exception:
        return None


def diagnostic_report(max_entries=30):
    """Pull recent Application/System error & critical events from the
    Windows Event Log. Read-only; requires no elevation for the standard
    log channels used here.
    """
    try:
        import win32evtlog
        import win32evtlogutil
    except ImportError:
        return {"available": False, "reason": "pywin32 not available", "entries": []}

    entries = []
    for channel in ("Application", "System"):
        try:
            handle = win32evtlog.OpenEventLog(None, channel)
            flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
            count = 0
            while count < max_entries // 2:
                records = win32evtlog.ReadEventLog(handle, flags, 0)
                if not records:
                    break
                for rec in records:
                    if rec.EventType not in (
                        win32evtlog.EVENTLOG_ERROR_TYPE,
                        win32evtlog.EVENTLOG_WARNING_TYPE,
                    ):
                        continue
                    try:
                        message = win32evtlogutil.SafeFormatMessage(rec, channel)
                    except Exception:
                        message = "(no message)"
                    entries.append(
                        {
                            "channel": channel,
                            "source": rec.SourceName,
                            "event_id": rec.EventID & 0xFFFF,
                            "type": "error" if rec.EventType == win32evtlog.EVENTLOG_ERROR_TYPE else "warning",
                            "time": rec.TimeGenerated.Format(),
                            "message": message[:500],
                        }
                    )
                    count += 1
                    if count >= max_entries // 2:
                        break
            win32evtlog.CloseEventLog(handle)
        except Exception as exc:
            entries.append({"channel": channel, "source": "diagnostic_report", "event_id": 0, "type": "error", "time": "", "message": f"Could not read {channel} log: {exc}"})

    entries.sort(key=lambda e: e.get("time", ""), reverse=True)
    return {"available": True, "entries": entries[:max_entries]}
