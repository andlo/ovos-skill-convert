"""Unit-resolution tests across all implemented categories, with
particular focus on the deliberate false-friend traps and collision
avoidance decisions documented in __init__.py."""
import pytest


def test_resolve_unit_exact_alias(skill):
    assert skill._resolve_unit("centimeters", "en-us") == "cm"
    assert skill._resolve_unit("feet", "en-us") == "ft"


def test_resolve_unit_danish_alias(skill):
    assert skill._resolve_unit("meter", "da-dk") == "m"
    assert skill._resolve_unit("fod", "da-dk") == "ft"


def test_resolve_unit_danish_mile_not_mapped(skill):
    """Scandinavian 'mil' (10 km) is deliberately NOT in the alias
    table. It should NOT silently resolve to the English 'mi' (mile)."""
    assert skill._resolve_unit("mil", "da-dk") != "mi"


def test_resolve_unit_danish_ton_is_metric(skill):
    """Danish 'ton' means metric ton (1000 kg) in everyday speech -
    must NOT resolve to pint's bare 'ton' (US short ton, 907 kg)."""
    assert skill._resolve_unit("ton", "da-dk") == "metric_ton"


def test_resolve_unit_english_ton_is_us_short_ton(skill):
    """English bare 'ton' is the US short ton by convention - distinct
    from the Danish case above, this is the correct default for en-us."""
    assert skill._resolve_unit("ton", "en-us") == "ton"


def test_resolve_unit_danish_pund_not_mapped(skill):
    """Traditional Danish 'pund' is exactly 500 g, NOT the imperial
    pound (453.592 g) - deliberately left unmapped rather than guessed."""
    assert skill._resolve_unit("pund", "da-dk") is None


def test_resolve_unit_danish_hk_is_metric_horsepower(skill):
    """Danish 'hk'/'hestekraft' is the metric horsepower, ~1.4%
    different from pint's bare 'horsepower' (imperial/mechanical)."""
    assert skill._resolve_unit("hk", "da-dk") == "metric_horsepower"
    assert skill._resolve_unit("hestekraft", "da-dk") == "metric_horsepower"


def test_resolve_unit_mass_gram_not_confused_with_acceleration(skill):
    """'g' resolves to gram (mass), never to standard_gravity - the
    acceleration category deliberately never aliases bare 'g'."""
    assert skill._resolve_unit("g", "en-us") == "g"


def test_resolve_unit_unknown_returns_none(skill):
    assert skill._resolve_unit("banana", "en-us") is None


def test_resolve_unit_empty_returns_none(skill):
    assert skill._resolve_unit("", "en-us") is None
    assert skill._resolve_unit(None, "en-us") is None


@pytest.mark.parametrize("raw,lang,expected", [
    ("kilogram", "en-us", "kg"),
    ("celsius", "en-us", "degC"),
    ("hour", "en-us", "hour"),
    ("mile per hour", "en-us", "mph"),
    ("square meter", "en-us", "m**2"),
    ("liter", "en-us", "liter"),
    ("bushel", "en-us", "bushel"),
    ("degree", "en-us", "degree"),
    ("bar", "en-us", "bar"),
    ("newton", "en-us", "newton"),
    ("kilojoule", "en-us", "kilojoule"),
    ("kilowatt", "en-us", "kilowatt"),
    ("newton meter", "en-us", "newton*meter"),
    ("percent", "en-us", "percent"),
    ("gigabyte", "en-us", "gigabyte"),
    ("liter per minute", "en-us", "liter/minute"),
    ("kilogram", "da-dk", "kg"),
    ("time", "da-dk", "hour"),
    ("kvadratmeter", "da-dk", "m**2"),
    ("bar", "da-dk", "bar"),
    ("newton", "da-dk", "newton"),
    ("procent", "da-dk", "percent"),
    ("gigabyte", "da-dk", "gigabyte"),
])
def test_resolve_unit_across_categories(skill, raw, lang, expected):
    assert skill._resolve_unit(raw, lang) == expected
