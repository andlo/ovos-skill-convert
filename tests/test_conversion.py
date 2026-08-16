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


def test_temperature_uses_quantity_not_multiplication():
    """The bug this test guards against: `value * UREG(unit)` raises
    OffsetUnitCalculusError for degC/degF. UREG.Quantity() is required
    - this is exactly what handle_convert() uses."""
    result = UREG.Quantity(100, "degC").to("degF")
    assert round(result.magnitude, 2) == 212.0

    with pytest.raises(pint.errors.OffsetUnitCalculusError):
        (100 * UREG("degC")).to("degF")


def test_mass_us_ton_vs_metric_ton_are_different():
    """The core reason 'ton' needed separate en-us/da-dk handling:
    these two units genuinely differ."""
    us_ton_kg = UREG.Quantity(1, "ton").to("kg").magnitude
    metric_ton_kg = UREG.Quantity(1, "metric_ton").to("kg").magnitude
    assert round(us_ton_kg, 2) == 907.18
    assert metric_ton_kg == 1000.0
    assert us_ton_kg != metric_ton_kg


def test_power_metric_vs_imperial_horsepower_are_different():
    """The core reason Danish 'hk' needed to map to metric_horsepower
    specifically, not bare 'horsepower'."""
    hp_watts = UREG.Quantity(1, "horsepower").to("watt").magnitude
    metric_hp_watts = UREG.Quantity(1, "metric_horsepower").to("watt").magnitude
    assert round(hp_watts, 2) == 745.70
    assert round(metric_hp_watts, 2) == 735.50
    assert hp_watts != metric_hp_watts


def test_mass_ounce_and_fluid_ounce_are_different_dimensions():
    """Guards against the 'oz' vs 'fluid_ounce' ambiguity that made
    the volume category's fluid ounce entry a deliberate separate key
    rather than reusing 'ounce'."""
    oz = UREG("oz")
    fl_oz = UREG("fluid_ounce")
    assert oz.dimensionality != fl_oz.dimensionality


def test_flow_cfm_typo_would_have_been_wrong():
    """Documents why 'cubic foot per minute' is spelled out in full in
    UNIT_ALIASES rather than using the common abbreviation 'cfm' -
    pint parses 'cfm' as centi-fermi (a length unit), not a flow rate."""
    assert UREG("cfm").dimensionality == UREG("m").dimensionality
    assert UREG("ft**3/minute").dimensionality != UREG("m").dimensionality
