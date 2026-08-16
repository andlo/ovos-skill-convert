"""Basic conversion + unit-resolution tests for the length category -
the only category implemented in this initial scaffold."""
import pytest


def test_resolve_unit_exact_alias(skill):
    assert skill._resolve_unit("centimeters", "en-us") == "cm"
    assert skill._resolve_unit("feet", "en-us") == "ft"


def test_resolve_unit_danish_alias(skill):
    assert skill._resolve_unit("meter", "da-dk") == "m"
    assert skill._resolve_unit("fod", "da-dk") == "ft"


def test_resolve_unit_danish_mile_not_mapped(skill):
    """Scandinavian 'mil' (10 km) is deliberately NOT in the alias
    table - see module docstring in __init__.py. It should NOT
    silently resolve to the English 'mi' (mile)."""
    assert skill._resolve_unit("mil", "da-dk") != "mi"


def test_resolve_unit_unknown_returns_none(skill):
    assert skill._resolve_unit("banana", "en-us") is None


def test_resolve_unit_empty_returns_none(skill):
    assert skill._resolve_unit("", "en-us") is None
    assert skill._resolve_unit(None, "en-us") is None
