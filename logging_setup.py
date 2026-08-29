"""Shared logging setup for PC Cleaner.

Writes rotating log files to %LOCALAPPDATA%\\PCCleaner\\logs so failures that
were previously silently swallowed (bare ``except: pass``) are recorded for
troubleshooting, without printing noise to the console in the packaged app.
"""

import logging
import logging.handlers
import os

_LOG_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "PCCleaner", "logs"
)
_LOG_FILE = os.path.join(_LOG_DIR, "pccleaner.log")

_configured = False


def get_logger(name="pccleaner"):
    """Return a module-level logger, configuring the root handler once."""
    global _configured
    if not _configured:
        try:
            os.makedirs(_LOG_DIR, exist_ok=True)
            handler = logging.handlers.RotatingFileHandler(
                _LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
            )
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
            )
            root = logging.getLogger("pccleaner")
            root.setLevel(logging.INFO)
            root.addHandler(handler)
        except OSError:
            # Can't write logs (e.g. read-only profile) — fall back to a
            # null handler so logging calls elsewhere never raise.
            logging.getLogger("pccleaner").addHandler(logging.NullHandler())
        _configured = True
    return logging.getLogger(name)
