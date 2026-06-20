"""OS permission probes via cua-driver `check_permissions`."""
from __future__ import annotations

import platform
import sys
from typing import Any

from .client import CuaDriverClient, CuaDriverError


def _blocked_reasons(perms: dict[str, Any]) -> list[str]:
    system = platform.system().lower()
    reasons: list[str] = []
    if system == "darwin":
        if not perms.get("accessibility"):
            reasons.append("macOS Accessibility permission not granted")
        if not perms.get("screen_recording"):
            reasons.append("macOS Screen Recording permission not granted")
    elif system == "linux":
        if perms.get("wayland_enabled") and not perms.get("wayland"):
            reasons.append("Linux Wayland portal permission required")
        if not perms.get("atspi"):
            reasons.append("Linux AT-SPI (org.a11y.Bus) not reachable")
        if not perms.get("xsend_event") and not perms.get("x11"):
            reasons.append("Linux X11/XSendEvent input path unavailable")
        if not perms.get("qt_accessibility", True):
            reasons.append("QT_ACCESSIBILITY=1 required for Qt apps")
    elif system == "windows":
        if perms.get("uac_blocked"):
            reasons.append("Windows UAC elevation required")
    return reasons


async def check_preconditions(client: CuaDriverClient | None = None) -> tuple[bool, list[str]]:
    """Return (ok, reasons). When not ok, Computer skill must emit precondition_blocked."""
    cli = client or CuaDriverClient()
    try:
        perms = await cli.health_check()
    except CuaDriverError as e:
        return False, [str(e)]

    if platform.system().lower() == "linux":
        import os
        if os.environ.get("QT_ACCESSIBILITY", "").strip() not in ("1", "true", "yes"):
            perms = dict(perms)
            perms["qt_accessibility"] = False

    reasons = _blocked_reasons(perms)
    return (not reasons, reasons)
