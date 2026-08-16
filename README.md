# <img src='icon.png' card_color='#40DBB0' width='50' height='50' style='vertical-align:bottom'/> Unit Converter

A local, fully offline unit converter skill for OVOS - no cloud
dependency, no API key. Conversion math is done with
[pint](https://pint.readthedocs.io/), spoken numbers are parsed with
[ovos-number-parser](https://github.com/OpenVoiceOS/ovos-number-parser).

[![Tests](https://github.com/andlo/ovos-skill-convert/actions/workflows/test.yml/badge.svg)](https://github.com/andlo/ovos-skill-convert/actions/workflows/test.yml)
[![PyPI version](https://img.shields.io/pypi/v/ovos-skill-convert.svg)](https://pypi.org/project/ovos-skill-convert/)

> **This is an early-stage scaffold (0.0.x).** Only the length/distance
> category works end-to-end right now. It's not ready for the OVOS
> Skill Store yet - see "Status" below.

## Why this exists

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

## Status

**Implemented:** length/distance (cm, mm, m, km, in, ft, yd, mi), in
English and Danish.

**Not implemented yet:** every other category from the original brief
- energy, force, mass, power, pressure, speed, temperature, time,
volume, angle, area, density, acceleration, torque, flow, light,
computer, concentration, custom. Each one needs its own spoken-alias
table reviewed before being wired in - see `UNIT_ALIASES` in
`__init__.py` and `DEVELOPMENT.md` for how that review process works
in this project.

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

## A known trap, left deliberately unresolved

Danish **"mil"** is NOT the same as the English "mile" - it's the
Scandinavian mile (10 km), a distinct unit. It's intentionally left out
of the Danish alias table rather than mapped to `mi` (or anything
invented), until we explicitly decide how to support it. See the
module docstring in `__init__.py` and `test_resolve_unit_danish_mile_not_mapped`
in `tests/test_smoke.py`.

## Unit resolution strategy

Spoken unit text is resolved in three steps:
1. Exact match against the current language's alias table.
2. Fuzzy match (`match_one`, threshold 0.8) against that same table -
   covers minor STT mishearings.
3. Fallback: try the raw text directly against `pint` (covers someone
   literally saying a unit symbol like "cm").

If none of those resolve, the skill says so rather than guessing.

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md).

## Category
**Utility**

## Tags
#converter #units #measurement #utility #offline
