"""Best-effort cross-platform desktop notifications (macOS osascript / Linux notify-send)."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys

logger = logging.getLogger("yt_to_obsidian.notifier")

_MACOS_APPLESCRIPT = (
    "on run argv\n"
    "  display notification (item 2 of argv) with title (item 1 of argv)\n"
    "end run\n"
)


def send_notification(title: str, message: str, *, enabled: bool = True) -> bool:
    """Send a desktop notification without ever raising on failure."""
    if not enabled:
        return False

    try:
        if sys.platform == "darwin":
            osascript = shutil.which("osascript")
            if not osascript:
                return False
            result = subprocess.run(
                [osascript, "-", title, message],
                input=_MACOS_APPLESCRIPT,
                text=True,
                capture_output=True,
                timeout=3,
                check=False,
            )
            return result.returncode == 0

        if sys.platform.startswith("linux"):
            notify_send = shutil.which("notify-send")
            if not notify_send:
                return False
            result = subprocess.run(
                [notify_send, title, message],
                capture_output=True,
                timeout=3,
                check=False,
            )
            return result.returncode == 0
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.debug("Notification failed (ignored): %s", exc)
    return False
