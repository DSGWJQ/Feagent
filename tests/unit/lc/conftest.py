from __future__ import annotations

import importlib.util

import pytest

if importlib.util.find_spec("src.lc") is None:
    pytest.skip(
        "src.lc is not present in this repository; skipping legacy lc unit tests",
        allow_module_level=True,
    )
