"""Shared pytest fixtures for the unit converter skill test suite."""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_INIT_PATH = Path(__file__).resolve().parents[1] / "__init__.py"
_spec = importlib.util.spec_from_file_location("convert_skill", _INIT_PATH)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

UnitConverter = _module.UnitConverter
UREG = _module.UREG


@pytest.fixture
def skill(monkeypatch):
    s = UnitConverter.__new__(UnitConverter)
    s.log = MagicMock()
    s.skill_id = "ovos-skill-convert.test"
    s.status = MagicMock()
    s._bus = MagicMock()
    s._settings = {}
    monkeypatch.setattr(UnitConverter, "lang", "en-us", raising=False)
    s.res_dir = str(Path(__file__).resolve().parents[1])  # repo root, holds locale/
    s._lang_resources = {}  # OVOSSkill.resources' internal per-language cache
    return s
