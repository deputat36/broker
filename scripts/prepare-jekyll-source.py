#!/usr/bin/env python3
"""Проверяет канонический формат YAML front matter без изменения файлов.

Текстовые поля Jekyll должны храниться в кавычках либо в одном из явных
структурных YAML-форматов. Это исключает неоднозначный разбор двоеточий с
пробелом в Psych и гарантирует, что репозиторий совпадает со сборкой.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


TEXT_KEYS = {
    "layout",
    "title",
    "description",
    "permalink",
    "breadcrumb",
    "h1",
    "og_type",
    "og_image",
    "og_image_alt",
    "robots",
    "hero_photo",
}
SKIP_PARTS = {".git", "_site", "vendor", "node_modules"}
FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(\s*)(.*)$")


def front_matter_end(lines: list[str]) -> int | None:
    if not lines or lines[0].strip() != "---":
        return None
    for index in range(1, min(len(lines), 200)):
        if lines[index].strip() == "---":
            return index
    return None


def is_canonical_value(value: str) -> bool:
    stripped = value.lstrip()
    return not stripped or stripped.startswith(('"', "'", "|", ">", "[", "{"))


def find_issues(path: Path) -> list[tuple[int, str, str]]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    end_index = front_matter_end(lines)
    if end_index is None:
        return []

    issues: list[tuple[int, str, str]] = []
    for index in range(1, end_index):
        match = FIELD_RE.match(lines[index])
        if not match:
            continue
        key, _spacing, value = match.groups()
        if key in TEXT_KEYS and not is_canonical_value(value):
            issues.append((index + 1, key, value.strip()))
    return issues


def iter_markdown(root: Path):
    for path in root.rglob("*.md"):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        yield path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Корень исходников Jekyll")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    files_with_issues = 0
    issue_count = 0

    for path in iter_markdown(root):
        issues = find_issues(path)
        if not issues:
            continue
        files_with_issues += 1
        issue_count += len(issues)
        relative = path.relative_to(root).as_posix()
        for line, key, value in issues:
            print(
                f"::error file={relative},line={line}::"
                f"Поле {key} должно быть канонически заключено в кавычки: {value}"
            )

    if files_with_issues:
        print(
            "Front matter требует канонизации: "
            f"файлов — {files_with_issues}, полей — {issue_count}"
        )
        return 1

    print("Front matter каноничен: файлов с нарушениями — 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
