"""The {to_unit} entity files must list exactly the unit
words in unit_aliases.json - they are generated from it by
scripts/make_unit_entities.py, and a stale copy would make Padatious
unsure about any unit added since."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOCALE = ROOT / "locale"
LANGS = sorted(p.name for p in LOCALE.iterdir() if (p / "unit_aliases.json").is_file())

spec = importlib.util.spec_from_file_location("make_unit_entities", ROOT / "scripts" / "make_unit_entities.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


@pytest.mark.parametrize("lang", LANGS)
@pytest.mark.parametrize("name", ["to_unit"])
def test_entity_file_matches_unit_aliases(lang, name):
    path = LOCALE / lang / f"{name}.entity"
    assert path.is_file(), f"missing {path} - run python scripts/make_unit_entities.py"
    assert path.read_text(encoding="utf-8") == gen.entity_text(LOCALE / lang), \
        f"{path} is out of date - run python scripts/make_unit_entities.py"


@pytest.mark.parametrize("lang", LANGS)
def test_never_mapped_words_are_not_entities(lang):
    import json
    data = json.loads((LOCALE / lang / "unit_aliases.json").read_text(encoding="utf-8"))
    words = set(gen.unit_words(LOCALE / lang))
    assert not words & {w.lower() for w in data.get("_never_map", [])}

