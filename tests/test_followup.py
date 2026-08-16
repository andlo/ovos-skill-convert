"""Tests for the 'what is that in X' follow-up conversion feature:
text scanning (_find_last_quantity_in_text), localized number parsing,
and the context-expiry logic in handle_convert_last()."""
import importlib.util
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_INIT_PATH = Path(__file__).resolve().parents[1] / "__init__.py"
_spec = importlib.util.spec_from_file_location("convert_skill_followup", _INIT_PATH)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

CONTEXT_TTL_SECONDS = _module.CONTEXT_TTL_SECONDS


def test_finds_number_and_unit_in_english_sentence(skill):
    found = skill._find_last_quantity_in_text(
        "the distance to the moon is 52,000 kilometers", "en-us")
    assert found == (52000.0, "km", "kilometers")


def test_finds_number_and_unit_in_danish_sentence(skill):
    found = skill._find_last_quantity_in_text(
        "afstanden til m\u00e5nen er 52.000 kilometer", "da-dk")
    assert found == (52000.0, "km", "kilometer")


def test_multi_number_sentence_picks_the_last_recognized_pair(skill):
    """Deliberate 'last pair wins' rule - see module docstring."""
    found = skill._find_last_quantity_in_text(
        "the moon is 384400 km away and weighs 5000 kg", "en-us")
    assert found == (5000.0, "kg", "kg")


def test_number_without_a_recognized_unit_returns_none(skill):
    assert skill._find_last_quantity_in_text("the answer is 42", "en-us") is None


def test_sentence_without_any_number_returns_none(skill):
    assert skill._find_last_quantity_in_text("hello there", "en-us") is None


def test_own_conversion_result_dialog_is_itself_scannable(skill):
    """Deliberately not excluded - this is what lets someone chain a
    second follow-up conversion off this skill's own result."""
    found = skill._find_last_quantity_in_text(
        "10 centimeters is 0.1 meters", "en-us")
    assert found == (0.1, "m", "meters")


def test_parse_localized_number_english_thousands_comma(skill):
    assert skill._parse_localized_number("52,000", "en-us") == 52000.0


def test_parse_localized_number_danish_thousands_period(skill):
    assert skill._parse_localized_number("52.000", "da-dk") == 52000.0


def test_parse_localized_number_danish_decimal_comma(skill):
    assert skill._parse_localized_number("1,5", "da-dk") == 1.5


def test_handle_speak_event_stores_context(skill):
    skill.speak_dialog = MagicMock()
    message = MagicMock()
    message.data = {"utterance": "it weighs 10 kilograms", "lang": "en-us"}
    skill.handle_speak_event(message)
    assert skill._last_quantity is not None
    assert skill._last_quantity["value"] == 10.0
    assert skill._last_quantity["unit"] == "kg"


def test_handle_convert_last_with_no_context_speaks_nothing_to_convert(skill):
    skill.speak_dialog = MagicMock()
    message = MagicMock()
    message.data = {"to_unit": "meters"}
    skill.handle_convert_last(message)
    skill.speak_dialog.assert_called_once_with("nothing_to_convert")


def test_handle_convert_last_with_expired_context_speaks_nothing_to_convert(skill):
    skill.speak_dialog = MagicMock()
    skill._last_quantity = {
        "value": 10.0, "unit": "km", "raw_unit": "kilometers", "lang": "en-us",
        "timestamp": time.monotonic() - (CONTEXT_TTL_SECONDS + 5),
    }
    message = MagicMock()
    message.data = {"to_unit": "meters"}
    skill.handle_convert_last(message)
    skill.speak_dialog.assert_called_once_with("nothing_to_convert")


def test_handle_convert_last_with_fresh_context_converts(skill):
    skill.speak_dialog = MagicMock()
    skill._last_quantity = {
        "value": 10.0, "unit": "km", "raw_unit": "kilometers", "lang": "en-us",
        "timestamp": time.monotonic(),
    }
    message = MagicMock()
    message.data = {"to_unit": "meters"}
    skill.handle_convert_last(message)
    skill.speak_dialog.assert_called_once_with("conversion_result", {
        "value": 10.0, "from_unit": "kilometers", "result": 10000.0, "to_unit": "meters",
    })
