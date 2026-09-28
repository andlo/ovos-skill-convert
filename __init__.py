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

19 of the 21 categories from the original brief are implemented,
including "Light" - added later than the others, once it turned out to
be solvable after all: pint has no built-in foot-candle, but
illuminance (lux vs foot-candle) is the SAME dimension
([luminosity]/[length]**2), unlike luminous flux (lumen) or intensity
(candela), which are genuinely different dimensions from illuminance
and from each other. A single custom unit definition
(UREG.define("foot_candle = lumen / foot ** 2 = fc")) is enough to
cover the illuminance sub-case; lumen/candela conversions are still out
of scope since there's nothing meaningful to convert them TO within
this skill's categories. "Custom" (the original program's user-
defined-unit tab) remains deliberately unimplemented - it doesn't map
onto a voice interface at all.

TEMPERATURE IS NOT SIMPLE MULTIPLICATION
-----------------------------------------
Celsius/Fahrenheit are "offset" units (there's a shift as well as a
scale between them) - `value * UREG(unit)` raises
`OffsetUnitCalculusError` for these. `UREG.Quantity(value, unit)` is
required instead, and works for every other (purely multiplicative)
category too, so it's used unconditionally below rather than special-
casing temperature.

FOLLOW-UP CONVERSION ("what is that in meters?")
--------------------------------------------------
Listens on the messagebus for EVERY "speak" event system-wide (not
just this skill's own), scans the spoken text for a number immediately
followed by a recognized unit, and remembers the last one found for
CONTEXT_TTL_SECONDS. A separate intent ("what is that in X" / "hvad er
det i X") converts from that remembered quantity instead of requiring
an explicit value+from_unit in the same utterance. This deliberately
also fires on THIS skill's own conversion results ("10 centimeters is
0.1 meters") - that's desired, it's what lets someone chain a second
follow-up conversion off the first one's result.

Known limitations of the text scanner, left as-is rather than over-
engineered for a heuristic feature:
- Only digit-written numbers are found (e.g. "52,000"), not spelled-
  out words - this matches how OVOS dialog rendering normally emits
  numbers (TTS verbalizes digits into speech downstream, the bus
  message text itself keeps them as digits).
- Scientific notation ("7.3\u00d710\u00b2\u00b2") is not recognized.
- Thousands/decimal separator convention is guessed from the message's
  language tag (comma-decimal for da-dk, period-decimal otherwise) -
  wrong if a skill emits numbers in a different convention than its
  own declared language.
- If a sentence has multiple recognizable (number, unit) pairs, the
  LAST one is remembered - e.g. "the Moon is 384,400 km away and
  weighs 7.3e22 kg" would remember the kg figure (the scientific-
  notation number wouldn't parse, but if it did, whichever comes last
  wins). This is a deliberate, simple, explainable rule - not an
  attempt at guessing "importance".
"""

import json
import re
import time
from pathlib import Path

from ovos_workshop.skills import OVOSSkill
from ovos_workshop.decorators import intent_handler, common_query
from ovos_number_parser import extract_number
from ovos_utils.parse import match_one

import pint

UREG = pint.UnitRegistry()

# pint has no built-in foot-candle - illuminance (lux vs foot-candle)
# IS a single interconvertible dimension though, unlike lumen/candela
# (see module docstring's "Light" paragraph), so a custom definition
# is enough to support it: 1 foot-candle = 1 lumen/ft^2 by definition.
UREG.define("foot_candle = lumen / foot ** 2 = fc")

UNIT_MATCH_THRESHOLD = 0.8
CONTEXT_TTL_SECONDS = 60
CONTEXT_MAX_UNIT_WORDS = 4  # longest multi-word alias we try matching after a number

NUMBER_RE = re.compile(r"[-+]?\d[\d.,]*\d|[-+]?\d")

SKILL_ROOT = Path(__file__).resolve().parent
LOCALE_DIR = SKILL_ROOT / "locale"

# ---------------------------------------------------------------
# Common Query safety net - see ovos-skill-geometry/ovos-skill-
# geography/ovos-skill-calculator's DEVELOPMENT.md for the live-
# tested finding this addresses (a platform-level semantic router,
# ovos-m2v-pipeline-high, can intercept a "what is X" utterance
# before this skill's own Padatious intents get a chance). Only the
# "what is {value} {from_unit} in {to_unit}" phrasing - the ONE line
# per language in convert.intent that's actually shaped like a
# question - not convert_last.intent's "what is that in X", which
# depends on mutable per-instance state (self._last_quantity) that
# could be stale or wrong during a Common Query race across skills,
# and not the imperative "convert X to Y" phrasings, which aren't
# question-shaped at all.
#
# Deliberately digit-only for the value (same NUMBER_RE convention
# already used elsewhere in this file for the follow-up-conversion
# scanner - see module docstring), and (prefix, connector) pairs
# mirroring the EXACT "what is X in Y" line already present in each
# language's own convert.intent - not a second implementation of
# unit-conversion parsing, just a fallback entry point that then
# calls the same self._resolve_unit()/pint conversion the regular
# intent handler uses.
CQ_CONVERT_PATTERNS = {
    "en-us": [(re.compile(r"^what(?:'s| is) ([\d.,]+)\s+(.+?)\s+in\s+(.+)$", re.I))],
    "da-dk": [(re.compile(r"^hvad er ([\d.,]+)\s+(.+?)\s+i\s+(.+)$", re.I))],
    "de-de": [(re.compile(r"^was sind ([\d.,]+)\s+(.+?)\s+in\s+(.+)$", re.I))],
    "es-es": [(re.compile(r"^qué son ([\d.,]+)\s+(.+?)\s+en\s+(.+)$", re.I))],
    "fr-fr": [(re.compile(r"^qu'est-ce que ([\d.,]+)\s+(.+?)\s+en\s+(.+)$", re.I))],
    "it-it": [(re.compile(r"^cosa sono ([\d.,]+)\s+(.+?)\s+in\s+(.+)$", re.I))],
    "nl-nl": [(re.compile(r"^wat is ([\d.,]+)\s+(.+?)\s+in\s+(.+)$", re.I))],
    "pt-pt": [(re.compile(r"^o que é ([\d.,]+)\s+(.+?)\s+em\s+(.+)$", re.I))],
}


def _load_unit_aliases_from_disk():
    """Reads locale/<lang>/unit_aliases.json for every language folder
    that has one, and flattens each into a single {alias: pint_unit}
    table per language, plus a separate never-map set per language
    (see "_never_map" below). Runtime resolution doesn't need to know
    which category a word came from - pint's own DimensionalityError
    already rejects nonsensical cross-category conversions (m -> kg
    etc), so category is purely an organisational grouping inside the
    JSON, not something the resolver needs.

    Raises at import time (rather than silently overwriting) if two
    categories in the same file define the same alias with DIFFERENT
    target units - that's a real ambiguity bug, not something to paper
    over. Keys starting with "_" are reserved: "_notes" is
    documentation (skipped entirely), "_never_map" is data (see below).

    "_never_map" is a flat list of words that must NEVER resolve to
    anything for that language, even via fuzzy matching or the raw-
    pint-string fallback in _resolve_unit(). This exists because both
    of those paths can silently defeat a deliberate omission: fuzzy
    matching found French "livre" (deliberately NOT mapped - see that
    file's "_notes") scoring 0.8 against "litre" (liter) purely from
    edit-distance, and the raw-pint fallback accepted Dutch "pond"
    directly because pint itself defines "pond" as an unrelated CGS
    force unit (gram-force) - neither is the intended meaning. Omitting
    a word from the alias table only blocks the FIRST resolution
    path (exact match); "_never_map" is what actually makes "we
    decided not to guess" hold for every path.
    """
    merged = {}
    never_map = {}
    if not LOCALE_DIR.is_dir():
        return merged, never_map
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
        never_map.setdefault(lang, set())
        never_map[lang].update(w.lower() for w in categories.get("_never_map", []))
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
    return merged, never_map


MERGED_UNIT_ALIASES, NEVER_MAP = _load_unit_aliases_from_disk()


UNIT_ENTITIES = ("from_unit", "to_unit")


class UnitConverter(OVOSSkill):

    def load_data_files(self, root_directory=None):
        super().load_data_files(root_directory)
        self._protect_slot_endings()
        self._register_unit_entities()

    def _protect_slot_endings(self):
        """Works around ovos-padatious <= 1.4.3 (the current stable
        release): before training it strips trailing punctuation from
        every sample with rstrip(string.punctuation) - and "}" is
        punctuation. "convert {value} {from_unit} to {to_unit}" is
        trained as "... to {to_unit", the slot is lost, and on a live
        install the skill never matches its own examples (conf 0.00 in
        a normalized container, 0.25 among ~200 other intents).
        Every line of convert.intent ends in a slot.

        Fixed upstream in the ovos-padatious 2.x pre-releases (it
        keeps {}<> now). Until that is what people run, lines ending
        in a slot get " ?" appended: the "?" is what gets stripped,
        the space stops the stripping, the brace survives. On a fixed
        ovos-padatious the "?" is stripped the same way, so this is
        harmless there.

        Done by handing Padatious a padded copy of each .intent file
        (in the skill's own data folder) - the files in locale/ stay
        as translators know them."""
        service = self.intent_service
        original = service.register_padatious_intent
        padded_root = Path(self.file_system.path) / "padatious_intents"

        def register_padded(intent_name, filename, lang, string_blacklist=None):
            try:
                lines = Path(filename).read_text(encoding="utf-8").splitlines()
                padded = [f"{line} ?" if line.rstrip().endswith("}") else line
                          for line in (raw.rstrip() for raw in lines)]
                target = padded_root / lang / Path(filename).name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("\n".join(padded) + "\n", encoding="utf-8")
                filename = str(target)
            except Exception as e:  # fall back to the original file
                self.log.warning(f"could not pad {filename}: {e}")
            return original(intent_name, filename, lang, string_blacklist)

        service.register_padatious_intent = register_padded

    def _register_unit_entities(self):
        """Registers locale/<lang>/{from_unit,to_unit}.entity with
        Padatious so it knows which words fill those slots - see
        scripts/make_unit_entities.py for why this matters.

        Done here, not in initialize(), because load_data_files() runs
        just before the intent files are registered: the entities are
        then in place when Padatious trains on the intents.

        Registered directly instead of via register_entity_file(): in
        ovos-workshop 7.x that names the entity "<skill_id>:<file>_<md5>",
        and Padatious looks up "{from_unit}" as "<skill_id>:from_unit",
        so an entity registered that way is never used."""
        base = Path(__file__).resolve().parent / "locale"
        for lang in self.native_langs:
            for name in UNIT_ENTITIES:
                path = base / lang.lower() / f"{name}.entity"
                if not path.is_file():
                    continue
                try:
                    self.intent_service.register_padatious_entity(
                        f"{self.skill_id}:{name}", str(path), lang)
                except Exception as e:  # never block the skill from loading
                    self.log.warning(f"could not register {path}: {e}")

    def initialize(self):
        self._last_quantity = None  # {value, unit, raw_unit, lang, timestamp} | None
        # Listens on EVERY "speak" event system-wide, not just this
        # skill's own - see module docstring's "FOLLOW-UP CONVERSION"
        # section for why. add_event() (not raw self.bus.on()) so the
        # listener is cleaned up automatically on skill shutdown.
        self.add_event("speak", self.handle_speak_event)

    @common_query()
    def handle_common_query(self, phrase, lang):
        """Safety net - see CQ_CONVERT_PATTERNS above. Resolves both
        units and runs the SAME pint conversion _speak_conversion()
        uses, just returning the number as a string instead of
        speaking a dialog directly."""
        lang = lang.lower()
        patterns = CQ_CONVERT_PATTERNS.get(lang) or CQ_CONVERT_PATTERNS.get("en-us", [])
        stripped = phrase.strip().rstrip("?").strip()
        for pattern in patterns:
            m = pattern.match(stripped)
            if not m:
                continue
            value_raw, from_raw, to_raw = m.groups()
            value = self._parse_localized_number(value_raw, lang)
            if value is None:
                return None
            from_unit = self._resolve_unit(from_raw, lang)
            to_unit = self._resolve_unit(to_raw, lang)
            if not from_unit or not to_unit:
                return None
            try:
                result = UREG.Quantity(value, from_unit).to(to_unit)
            except Exception:
                return None
            return str(round(result.magnitude, 4)), 0.8
        return None

    def _aliases_for(self, lang):
        lang = lang.lower()
        return MERGED_UNIT_ALIASES.get(lang) or MERGED_UNIT_ALIASES.get("en-us", {})

    def _never_map_for(self, lang):
        lang = lang.lower()
        return NEVER_MAP.get(lang) or NEVER_MAP.get("en-us", set())

    def _resolve_unit(self, raw, lang):
        """Fuzzy-matches spoken unit text against the known alias
        table for the device language, falling back to trying the raw
        text directly against pint (covers e.g. someone literally
        saying a unit symbol like 'cm').

        Checks the language's "_never_map" FIRST, before either of
        those paths - both fuzzy matching and the raw-pint fallback
        can otherwise silently resolve a word that was deliberately
        left out of the alias table (see _load_unit_aliases_from_disk
        docstring for the two real cases - "livre"/"litre" and
        "pond" - that made this check necessary)."""
        if not raw:
            return None
        key = raw.strip().lower()
        if key in self._never_map_for(lang):
            return None
        aliases = self._aliases_for(lang)
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

    def _parse_localized_number(self, raw, lang):
        """Best-effort locale-aware parse of a digit-written number
        found by NUMBER_RE. da-dk uses '.' as thousands separator and
        ',' as decimal; en-us (and the fallback for everything else)
        is the reverse. Wrong if a skill emits numbers in a different
        convention than its declared language, but that's a pre-
        existing risk of this being a heuristic feature at all - see
        module docstring."""
        if lang.lower().startswith("da"):
            cleaned = raw.replace(".", "").replace(",", ".")
        else:
            cleaned = raw.replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _find_last_quantity_in_text(self, text, lang):
        """Scans text for every (number, unit) pair - a digit number
        immediately followed by up to CONTEXT_MAX_UNIT_WORDS words
        that exactly match a known alias for `lang` - and returns the
        LAST one found, or None if there are none. Exact match only
        (no fuzzy match_one here) - this runs on every utterance any
        skill speaks, so a stricter match is deliberate to keep false
        positives rare."""
        aliases = self._aliases_for(lang)
        result = None
        for m in NUMBER_RE.finditer(text):
            value = self._parse_localized_number(m.group(), lang)
            if value is None:
                continue
            after_words = text[m.end():].strip().split()
            for window in range(min(CONTEXT_MAX_UNIT_WORDS, len(after_words)), 0, -1):
                candidate = " ".join(after_words[:window]).strip(".,!?;:\u00bb\u00ab\"'").lower()
                if candidate in aliases:
                    result = (value, aliases[candidate], candidate)
                    break
        return result

    def handle_speak_event(self, message):
        text = message.data.get("utterance", "")
        if not text:
            return
        lang = message.data.get("lang") or self.lang
        found = self._find_last_quantity_in_text(text, lang)
        if found is None:
            return
        value, unit, raw_unit = found
        self._last_quantity = {
            "value": value,
            "unit": unit,
            "raw_unit": raw_unit,
            "lang": lang,
            "timestamp": time.monotonic(),
        }
        self.log.debug(
            f"remembered quantity for follow-up conversion: "
            f"{value} {unit} (spoken as {raw_unit!r}, from: {text!r})"
        )

    def _speak_conversion(self, value, from_unit, to_unit, from_raw, to_raw):
        """Shared by handle_convert() and handle_convert_last() -
        does the actual pint conversion + speaks the result or the
        appropriate error dialog."""
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

        self._speak_conversion(value, from_unit, to_unit, from_raw, to_raw)

    @intent_handler("convert_last.intent")
    def handle_convert_last(self, message):
        if self._last_quantity is None:
            self.speak_dialog("nothing_to_convert")
            return
        age = time.monotonic() - self._last_quantity["timestamp"]
        if age > CONTEXT_TTL_SECONDS:
            self.speak_dialog("nothing_to_convert")
            return

        to_raw = message.data.get("to_unit")
        to_unit = self._resolve_unit(to_raw, self.lang)
        if not to_unit:
            self.speak_dialog("unit_not_understood")
            return

        self._speak_conversion(
            self._last_quantity["value"],
            self._last_quantity["unit"],
            to_unit,
            self._last_quantity["raw_unit"],
            to_raw,
        )
