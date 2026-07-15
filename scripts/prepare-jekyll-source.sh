#!/usr/bin/env bash

set -euo pipefail

ROOT="${1:-.}"

python3 scripts/prepare-jekyll-source.py --root "$ROOT" --write
python3 scripts/prepare-conditional-assets.py --root "$ROOT" --write
