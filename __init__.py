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

SCOPE OF THIS INITIAL SCAFFOLD
-------------------------------
This is a skeleton, not a finished skill. Only the "length/distance"
category is wired up end-to-end as a proof of concept: value
extraction, unit alias resolution, pint conversion, dialog. Every other
category from the original brief (energy, force, mass, power,
pressure, speed, temperature, time, volume, angle, area, density,
acceleration, torque, flow, light, computer, concentration, custom) is
NOT implemented yet - see UNIT_ALIASES below, where each one needs its
own alias table proposed and checked before being added, same as vocab
work has always been done in this project.

A KNOWN TRAP LEFT DELIBERATELY UNRESOLVED
-------------------------------------------
Danish "mil" is NOT interchangeable with the English "mile" - it's the
Scandinavian mile (10 km), a different unit entirely. It's deliberately
left OUT of the Danish alias table below rather than mapped to either
"mi" or something invented, until we decide how (or whether) to
support it explicitly.
"""

from ovos_workshop.skills import OVOSSkill
from ovos_workshop.decorators import intent_handler
from ovos_number_parser import extract_number
from ovos_utils.parse import match_one

import pint

UREG = pint.UnitRegistry()

UNIT_MATCH_THRESHOLD = 0.8

# category -> lang -> {spoken alias: pint unit string}
# Only "length" is populated for this initial scaffold - see module
# docstring for why the rest is deliberately left empty.
UNIT_ALIASES = {
    "length": {
        "en-us": {
            "centimeter": "cm", "centimeters": "cm", "cm": "cm",
            "millimeter": "mm", "millimeters": "mm", "mm": "mm",
            "meter": "m", "meters": "m", "metre": "m", "metres": "m", "m": "m",
            "kilometer": "km", "kilometers": "km", "km": "km",
            "inch": "in", "inches": "in",
            "foot": "ft", "feet": "ft",
            "yard": "yd", "yards": "yd",
            "mile": "mi", "miles": "mi",
        },
        "da-dk": {
            "centimeter": "cm", "cm": "cm",
            "millimeter": "mm", "mm": "mm",
            "meter": "m", "m": "m",
            "kilometer": "km", "km": "km",
            "tomme": "in", "tommer": "in",
            "fod": "ft",
            "yard": "yd",
            # "mil" (Scandinavian mile, 10 km) intentionally omitted -
            # see module docstring
        },
    },
}


class UnitConverter(OVOSSkill):

    def _aliases_for(self, lang):
        """length is the only populated category right now - falls
        back to English aliases for any language without its own
        table."""
        lang = lang.lower()
        return UNIT_ALIASES["length"].get(lang) or UNIT_ALIASES["length"]["en-us"]

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
            quantity = value * UREG(from_unit)
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
