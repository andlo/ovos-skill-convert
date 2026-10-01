"""In de/es/fr/nl/pt convert.intent's {quantity} also takes the "that" of a
follow-up ("wie viele pfund sind das" -> quantity "das"), so padatious can
send a follow-up to handle_convert. It must then answer as convert_last
does, not "unit not understood". Found by the golden utterance run."""
import time
from unittest.mock import MagicMock

import pytest
from ovos_bus_client.message import Message


@pytest.fixture
def follow(skill, monkeypatch):
    skill.speak_dialog = MagicMock()
    skill._speak_conversion = MagicMock()
    skill._last_quantity = {"value": 5.0, "unit": "kilogram", "raw_unit": "kilogramm",
                            "timestamp": time.monotonic()}
    return skill


@pytest.mark.parametrize("lang,quantity,to_unit", [
    ("de-de", "das", "zoll"),
    ("fr-fr", "ça", "pouce"),
    ("fr-fr", "qu'est-ce que c'est", "pouce"),
    ("pt-pt", "isso", "polegada"),
    ("nl-nl", "dat", "inch"),
    ("es-es", "eso", "pulgada"),
])
def test_a_that_quantity_converts_the_last_one(follow, monkeypatch, lang, quantity, to_unit):
    monkeypatch.setattr(type(follow), "lang", lang, raising=False)
    follow.handle_convert(Message("x", {"quantity": quantity, "to_unit": to_unit}))
    follow._speak_conversion.assert_called_once()
    assert follow._speak_conversion.call_args.args[0] == 5.0


def test_without_a_recent_conversion_it_is_still_not_understood(follow):
    follow._last_quantity = None
    follow.handle_convert(Message("x", {"quantity": "banana", "to_unit": "feet"}))
    follow.speak_dialog.assert_called_once_with("unit_not_understood")


def test_a_real_quantity_is_not_taken_for_that(follow):
    follow.handle_convert(Message("x", {"quantity": "10 meters", "to_unit": "feet"}))
    assert follow._speak_conversion.call_args.args[0] == 10.0
