#!/bin/sh
# Check the BlogPosting authorship contract with test-only content.
#
# Builds the three fixture posts under scripts/fixtures/content/ (owner,
# guest, multi-author) into a throwaway directory and runs the validator
# in fixture mode. The fixture posts are never part of the published
# site: the build layers scripts/fixtures/config-override.toml after
# hugo.toml, which points both languages at the fixture content only.
# Run from anywhere; HUGO may point at a Hugo binary (default is the
# extended 0.152.2 binary used for this project).
set -e
cd "$(dirname "$0")/.."
HUGO_BIN="${HUGO:-/home/hatch/workspace/blog-redesign/tools/hugo}"
"$HUGO_BIN" --minify --gc \
    --config hugo.toml,scripts/fixtures/config-override.toml \
    -d /tmp/maj-fixtures-public
python3 scripts/validate-identity.py --fixtures /tmp/maj-fixtures-public \
    --identity data/identity.yaml
