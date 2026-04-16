"""Shared test helpers for scripts/ tests.

Provides a pytest fixture that loads count-tokens.py by file path,
since the hyphenated filename blocks ordinary `import count_tokens`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT_PATH = Path(__file__).parent / "count-tokens.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("count_tokens", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def count_tokens():
    """Load count-tokens.py as an importable module."""
    return _load()
