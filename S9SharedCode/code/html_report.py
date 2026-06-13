"""Thin wrapper so assignment scripts can import the replay report generator."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from replay_viewer import (  # noqa: E402
    build_report,
    build_session_index,
    count_interactive_browser_actions,
    load_session,
    write_report,
)

__all__ = [
    "build_report",
    "build_session_index",
    "count_interactive_browser_actions",
    "load_session",
    "write_report",
]


def main() -> None:
    import replay_viewer

    replay_viewer.main()


if __name__ == "__main__":
    main()
