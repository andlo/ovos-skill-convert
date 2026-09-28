"""Registration workarounds for the current stable ovos-padatious /
ovos-workshop - see _protect_slot_endings() and _register_unit_entities()."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

LOCALE = Path(__file__).resolve().parents[1] / "locale"


@pytest.fixture
def wired(skill, tmp_path, monkeypatch):
    service = SimpleNamespace(register_padatious_intent=MagicMock(),
                              register_padatious_entity=MagicMock())
    monkeypatch.setattr(type(skill), "intent_service", service, raising=False)
    monkeypatch.setattr(type(skill), "file_system", SimpleNamespace(path=str(tmp_path)), raising=False)
    monkeypatch.setattr(type(skill), "native_langs", ["en-US", "da-DK"], raising=False)
    return skill, service


def test_lines_ending_in_a_slot_are_padded(wired):
    skill, service = wired
    original = service.register_padatious_intent
    skill._protect_slot_endings()
    service.register_padatious_intent("x:convert.intent", str(LOCALE / "en-us" / "convert.intent"), "en-US")

    name, padded_path, lang, _ = original.call_args.args
    assert (name, lang) == ("x:convert.intent", "en-US")
    padded = Path(padded_path).read_text(encoding="utf-8").splitlines()
    source = (LOCALE / "en-us" / "convert.intent").read_text(encoding="utf-8").splitlines()
    assert len(padded) == len(source)
    for src, out in zip(source, padded):
        assert out == (f"{src} ?" if src.endswith("}") else src)
    # the files translators edit are untouched
    assert not any(line.endswith(" ?") for line in source)


def test_padded_samples_keep_their_closing_brace_after_padatious_normalisation(wired):
    import string
    skill, service = wired
    original = service.register_padatious_intent
    skill._protect_slot_endings()
    service.register_padatious_intent("x:convert.intent", str(LOCALE / "en-us" / "convert.intent"), "en-US")
    for line in Path(original.call_args.args[1]).read_text(encoding="utf-8").splitlines():
        # what ovos-padatious 1.4.3's normalize_utterances() does to each sample
        assert line.rstrip(string.punctuation).count("{") == line.count("}"), line


def test_unit_entities_registered_under_the_name_padatious_looks_up(wired):
    skill, service = wired
    skill._register_unit_entities()
    names = {(c.args[0], c.args[2]) for c in service.register_padatious_entity.call_args_list}
    assert names == {(f"{skill.skill_id}:{e}", lang)
                     for e in ("to_unit",) for lang in ("en-US", "da-DK")}
