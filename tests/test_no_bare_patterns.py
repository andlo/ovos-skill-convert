"""convert.intent must not have a bare '{quantity} <word> {to_unit}' line.

Such a line makes padatious read ordinary sentences as conversions: in
Danish "Hvordan har du det i dag?" became quantity "Hvordan har du det" and
unit "dag", and "Velkommen til caféen" or "I'm going to bed" fit too. The
skill then answers "I don't know that unit" and nothing after it in the
pipeline (common query, persona, fallbacks) gets the chance.
"""
import re
from pathlib import Path

LOCALE = Path(__file__).resolve().parent.parent / "locale"
BARE = re.compile(r"^\{quantity\}\s+\S+\s+\{to_unit\}\s*$")


def test_no_bare_quantity_patterns():
    found = []
    for f in sorted(LOCALE.glob("*/convert.intent")):
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if BARE.match(line.strip()):
                found.append(f"{f.parent.name}/{f.name}:{n}: {line.strip()}")
    assert not found, "bare patterns:\n" + "\n".join(found)
