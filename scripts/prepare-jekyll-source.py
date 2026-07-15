#!/usr/bin/env python3
"""Нормализует текстовые поля YAML front matter перед Jekyll-сборкой.

Часть страниц исторически содержит двоеточие с пробелом внутри некавыченного
`description`. Psych воспринимает такой scalar как некорректный YAML, после чего
GitHub Pages собирает страницу без title, description, schema и permalink.
Скрипт детерминированно заключает известные текстовые поля в JSON-кавычки.
"""

from __future__ import annotations

import argparse
import json
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


def already_quoted(value: str) -> bool:
    stripped = value.lstrip()
    return (
        not stripped
        or stripped.startswith(('"', "'", "|", ">", "[", "{"))
    )


def normalize_file(path: Path, write: bool) -> bool:
    raw = path.read_text(encoding="utf-8-sig")
    newline = "\r\n" if "\r\n" in raw else "\n"
    had_final_newline = raw.endswith(("\n", "\r"))
    lines = raw.splitlines()
    end_index = front_matter_end(lines)
    if end_index is None:
        return False

    changed = False
    for index in range(1, end_index):
        match = FIELD_RE.match(lines[index])
        if not match:
            continue
        key, spacing, value = match.groups()
        if key not in TEXT_KEYS or already_quoted(value):
            continue

        normalized_value = json.dumps(value.strip(), ensure_ascii=False)
        lines[index] = f"{key}:{spacing or ' '}{normalized_value}"
        changed = True

    if changed and write:
        output = newline.join(lines)
        if had_final_newline:
            output += newline
        path.write_text(output, encoding="utf-8", newline="")
    return changed


def iter_markdown(root: Path):
    for path in root.rglob("*.md"):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        yield path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Корень исходников Jekyll")
    parser.add_argument("--write", action="store_true", help="Записать нормализованные файлы")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    changed_files = [path for path in iter_markdown(root) if normalize_file(path, args.write)]

    action = "нормализовано" if args.write else "требует нормализации"
    print(f"Front matter: {action} файлов — {len(changed_files)}")
    for path in changed_files[:20]:
        print(path.relative_to(root).as_posix())
    if len(changed_files) > 20:
        print(f"... и ещё {len(changed_files) - 20}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
