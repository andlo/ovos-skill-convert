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

SCOPE
-----
18 of the 21 categories from the original brief are implemented:
length, mass, temperature, time, speed, area, volume, volume_dry
(en-us only - see below), angle, density, pressure, force, energy,
power, torque, acceleration, concentration, computer.

Two categories from the original brief are deliberately NOT
implemented:
- "Light" - pint (this version) has no foot-candle/phot units, and
  lumen/lux/candela are three different dimensions that aren't
  directly interconvertible with each other, so there's nothing
  meaningful to build here without adding custom unit definitions.
- "Custom" - was the original program's user-defined-unit tab, which
  doesn't map onto a voice interface at all.

Every alias string below was checked against the installed pint
registry before being added (see DEVELOPMENT.md) - none of this is
guessed. Several deliberate omissions/false-friend traps are flagged
inline where they came up; see also the "known traps" list in
DEVELOPMENT.md.

TEMPERATURE IS NOT SIMPLE MULTIPLICATION
-----------------------------------------
Celsius/Fahrenheit are "offset" units (there's a shift as well as a
scale between them) - `value * UREG(unit)` raises
`OffsetUnitCalculusError` for these. `UREG.Quantity(value, unit)` is
required instead, and works for every other (purely multiplicative)
category too, so it's used unconditionally below rather than special-
casing temperature.
"""

from ovos_workshop.skills import OVOSSkill
from ovos_workshop.decorators import intent_handler
from ovos_number_parser import extract_number
from ovos_utils.parse import match_one

import pint

UREG = pint.UnitRegistry()

UNIT_MATCH_THRESHOLD = 0.8

# category -> lang -> {spoken alias: pint unit string}
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
            # NOT the same as English "mile". See DEVELOPMENT.md.
        },
    },
    "mass": {
        "en-us": {
            "gram": "g", "grams": "g", "g": "g",
            "milligram": "mg", "milligrams": "mg", "mg": "mg",
            "kilogram": "kg", "kilograms": "kg", "kilo": "kg", "kilos": "kg", "kg": "kg",
            "pound": "lb", "pounds": "lb", "lb": "lb", "lbs": "lb",
            "ounce": "oz", "ounces": "oz", "oz": "oz",
            "stone": "stone",
            "ton": "ton", "tons": "ton",  # bare "ton" = US short ton (2000 lb) in pint
            "metric ton": "metric_ton", "metric tons": "metric_ton",
            "tonne": "metric_ton", "tonnes": "metric_ton",
        },
        "da-dk": {
            "gram": "g", "g": "g",
            "milligram": "mg", "mg": "mg",
            "kilogram": "kg", "kilo": "kg", "kg": "kg",
            # Danish "ton" means METRIC ton (1000 kg) in everyday
            # speech - deliberately mapped to metric_ton, NOT pint's
            # bare "ton" (which is the US short ton, 2000 lb / 907 kg).
            "ton": "metric_ton", "tons": "metric_ton",
            # "pund" intentionally omitted - traditional Danish "pund"
            # is exactly 500 g, NOT the imperial pound (453.592 g).
            # A different false-friend trap, same shape as "mil".
        },
    },
    "temperature": {
        "en-us": {
            "celsius": "degC", "centigrade": "degC",
            "fahrenheit": "degF",
            "kelvin": "kelvin",
        },
        "da-dk": {
            "celsius": "degC",
            "fahrenheit": "degF",
            "kelvin": "kelvin",
            # bare "grader"/"degrees" is NOT mapped to temperature - it
            # resolves to the angle category instead (see "angle"
            # below). Saying just "grader" defaults to angle; "celsius"
            # (etc) must be named explicitly for temperature. This is
            # a deliberate disambiguation, not an oversight.
        },
    },
}

UNIT_ALIASES["time"] = {
    "en-us": {
        "second": "second", "seconds": "second", "sec": "second",
        "minute": "minute", "minutes": "minute", "min": "minute",
        "hour": "hour", "hours": "hour", "hr": "hour",
        "day": "day", "days": "day",
        "week": "week", "weeks": "week",
        "year": "year", "years": "year",
    },
    "da-dk": {
        "sekund": "second", "sekunder": "second",
        "minut": "minute", "minutter": "minute",
        "time": "hour", "timer": "hour",
        "dag": "day", "dage": "day",
        "uge": "week", "uger": "week",
        "\u00e5r": "year",  # "år" - NOT aliased as "ar", which is a
                             # real pint area unit (100 m²) - a
                             # collision I almost introduced myself.
    },
}

UNIT_ALIASES["speed"] = {
    "en-us": {
        "meter per second": "m/s", "meters per second": "m/s", "m/s": "m/s",
        "kilometer per hour": "km/h", "kilometers per hour": "km/h", "km/h": "km/h", "kmh": "km/h",
        "mile per hour": "mph", "miles per hour": "mph", "mph": "mph",
        "knot": "knot", "knots": "knot",
    },
    "da-dk": {
        "meter per sekund": "m/s", "meter i sekundet": "m/s",
        "kilometer i timen": "km/h", "kilometer per time": "km/h",
        "knob": "knot",
        # miles per hour intentionally omitted - not naturally spoken in Danish
    },
}

UNIT_ALIASES["area"] = {
    "en-us": {
        "square meter": "m**2", "square meters": "m**2",
        "square kilometer": "km**2", "square kilometers": "km**2",
        "square foot": "ft**2", "square feet": "ft**2",
        "acre": "acre", "acres": "acre",
        "hectare": "hectare", "hectares": "hectare",
    },
    "da-dk": {
        "kvadratmeter": "m**2",
        "kvadratkilometer": "km**2",
        "hektar": "hectare",
        # "tønde land" (historical Danish land unit, ~5516 m²)
        # intentionally omitted - regional/historical variants exist,
        # too ambiguous to alias without picking one arbitrarily
    },
}

UNIT_ALIASES["volume"] = {
    "en-us": {
        "liter": "liter", "liters": "liter", "litre": "liter", "litres": "liter",
        "milliliter": "milliliter", "milliliters": "milliliter", "ml": "milliliter",
        "gallon": "gallon", "gallons": "gallon",  # US liquid gallon (pint default)
        "quart": "quart", "quarts": "quart",
        "pint": "pint", "pints": "pint",  # US liquid pint (pint default)
        "cup": "cup", "cups": "cup",
        "tablespoon": "tablespoon", "tablespoons": "tablespoon", "tbsp": "tablespoon",
        "teaspoon": "teaspoon", "teaspoons": "teaspoon", "tsp": "teaspoon",
        "fluid ounce": "fluid_ounce", "fluid ounces": "fluid_ounce",
    },
    "da-dk": {
        "liter": "liter",
        "milliliter": "milliliter",
        "deciliter": "deciliter",
        "spiseske": "tablespoon", "spiseskeer": "tablespoon",
        "teske": "teaspoon", "teskeer": "teaspoon",
        # gallon/quart/US-pint/cup intentionally omitted - not
        # naturally spoken in Danish; Danish speakers use liter-based
        # units for volume
    },
}

UNIT_ALIASES["volume_dry"] = {
    "en-us": {
        "dry pint": "dry_pint", "dry pints": "dry_pint",
        "dry quart": "dry_quart", "dry quarts": "dry_quart",
        "dry gallon": "dry_gallon", "dry gallons": "dry_gallon",
        "bushel": "bushel", "bushels": "bushel",
    },
    # da-dk intentionally has no entry here - Danish doesn't
    # distinguish dry/liquid volume in everyday speech (liter-based
    # units cover both), so there's no natural Danish phrasing to
    # alias without inventing one
}

UNIT_ALIASES["angle"] = {
    "en-us": {
        "degree": "degree", "degrees": "degree",
        "radian": "radian", "radians": "radian",
        "gradian": "gradian", "gradians": "gradian", "gon": "gradian",
    },
    "da-dk": {
        "grad": "degree", "grader": "degree",
        "radian": "radian", "radianer": "radian",
    },
}

UNIT_ALIASES["density"] = {
    "en-us": {
        "kilogram per cubic meter": "kg/m**3", "kilograms per cubic meter": "kg/m**3",
        "gram per cubic centimeter": "g/cm**3", "grams per cubic centimeter": "g/cm**3",
        "gram per milliliter": "g/mL", "grams per milliliter": "g/mL",
        "pound per cubic foot": "lb/ft**3", "pounds per cubic foot": "lb/ft**3",
    },
    "da-dk": {
        "kilogram per kubikmeter": "kg/m**3",
        "gram per kubikcentimeter": "g/cm**3",
        "gram per milliliter": "g/mL",
    },
}

UNIT_ALIASES["pressure"] = {
    "en-us": {
        "pascal": "pascal", "pascals": "pascal",
        "kilopascal": "kPa", "kilopascals": "kPa",
        "bar": "bar",
        "psi": "psi",
        "atmosphere": "atm", "atmospheres": "atm", "atm": "atm",
    },
    "da-dk": {
        "pascal": "pascal",
        "kilopascal": "kPa",
        "bar": "bar",
        "atmosfaere": "atm", "atmosf\u00e6re": "atm", "atmosf\u00e6rer": "atm",
    },
}

UNIT_ALIASES["force"] = {
    "en-us": {
        "newton": "newton", "newtons": "newton",
        "pound-force": "lbf", "pound force": "lbf", "lbf": "lbf",
    },
    "da-dk": {
        "newton": "newton",
        # "pund-kraft" intentionally omitted - not a natural spoken
        # Danish term
    },
}

UNIT_ALIASES["energy"] = {
    "en-us": {
        "joule": "joule", "joules": "joule",
        "kilojoule": "kilojoule", "kilojoules": "kilojoule",
        "calorie": "calorie", "calories": "calorie",
        "kilocalorie": "kilocalorie", "kilocalories": "kilocalorie",
        "watt hour": "watt_hour", "watt-hour": "watt_hour",
        "kilowatt hour": "kilowatt_hour", "kilowatt-hour": "kilowatt_hour", "kwh": "kilowatt_hour",
        "btu": "BTU",
    },
    "da-dk": {
        "joule": "joule",
        "kilojoule": "kilojoule",
        "kalorie": "calorie", "kalorier": "calorie",
        "kilokalorie": "kilocalorie", "kilokalorier": "kilocalorie",
        "kilowatttime": "kilowatt_hour", "kilowatt-time": "kilowatt_hour",
    },
}

UNIT_ALIASES["power"] = {
    "en-us": {
        "watt": "watt", "watts": "watt",
        "kilowatt": "kilowatt", "kilowatts": "kilowatt",
        "horsepower": "horsepower",
    },
    "da-dk": {
        "watt": "watt",
        "kilowatt": "kilowatt",
        # Danish "hestekraft"/"hk" is the METRIC horsepower, which is
        # NOT the same value as pint's bare "horsepower" (mechanical/
        # imperial hp) - about 1.4% different. Mapped to
        # metric_horsepower specifically, not "horsepower" - same
        # shape of trap as "ton" in the mass category above.
        "hestekraft": "metric_horsepower", "hestekraefter": "metric_horsepower",
        "hestekr\u00e6fter": "metric_horsepower", "hk": "metric_horsepower",
    },
}

UNIT_ALIASES["torque"] = {
    "en-us": {
        "newton meter": "newton*meter", "newton meters": "newton*meter", "newton-meter": "newton*meter",
        "foot-pound": "foot_pound", "foot pound": "foot_pound", "foot pounds": "foot_pound",
    },
    "da-dk": {
        "newtonmeter": "newton*meter",
    },
}

UNIT_ALIASES["acceleration"] = {
    "en-us": {
        "meter per second squared": "m/s**2", "meters per second squared": "m/s**2",
        "foot per second squared": "ft/s**2", "feet per second squared": "ft/s**2",
        # "standard gravity"/"free fall" only - deliberately NOT bare
        # "g", which would collide with the mass category's gram
        # symbol ("g" = gram there)
        "standard gravity": "standard_gravity", "free fall": "standard_gravity",
    },
    "da-dk": {
        "meter per sekund i anden": "m/s**2",
        "tyngdeacceleration": "standard_gravity",
    },
}

UNIT_ALIASES["concentration"] = {
    "en-us": {
        "mole per liter": "mol/L", "moles per liter": "mol/L",
        "milligram per deciliter": "mg/dL", "milligrams per deciliter": "mg/dL",
        "parts per million": "ppm", "ppm": "ppm",
        "percent": "percent",
    },
    "da-dk": {
        "mol per liter": "mol/L",
        "milligram per deciliter": "mg/dL",
        "procent": "percent",
    },
}

UNIT_ALIASES["computer"] = {
    "en-us": {
        "bit": "bit", "bits": "bit",
        "byte": "byte", "bytes": "byte",
        "kilobyte": "kilobyte", "kilobytes": "kilobyte",
        "megabyte": "megabyte", "megabytes": "megabyte",
        "gigabyte": "gigabyte", "gigabytes": "gigabyte",
        "terabyte": "terabyte", "terabytes": "terabyte",
    },
    "da-dk": {
        "bit": "bit",
        "byte": "byte",
        "kilobyte": "kilobyte",
        "megabyte": "megabyte",
        "gigabyte": "gigabyte",
        "terabyte": "terabyte",
    },
}

UNIT_ALIASES["flow"] = {
    "en-us": {
        "liter per minute": "liter/minute", "liters per minute": "liter/minute",
        "gallon per minute": "gallon/minute", "gallons per minute": "gallon/minute",
        "cubic meter per hour": "m**3/hour", "cubic meters per hour": "m**3/hour",
        # written out in full, deliberately NOT "cfm" - pint parses
        # "cfm" as centi-fermi (an obscure LENGTH unit), a silent
        # wrong match found while checking this table
        "cubic foot per minute": "ft**3/minute", "cubic feet per minute": "ft**3/minute",
    },
    "da-dk": {
        "liter per minut": "liter/minute",
        "kubikmeter per time": "m**3/hour",
    },
}


def _build_merged_aliases():
    """Flattens UNIT_ALIASES into one {alias: pint_unit} table per
    language. Runtime unit resolution doesn't need to know which
    category a word belongs to - pint's own DimensionalityError
    already rejects nonsensical cross-category conversions (m -> kg
    etc), so category is purely an organisational grouping for review,
    not something the resolver needs.

    Raises at import time (rather than silently overwriting) if two
    categories define the same alias for the same language with
    DIFFERENT target units - that would be a real ambiguity bug, not
    something to paper over.
    """
    merged = {}
    origin = {}  # (lang, alias) -> category, for the collision error message
    for category, per_lang in UNIT_ALIASES.items():
        for lang, aliases in per_lang.items():
            merged.setdefault(lang, {})
            for alias, pint_unit in aliases.items():
                existing = merged[lang].get(alias)
                if existing is not None and existing != pint_unit:
                    prev_category = origin[(lang, alias)]
                    raise ValueError(
                        f"UNIT_ALIASES collision: {lang!r} alias {alias!r} maps to "
                        f"both {existing!r} (in {prev_category!r}) and {pint_unit!r} "
                        f"(in {category!r})"
                    )
                merged[lang][alias] = pint_unit
                origin[(lang, alias)] = category
    return merged


MERGED_UNIT_ALIASES = _build_merged_aliases()


class UnitConverter(OVOSSkill):

    def _aliases_for(self, lang):
        lang = lang.lower()
        return MERGED_UNIT_ALIASES.get(lang) or MERGED_UNIT_ALIASES["en-us"]

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
