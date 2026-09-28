#!/usr/bin/env python3
"""Writes locale/<lang>/to_unit.entity from that language's
unit_aliases.json. (The unit being converted FROM is part of the
{quantity} slot - "10 centimeters" - and split by the skill itself, see
_split_quantity() - so it has no entity file.)

Why: convert.intent is almost nothing but slots ("convert {quantity}
to {to_unit}"). Without entity files Padatious has to guess
what a unit looks like from a handful of lines, and on a real install
with ~200 other intents it scored "convert 10 centimeters to inches" at
0.25 - far below the pipeline's thresholds, so it fell through to the
fallback skills. The entity files tell it exactly which words can fill
{to_unit}.

unit_aliases.json stays the single source of truth: run this after
editing it (tests/test_entities.py fails if the two drift apart).

    python scripts/make_unit_entities.py
"""
import json
from pathlib import Path

LOCALE = Path(__file__).resolve().parents[1] / "locale"
HEADER = "# generated from unit_aliases.json by scripts/make_unit_entities.py - do not edit\n"


def unit_words(lang_dir: Path) -> list:
    data = json.loads((lang_dir / "unit_aliases.json").read_text(encoding="utf-8"))
    words = set()
    for category, aliases in data.items():
        if category.startswith("_") or not isinstance(aliases, dict):
            continue
        words.update(alias.strip().lower() for alias in aliases if alias.strip())
    return sorted(words)


def entity_text(lang_dir: Path) -> str:
    return HEADER + "\n".join(unit_words(lang_dir)) + "\n"


def main() -> None:
    for lang_dir in sorted(p for p in LOCALE.iterdir() if (p / "unit_aliases.json").is_file()):
        text = entity_text(lang_dir)
        (lang_dir / "to_unit.entity").write_text(text, encoding="utf-8")
        stale = lang_dir / "from_unit.entity"
        if stale.exists():
            stale.unlink()
        print(f"{lang_dir.name}: {len(unit_words(lang_dir))} unit words")


if __name__ == "__main__":
    main()
