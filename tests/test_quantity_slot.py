"""convert.intent uses ONE {quantity} slot ('10 centimeters') instead of
'{value} {from_unit}': ovos-workshop 9.x rejects templates with two slots
next to each other, which dropped every line of convert.intent on the
alpha channel. _split_quantity() does the split instead."""
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest

LOCALE = Path(__file__).resolve().parents[1] / "locale"


@pytest.mark.parametrize("path", sorted(LOCALE.glob("*/*.intent")), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_no_intent_line_has_two_slots_next_to_each_other(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        assert not re.search(r"\}\s*\{", line), f"adjacent slots in {path}: {line!r}"


@pytest.mark.parametrize("raw,lang,expected", [
    ("10 centimeters", "en-us", (10.0, "centimeters")),
    ("2 meters", "en-us", (2.0, "meters")),
    ("100 celsius", "en-us", (100.0, "celsius")),
    ("1,000 feet", "en-us", (1000.0, "feet")),
    ("ten centimeters", "en-us", (10, "centimeters")),
    ("two and a half meters", "en-us", (2.5, "meters")),
    ("meters", "en-us", (1, "meters")),
    ("10,5 meter", "da-dk", (10.5, "meter")),
    ("ti centimeter", "da-dk", (10, "centimeter")),
])
def test_split_quantity(skill, raw, lang, expected):
    value, unit = skill._split_quantity(raw, lang)
    assert (value, unit) == expected


def test_multi_word_unit_wins_over_its_last_word(skill):
    aliases = skill._aliases_for("en-us")
    multi = next(a for a in aliases if " " in a and a.split()[-1] in aliases)
    value, unit = skill._split_quantity(f"3 {multi}", "en-us")
    assert (value, unit) == (3.0, multi)


def test_unknown_unit_keeps_the_digits_and_leaves_the_rest_for_fuzzy_matching(skill):
    assert skill._split_quantity("10 centimetres-ish", "en-us") == (10.0, "centimetres-ish")


def test_handler_converts_from_the_quantity_slot(skill, monkeypatch):
    spoken = []
    monkeypatch.setattr(skill, "_speak_conversion", lambda *a: spoken.append(a), raising=False)
    monkeypatch.setattr(skill, "speak_dialog", MagicMock(), raising=False)
    message = MagicMock(data={"quantity": "10 centimeters", "to_unit": "inches"})
    skill.handle_convert(message)
    value, from_unit, to_unit, from_raw, to_raw = spoken[0]
    assert (value, from_unit, to_unit, from_raw, to_raw) == (10.0, "cm", "in", "centimeters", "inches")
