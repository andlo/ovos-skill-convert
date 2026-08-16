# <img src='icon.png' card_color='#40DBB0' width='50' height='50' style='vertical-align:bottom'/> Unit Converter

A local, fully offline unit converter skill for OVOS - no cloud
dependency, no API key. Conversion math is done with
[pint](https://pint.readthedocs.io/), spoken numbers are parsed with
[ovos-number-parser](https://github.com/OpenVoiceOS/ovos-number-parser).

[![Tests](https://github.com/andlo/ovos-skill-convert/actions/workflows/test.yml/badge.svg)](https://github.com/andlo/ovos-skill-convert/actions/workflows/test.yml)
[![PyPI version](https://img.shields.io/pypi/v/ovos-skill-convert.svg)](https://pypi.org/project/ovos-skill-convert/)

> **This is an early-stage scaffold (0.0.x).** 19 of 21 categories from
> the original brief are wired up in English and Danish; 6 more
> languages have a first machine-translated pass (see "Status" -
> quality bar is lower than en-us/da-dk for those). Not ready for the
> OVOS Skill Store yet.

## Why this exists

![Convert - a classic Windows unit converter utility](docs/convert-legacy.jpg)

Back in the day, most Windows PCs had a little utility like this one -
a simple offline converter with tabs for every unit category you could
think of (distance, mass, temperature, volume, and so on), no internet
connection required. This skill is the voice-assistant equivalent of
that program: local, offline, no account, no API key, just "convert X
to Y".

There's a Wolfram Alpha plugin/skill in the OVOS ecosystem
(`ovos-wolfram-alpha-plugin` / `ovos-skill-wolfie`) that covers unit
conversion as part of a much broader "single-answer question" tool -
but it requires an internet connection and a Wolfram Alpha API key.
Nothing in the ecosystem does *just* unit conversion, locally, with no
dependency on a cloud service. This fills that gap.

## Install
```bash
pip install ovos-skill-convert
```

## Usage
```
"convert 10 centimeters to inches"
"how many feet is 2 meters"
"konverter 10 centimeter til tommer"      (Danish)
"hvor mange fod er 2 meter"               (Danish)
```

### Follow-up conversions ("what is that in meters?")

The skill listens for a number+unit spoken by *any* skill (not just
itself) and remembers the last one for 60 seconds, so a follow-up
works without repeating the value:

```
Other skill: "the distance to the Moon is 384400 kilometers"
You:         "what is that in miles"
Skill:       "384400.0 kilometers is 238855.0863 miles"
```

This also chains off the skill's own results:
```
You:   "convert 10 centimeters to inches"
Skill: "10 centimeters is 3.937 inches"
You:   "and what is that in feet"
Skill: "3.937 inches is 0.3281 feet"
```

If nothing recent was heard, it says so rather than guessing. See the
module docstring in `__init__.py` ("FOLLOW-UP CONVERSION") for the
known limitations of this heuristic (digit-written numbers only, no
scientific notation, locale-guessed decimal separator).

## Status

**Categories (19 of 21):** length, mass, temperature, time, speed,
area, volume, volume_dry (en-us only), angle, density, pressure,
force, energy, power, torque, acceleration, concentration, computer,
flow, light. **Deliberately not implemented:** "Custom" (the original
program's user-defined-unit tab - doesn't map onto a voice interface).

**Light** was added after initially being written off entirely: `pint`
has no built-in foot-candle, but illuminance (lux vs foot-candle) *is*
a single interconvertible dimension, unlike luminous flux (lumen) or
intensity (candela) - a one-line custom unit definition
(`UREG.define("foot_candle = lumen / foot ** 2 = fc")`) was enough to
cover it. Lumen/candela conversions remain out of scope.

**Languages:**

| Language | Confidence |
|---|---|
| `en-us` | Reference implementation, ~300 aliases, verified against `pint` unit-by-unit |
| `da-dk` | Native-speaker level - every false-friend trap actively hunted, not just translated |
| `de-de`, `es-es`, `fr-fr`, `it-it`, `nl-nl`, `pt-pt` | **First machine-translated pass, NOT native-speaker verified.** Same category structure as en-us, smaller alias sets (~80 each), the highest-confidence false-friend patterns applied by generalizing from the da-dk findings (see below) - but not fact-checked with the same rigor. Treat as a starting point; each file's `"_notes"` key flags what's unverified. |

Every unit string used anywhere was checked against the installed
`pint` registry before being added (see `DEVELOPMENT.md` for the
verification method) - none of it is guessed, even in the lower-
confidence languages. What's *not* verified in the new 6 is whether
the chosen alias words match how people actually speak in each
language - that needs native-speaker review.

Unit aliases live in `locale/<lang>/unit_aliases.json` per language,
not hardcoded in Python - see "Adding a new unit category or language"
in `DEVELOPMENT.md` for how to add or improve a language via the same
`ovos-localize` workflow used for the rest of this project's locale
content.

### False-friend traps found and handled

A few unit names collide across languages/contexts with a *different*
real-world value - each is called out in that language's
`unit_aliases.json` `"_notes"` key:

| Word | Wrong assumption | Correct handling |
|---|---|---|
| Danish "mil" | = English "mile" | It's the Scandinavian mile (10 km) - omitted, not mapped |
| Danish "ton" | = pint's bare `ton` (US short ton, 907 kg) | Mapped to `metric_ton` (1000 kg) - matches everyday Danish usage |
| Danish "pund" | = imperial pound (453.6 g) | It's exactly 500 g historically - omitted, not mapped |
| Danish "hk"/"hestekraft" | = pint's bare `horsepower` | Mapped to `metric_horsepower` (~1.4% different) |
| `cfm` (as an alias) | = cubic feet per minute | `pint` parses it as **centi-fermi**, an obscure length unit - spelled out in full instead |
| bare "g" | could mean gram or "free fall"/gravity | Only ever aliased to gram; acceleration uses "standard gravity"/"free fall" |
| bare "grader"/"degrees" (da/en) | could mean angle or temperature | Defaults to angle; temperature requires naming celsius/fahrenheit/kelvin explicitly |
| `oz` vs `fluid_ounce` | same English word, different dimension (mass vs volume) | Kept as separate keys, never merged |
| French "livre" | harmless if just omitted | **Wasn't** - fuzzy-matched "litre" (liter) at exactly the 0.80 threshold. Omitting a word from the alias table only blocks *exact* matching, not fuzzy matching or the raw-pint fallback below. |
| Dutch "pond" | harmless if just omitted | **Wasn't** - `pint` itself defines `pond` as an unrelated CGS force unit (gram-force), so the raw-pint fallback silently accepted it |
| Danish "mil" | harmless if just omitted | Resolves via the raw-pint fallback too - `pint` has "mil" as the dimensionless milli- SI prefix, so it doesn't crash, it just produces a confusing `DimensionalityError` instead of "I don't understand" |

The last three rows are the same *kind* of bug as the others, but a
category ahead: a word can be **correctly excluded from the alias
table** and *still* resolve to something wrong, via fuzzy matching or
the pint-string fallback. This is now handled with an explicit
per-language `"_never_map"` list in each `unit_aliases.json` - words
that must never resolve to anything, checked *before* either of those
two paths, not just absent from the main table. Every flagged word in
every language above (French/German/Italian/Portuguese "mile"-words,
"pound"-words, etc.) is in its language's `_never_map`, whether or not
it was actually provably dangerous - cheap insurance, and it documents
intent even where nothing currently breaks.

A startup consistency check (`_load_unit_aliases_from_disk()`) also
raises an error at import time if any two categories ever define the
same spoken alias with two *different* target units for the same
language - so a future collision like these can't ship silently.

## Architecture: why NOT Common Query

This is a regular intent skill (padatious), not a Common Query
provider. Common Query exists to pick the best answer among *multiple
skills that might plausibly answer the same question* (e.g. "what's
the capital of France"). Unit conversion has exactly one correct
answer and no competing sources to arbitrate between - routing it
through CQ would add latency and confidence-scoring machinery for a
problem that's already fully deterministic. A plain intent match with
structured slots (`value`, `from_unit`, `to_unit`) is the right tool
here.

## Unit resolution strategy

Spoken unit text is resolved in four steps:
1. Check the language's `_never_map` first - if the word is on it,
   stop immediately and return "not understood", regardless of what
   the later steps would have matched.
2. Exact match against the current language's alias table.
3. Fuzzy match (`match_one`, threshold 0.8) against that same table -
   covers minor STT mishearings.
4. Fallback: try the raw text directly against `pint` (covers someone
   literally saying a unit symbol like "cm").

If none of those resolve, the skill says so rather than guessing.

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md).

## Category
**Utility**

## Tags
#converter #units #measurement #utility #offline
