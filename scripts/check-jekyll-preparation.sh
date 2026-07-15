#!/usr/bin/env bash

set -euo pipefail

LOG_FILE="${1:-prepare-second-pass.log}"

hash_diff() {
  git diff --binary -- . \
    ':(exclude)source-audits.log' \
    ':(exclude)post-build-audits.log' \
    ':(exclude)prepare-second-pass.log' \
    | sha256sum \
    | cut -d' ' -f1
}

before_hash="$(hash_diff)"
bash scripts/prepare-jekyll-source.sh 2>&1 | tee "$LOG_FILE"
after_hash="$(hash_diff)"

git diff --check

if [[ "$before_hash" != "$after_hash" ]]; then
  echo "::error::Проверка Jekyll-исходников изменила рабочее дерево" >&2
  echo "Diff hash до:    $before_hash" >&2
  echo "Diff hash после: $after_hash" >&2
  echo "Изменённые файлы:" >&2
  git diff --name-only >&2
  exit 1
fi

for marker in \
  "Канонический layout подтверждён:" \
  "Канонические prepared-source подтверждены:" \
  "Front matter каноничен: файлов с нарушениями — 0"
do
  if ! grep -Fq "$marker" "$LOG_FILE"; then
    echo "::error file=$LOG_FILE::Проверка не подтвердила ожидаемый маркер: $marker" >&2
    exit 1
  fi
done

echo "Jekyll-исходники каноничны: проверки не изменили рабочее дерево"
