"""End-to-end conversion math sanity checks, using the same pint
UnitRegistry instance the skill itself uses (imported via the
conftest module-loading trick, not a normal package import)."""
import importlib.util
from pathlib import Path

import pint
import pytest

_INIT_PATH = Path(__file__).resolve().parents[1] / "__init__.py"
_spec = importlib.util.spec_from_file_location("convert_skill_math", _INIT_PATH)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

UREG = _module.UREG


def test_length_conversion_cm_to_m():
    result = (250 * UREG("cm")).to("m")
    assert round(result.magnitude, 2) == 2.5


def test_length_conversion_ft_to_m():
    result = (1 * UREG("ft")).to("m")
    assert round(result.magnitude, 4) == 0.3048


def test_length_conversion_incompatible_dimensions_raises():
    with pytest.raises(pint.errors.DimensionalityError):
        (1 * UREG("m")).to("kg")
