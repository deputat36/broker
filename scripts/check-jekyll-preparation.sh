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
python3 scripts/prepare-jekyll-source.py --write 2>&1 | tee "$LOG_FILE"
after_hash="$(hash_diff)"

git diff --check

if [[ "$before_hash" != "$after_hash" ]]; then
  echo "::error::Повторный Jekyll prebuild изменил подготовленные исходники" >&2
  echo "Diff hash до:    $before_hash" >&2
  echo "Diff hash после: $after_hash" >&2
  echo "Изменённые файлы после второго прохода:" >&2
  git diff --name-only >&2
  exit 1
fi

for marker in \
  "Front matter: нормализовано: файлов — 0" \
  "Фото-разметка: подготовлена: файлов — 0" \
  "Thank-you privacy: минимизирована: файлов — 0"
do
  if ! grep -Fq "$marker" "$LOG_FILE"; then
    echo "::error file=$LOG_FILE::Второй проход не подтвердил нулевое изменение: $marker" >&2
    exit 1
  fi
done

echo "Jekyll source preparation идемпотентна: повторный проход не изменил diff"
