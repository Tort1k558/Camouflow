"""Single source of truth for the application version.

Keep in sync with the GitHub release tag: CHANGELOG.md documents each bump,
camouflow.spec embeds it into the Windows version resource, and the QML shell
shows it in the window title.
"""

from __future__ import annotations

APP_VERSION = "0.3.1"
