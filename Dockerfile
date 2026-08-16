# Container image for ovos-skill-convert.
#
# This does NOT run a full voice assistant by itself - a skill has no
# meaning without an ovos-core instance (messagebus, intent service,
# STT/TTS) to load it into. What this image IS: the skill package
# installed and importable, ready to be layered into an ovos-core
# image (COPY --from=ghcr.io/andlo/ovos-skill-convert:latest ...) or
# used as-is to run the test suite in CI/locally without a full OVOS
# stack.
#
# Built from local source (COPY + pip install .), not from PyPI - the
# release workflow tags and builds this image from the SAME commit
# that gets published to PyPI, avoiding any race between "is the new
# version live on PyPI yet" and "the image build already started".
FROM python:3.11-slim

WORKDIR /app

# Only what's needed to resolve/install dependencies copied first, so
# this layer caches across rebuilds where only skill code changed, not
# dependencies.
COPY setup.py version.py requirements.txt requirements-test.txt README.md ./
COPY __init__.py ./
COPY locale/ ./locale/
COPY tests/ ./tests/

RUN pip install --no-cache-dir -e . \
    && pip install --no-cache-dir -r requirements-test.txt

# Non-root user - no reason this needs root.
RUN useradd --create-home --shell /bin/bash ovos
USER ovos

# Default action: run the test suite. Override the command to `python`
# or a shell if you're using this image as a base layer instead.
CMD ["pytest", "tests/", "-v"]
