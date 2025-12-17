"""
Local compatibility shim for the ``watchfiles`` package.

Why this file exists:
    - ``uvicorn[standard]`` installs ``watchfiles`` and prefers it for ``--reload``.
    - On some Windows setups (esp. corporate devices / IDE terminals) the native watcher
      either cannot create the required pipes (WinError 5) or forwards spurious
      console CTRL+C events that immediately tear down the child server process.
    - By raising ``ImportError`` here we force uvicorn to fall back to the safer
      stat-based reloader on Windows while keeping the fast watcher available for
      other platforms.

Set ``AGENT_ENABLE_WATCHFILES=1`` if you really want to use the native watcher.
"""

from __future__ import annotations

import importlib.metadata as metadata
import importlib.util
import os
import sys
from types import ModuleType

_WINDOWS = os.name == "nt"
_ENABLE_NATIVE = os.environ.get("AGENT_ENABLE_WATCHFILES", "").lower() in {"1", "true", "yes"}


def _load_real_watchfiles() -> ModuleType:
    """Import the real ``watchfiles`` package from site-packages."""
    try:
        dist = metadata.distribution("watchfiles")
    except metadata.PackageNotFoundError as exc:  # pragma: no cover - safety
        raise ImportError("watchfiles package is not installed.") from exc

    package_root = None
    for file in dist.files or []:
        normalized = str(file).replace("\\", "/")
        if normalized == "watchfiles/__init__.py":
            package_root = os.path.dirname(dist.locate_file(file))
            break

    if package_root is None:
        raise ImportError("Unable to locate the installed watchfiles package.")

    init_path = os.path.join(package_root, "__init__.py")
    spec = importlib.util.spec_from_file_location("watchfiles", init_path)
    if spec is None or spec.loader is None:  # pragma: no cover - safety
        raise ImportError("Unable to load the watchfiles module from site-packages.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    sys.modules[__name__] = module
    return module


if _WINDOWS and not _ENABLE_NATIVE:
    raise ImportError(
        "watchfiles disabled on Windows to avoid Ctrl+C reloader issues. "
        "Set AGENT_ENABLE_WATCHFILES=1 to force-enable the native watcher."
    )

_module = _load_real_watchfiles()
globals().update(_module.__dict__)
