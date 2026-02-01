from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = ["BrowserInterface", "SharedVarsManager"]

if TYPE_CHECKING:
    from .browser_interface import BrowserInterface
    from .shared_vars import SharedVarsManager


def __getattr__(name: str):
    if name == "BrowserInterface":
        from .browser_interface import BrowserInterface as value

        return value
    if name == "SharedVarsManager":
        from .shared_vars import SharedVarsManager as value

        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(list(globals().keys()) + __all__)
