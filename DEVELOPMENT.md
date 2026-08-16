# Development

## Setup
```bash
git clone https://github.com/andlo/ovos-skill-convert.git
cd ovos-skill-convert
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -r requirements-test.txt
```

## Running tests
```bash
pytest tests/ -v
```
`tests/test_smoke.py` covers unit-alias resolution (exact match, fuzzy
match, unknown/empty input, the deliberate Danish "mil" non-mapping).
`tests/test_conversion.py` sanity-checks the actual `pint` conversion
math independent of the skill/bus layer.

## Adding a new unit category

As of `0.0.2`, 18 of the 21 original categories are done (see README
"Status"). What's left is Light (blocked on `pint` lacking foot-candle/
phot units - would need custom unit definitions) and Custom (doesn't
map onto a voice interface, likely permanently skipped).

The process below is how the existing categories were built, and
applies to any future one (a new Light approach, a category split more
finely, etc):

1. Pick the category and list the units you want spoken support for.
2. **Verify every candidate pint unit string actually resolves**,
   before writing a single alias - don't trust memory or docs. This
   caught several real mistakes while building the current categories
   (`cfm` silently parsing as centi-fermi; `us_ton`/`us_gallon` not
   existing under those exact names; `foot_candle` not existing at
   all in this pint version):
   ```python
   import pint
   u = pint.UnitRegistry()
   for candidate in ["kg", "lb", "metric_ton", "..."]:
       try:
           print("OK", candidate, u(candidate).units)
       except Exception as e:
           print("FAIL", candidate, e)
   ```
3. Draft the `UNIT_ALIASES["<category>"]["en-us"]` entry - spoken
   forms (singular/plural/symbol) mapped to the verified pint string.
4. Draft the Danish (`da-dk`) equivalent **as a structural translation,
   not a literal one** - actively look for false-friend traps like the
   ones in the README's table (Danish "ton"/"pund"/"hk" all needed
   different handling than a literal translation would give). A good
   check: does this Danish word's real-world value actually equal the
   English unit it superficially resembles? If unsure, omit it rather
   than guess - an omitted unit just doesn't work yet; a wrongly
   mapped one gives a confidently wrong answer.
5. Check for **cross-category collisions** in the same language -
   `_build_merged_aliases()` will raise at import time if two
   categories claim the same alias with different meanings, but it's
   worth deliberately checking short/symbol-like aliases (single
   letters, common abbreviations) against every other category before
   adding them, not just relying on the exception to catch it.
6. Add `test_resolve_unit_*` / `test_resolve_unit_across_categories`
   cases per language, and a `test_conversion.py` case for anything
   with a real numeric trap (offset units, two similarly-named but
   different-valued units). Confirm `pytest tests/ -v` still passes.

## Live bus testing

Same discipline as the rest of the OVOS projects here:
- One utterance per script run.
- `time.sleep(6-10)` after sending, to give the skill time to respond
  and be captured.
- `time.sleep(30-60)` between separate test runs, to avoid queue
  contamination on the live device.
- Test device: `ovos@192.168.65.43` (systemd/venv install).

## Versioning

`version.py` follows `VERSION_MAJOR.VERSION_MINOR.VERSION_BUILD[aVERSION_ALPHA]`.

This project stays on **0.0.x** until the length category is stable
and at least one more category has gone through the review process
above - at that point we bump to **0.1.0**. Until then, every release
is a `0.0.x` bump of `VERSION_BUILD`.

## Releasing

Releases are tag-triggered (`v*`), and build/publish both the PyPI
package and a container image from the same commit:

```bash
# bump VERSION_BUILD (or MINOR, once we're past 0.0.x) in version.py
git add version.py
git commit -m "chore: bump version to 0.0.X"
git tag vX.Y.Z
git push && git push --tags
```

This triggers, in order:
1. `.github/workflows/test.yml` - must pass first.
2. `.github/workflows/publish.yml` - builds and publishes to PyPI
   (uses PyPI's trusted publishing / OIDC, no stored token needed).
3. `.github/workflows/docker-publish.yml` - builds and pushes
   `ghcr.io/andlo/ovos-skill-convert:X.Y.Z` and `:latest`.

### One-time PyPI setup (not yet done)

Trusted publishing needs to be configured on the PyPI project side
before the first tagged release: create the project on PyPI (or claim
it on first manual upload), then add GitHub Actions as a trusted
publisher for the `andlo/ovos-skill-convert` repo, workflow
`publish.yml`, environment `pypi`. No API token needs to live in
GitHub secrets with this approach.

## Container image

`ghcr.io/andlo/ovos-skill-convert` bundles the skill for use in a
containerized OVOS setup (same pattern as `ovos-tui-client`'s
companion image: built from local source in the same tagged commit
that goes to PyPI, not pulled from PyPI after the fact, to avoid a
race between "is the new version live on PyPI yet" and "the image
build already started").

Build locally:
```bash
docker build -t ovos-skill-convert:dev .
```

## Style / conventions

- License: GPL-3.0-or-later (matches the other `andlo` skill repos).
- `locale/<lang-code>/` layout, not the old `dialog/vocab/<lang-code>/`
  layout.
- `skill.json` lives inside each `locale/<lang>/` folder, one per
  language.
- Present vocab/alias/intent changes for review before committing -
  same as translation work elsewhere in this project.
