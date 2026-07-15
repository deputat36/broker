#!/usr/bin/env bash

set -euo pipefail

ROOT="${1:-.}"

python3 scripts/audit-canonical-layout.py
python3 scripts/audit-canonical-prepared-sources.py
python3 scripts/prepare-jekyll-source.py --root "$ROOT" --write
