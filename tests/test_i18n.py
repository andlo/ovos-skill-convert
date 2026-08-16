"""Sanity checks for the 6 new languages added in the machine-
translated first pass (de-de, es-es, fr-fr, it-it, nl-nl, pt-pt) - and
for the Light category (lux/foot-candle) added at the same time.

These are deliberately light-touch: one or two representative aliases
per language plus the specific false-friend traps called out in each
locale's unit_aliases.json "_notes". Full native-speaker-level
coverage (the kind da-dk has) is future work - see README."""
import pytest


def test_light_lux_resolves(skill):
    assert skill._resolve_unit("lux", "en-us") == "lux"


def test_light_foot_candle_resolves(skill):
    assert skill._resolve_unit("foot-candle", "en-us") == "foot_candle"


def test_light_lux_to_foot_candle_conversion():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "convert_skill_light", Path(__file__).resolve().parents[1] / "__init__.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    result = m.UREG.Quantity(100, "lux").to("foot_candle")
    assert round(result.magnitude, 4) == 9.2903


@pytest.mark.parametrize("raw,lang,expected", [
    ("Zentimeter", "de-de", "cm"),
    ("Tonne", "de-de", "metric_ton"),
    ("PS", "de-de", "metric_horsepower"),
    ("cent\u00edmetro", "es-es", "cm"),
    ("tonelada", "es-es", "metric_ton"),
    ("cv", "es-es", "metric_horsepower"),
    ("centim\u00e8tre", "fr-fr", "cm"),
    ("tonne", "fr-fr", "metric_ton"),
    ("octet", "fr-fr", "byte"),
    ("centimetro", "it-it", "cm"),
    ("tonnellata", "it-it", "metric_ton"),
    ("centimeter", "nl-nl", "cm"),
    ("ton", "nl-nl", "metric_ton"),
    ("pk", "nl-nl", "metric_horsepower"),
    ("cent\u00edmetro", "pt-pt", "cm"),
    ("tonelada", "pt-pt", "metric_ton"),
])
def test_new_language_core_aliases(skill, raw, lang, expected):
    assert skill._resolve_unit(raw.lower(), lang) == expected


@pytest.mark.parametrize("dangerous_word,lang", [
    ("pfund", "de-de"),      # German "pound word" = 500g, not imperial lb - omitted
    ("meile", "de-de"),      # false-friend risk, same shape as Danish "mil"
    ("libra", "es-es"),      # regional ambiguity, omitted
    ("milla", "es-es"),
    ("livre", "fr-fr"),      # French "pound word" = 500g, not imperial lb
    ("mille", "fr-fr"),      # ALSO means "thousand" in French - deliberately unmapped
    ("libbra", "it-it"),
    ("miglio", "it-it"),
    ("pond", "nl-nl"),       # Dutch "pound word" = 500g, not imperial lb
    ("mijl", "nl-nl"),
    ("libra", "pt-pt"),
    ("milha", "pt-pt"),
])
def test_flagged_false_friend_words_stay_unmapped(skill, dangerous_word, lang):
    """These words are deliberately absent from their language's
    unit_aliases.json - see that file's '_notes' key for why. This
    test guards against someone adding a guessed mapping later without
    checking the real-world value first."""
    assert skill._resolve_unit(dangerous_word, lang) is None
