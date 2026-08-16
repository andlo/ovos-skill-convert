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

This project follows the same review-before-implementation pattern as
the rest of the OVOS work here: **propose the alias table, get it
checked, then commit it** - don't add a full category unreviewed.

1. Pick the category (e.g. "mass") and list the units you want spoken
   support for, with their `pint` unit strings
   (see [pint's default unit list](https://github.com/hgrecco/pint/blob/master/pint/default_en.txt)).
2. Draft the `UNIT_ALIASES["mass"]` entry for `en-us` first - spoken
   forms (singular/plural/symbol) mapped to the pint string.
3. Draft the Danish (`da-dk`) equivalent **as a structural translation,
   not a literal one** - watch for false-friend traps like the
   Danish "mil" vs English "mile" case documented in `__init__.py`.
   When in doubt about whether a Danish unit name is truly equivalent
   to its English counterpart, flag it rather than guessing.
4. Bring both tables here for review before wiring them into the
   skill.
5. Once agreed, add the category to `UNIT_ALIASES`, add a
   `test_resolve_unit_*` case per language, and confirm
   `pytest tests/ -v` still passes.

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
