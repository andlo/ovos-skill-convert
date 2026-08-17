"""Tests for the Common Query safety net (handle_common_query) - see
ovos-skill-geometry/ovos-skill-geography/ovos-skill-calculator's
DEVELOPMENT.md for why this exists (live-tested platform routing
gap, not hypothetical)."""


def test_common_query_meters_to_inches(skill):
    answer, confidence = skill.handle_common_query("what is 2 meters in inches", "en-us")
    assert float(answer) == 78.7402
    assert confidence == 0.8


def test_common_query_km_to_miles(skill):
    answer, confidence = skill.handle_common_query("what is 10 kilometers in miles", "en-us")
    assert float(answer) == 6.2137


def test_common_query_whats_contraction_form(skill):
    answer, confidence = skill.handle_common_query("what's 5 pounds in kilograms", "en-us")
    assert float(answer) == 2.268


def test_common_query_incompatible_dimensions_returns_none(skill):
    assert skill.handle_common_query("what is 5 meters in kilograms", "en-us") is None


def test_common_query_unresolvable_unit_returns_none(skill):
    assert skill.handle_common_query("what is 5 zorkles in inches", "en-us") is None


def test_common_query_non_matching_phrase_returns_none(skill):
    assert skill.handle_common_query("play some music", "en-us") is None


def test_common_query_danish(skill):
    answer, confidence = skill.handle_common_query("hvad er 2 meter i tommer", "da-dk")
    assert float(answer) == 78.7402


def test_common_query_does_not_match_convert_last_phrasing(skill):
    """'what is that in X' depends on mutable per-instance state and
    is deliberately NOT covered by the safety net - see the module
    docstring's Common Query section."""
    assert skill.handle_common_query("what is that in inches", "en-us") is None


def test_common_query_does_not_match_imperative_convert_phrasing(skill):
    """'convert X to Y' isn't question-shaped, so it's not a
    plausible misrouting target and isn't covered."""
    assert skill.handle_common_query("convert 2 meters to inches", "en-us") is None
