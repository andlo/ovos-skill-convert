"""
skill OVOS Unit Converter
Copyright (C) 2026  Andreas Lorensen

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

---

Local, fully offline unit converter skill - no cloud dependency, no API
key. Uses `pint` for the actual conversion math and
`ovos-number-parser` to pull the numeric value out of the spoken
utterance.

UNIT ALIASES LIVE IN locale/<lang>/unit_aliases.json, NOT HERE
-----------------------------------------------------------------
Deliberately NOT a hardcoded Python dict - keeping alias tables as
per-language JSON resource files under locale/ means a new language
can be added by a translator (via the same ovos-localize workflow used
for .dialog/.intent/.voc elsewhere in this project) without touching
this file at all. See locale/en-us/unit_aliases.json for the reference
structure and locale/da-dk/unit_aliases.json for the Danish false-
friend decisions (both files carry their own "_notes" key explaining
what to watch for before editing).

18 of the 21 categories from the original brief are implemented. Two
are deliberately NOT: "Light" (this pint version has no foot-candle/
phot units, and lumen/lux/candela are three different dimensions that
aren't directly interconvertible) and "Custom" (was the original
program's user-defined-unit tab, doesn't map onto a voice interface).

TEMPERATURE IS NOT SIMPLE MULTIPLICATION
-----------------------------------------
Celsius/Fahrenheit are "offset" units (there's a shift as well as a
scale between them) - `value * UREG(unit)` raises
`OffsetUnitCalculusError` for these. `UREG.Quantity(value, unit)` is
required instead, and works for every other (purely multiplicative)
category too, so it's used unconditionally below rather than special-
casing temperature.
"""

import json
from pathlib import Path

from ovos_workshop.skills import OVOSSkill
from ovos_workshop.decorators import intent_handler
from ovos_number_parser import extract_number
from ovos_utils.parse import match_one

import pint

UREG = pint.UnitRegistry()

UNIT_MATCH_THRESHOLD = 0.8

SKILL_ROOT = Path(__file__).resolve().parent
LOCALE_DIR = SKILL_ROOT / "locale"


def _load_unit_aliases_from_disk():
    """Reads locale/<lang>/unit_aliases.json for every language folder
    that has one, and flattens each into a single {alias: pint_unit}
    table per language. Runtime resolution doesn't need to know which
    category a word came from - pint's own DimensionalityError already
    rejects nonsensical cross-category conversions (m -> kg etc), so
    category is purely an organisational grouping inside the JSON, not
    something the resolver needs.

    Raises at import time (rather than silently overwriting) if two
    categories in the same file define the same alias with DIFFERENT
    target units - that's a real ambiguity bug, not something to paper
    over. Keys starting with "_" (e.g. "_notes") are skipped - they're
    documentation, not category data.
    """
    merged = {}
    if not LOCALE_DIR.is_dir():
        return merged
    for lang_dir in sorted(LOCALE_DIR.iterdir()):
        if not lang_dir.is_dir():
            continue
        alias_file = lang_dir / "unit_aliases.json"
        if not alias_file.exists():
            continue
        with open(alias_file, encoding="utf-8") as f:
            categories = json.load(f)

        lang = lang_dir.name.lower()
        merged.setdefault(lang, {})
        origin = {}  # alias -> category, for the collision error message
        for category, aliases in categories.items():
            if category.startswith("_"):
                continue
            for alias, pint_unit in aliases.items():
                existing = merged[lang].get(alias)
                if existing is not None and existing != pint_unit:
                    prev_category = origin[alias]
                    raise ValueError(
                        f"unit_aliases.json collision in {alias_file}: "
                        f"alias {alias!r} maps to both {existing!r} "
                        f"(in {prev_category!r}) and {pint_unit!r} "
                        f"(in {category!r})"
                    )
                merged[lang][alias] = pint_unit
                origin[alias] = category
    return merged


MERGED_UNIT_ALIASES = _load_unit_aliases_from_disk()


class UnitConverter(OVOSSkill):

    def _aliases_for(self, lang):
        lang = lang.lower()
        return MERGED_UNIT_ALIASES.get(lang) or MERGED_UNIT_ALIASES.get("en-us", {})

    def _resolve_unit(self, raw, lang):
        """Fuzzy-matches spoken unit text against the known alias
        table for the device language, falling back to trying the raw
        text directly against pint (covers e.g. someone literally
        saying a unit symbol like 'cm')."""
        if not raw:
            return None
        aliases = self._aliases_for(lang)
        key = raw.strip().lower()
        if key in aliases:
            return aliases[key]
        match, score = match_one(key, list(aliases.keys()))
        if score >= UNIT_MATCH_THRESHOLD:
            return aliases[match]
        try:
            UREG(raw)  # validates it parses as a pint unit at all
            return raw
        except Exception:
            return None

    @intent_handler("convert.intent")
    def handle_convert(self, message):
        value_raw = message.data.get("value")
        from_raw = message.data.get("from_unit")
        to_raw = message.data.get("to_unit")

        value = extract_number(value_raw, lang=self.lang) if value_raw else None
        if value is False or value is None:
            value = 1

        from_unit = self._resolve_unit(from_raw, self.lang)
        to_unit = self._resolve_unit(to_raw, self.lang)

        if not from_unit or not to_unit:
            self.speak_dialog("unit_not_understood")
            return

        try:
            # UREG.Quantity(), not `value * UREG(unit)` - the latter
            # raises OffsetUnitCalculusError for offset units like
            # degC/degF (see module docstring). Quantity() handles
            # both offset and purely-multiplicative units correctly.
            quantity = UREG.Quantity(value, from_unit)
            result = quantity.to(to_unit)
        except pint.errors.DimensionalityError:
            self.speak_dialog("incompatible_units", {
                "from_unit": from_raw, "to_unit": to_raw})
            return
        except Exception:
            self.log.exception("conversion failed")
            self.speak_dialog("conversion_failed")
            return

        self.speak_dialog("conversion_result", {
            "value": value,
            "from_unit": from_raw,
            "result": round(result.magnitude, 4),
            "to_unit": to_raw,
        })
