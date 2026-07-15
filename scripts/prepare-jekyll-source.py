#!/usr/bin/env python3
"""Подготавливает исходники перед Jekyll-сборкой.

Скрипт выполняет две детерминированные операции:

1. Нормализует текстовые поля YAML front matter. Исторические страницы
   содержат двоеточие с пробелом внутри некавыченного `description`, из-за
   чего Psych может собрать страницу без title, description, schema и permalink.
2. Переводит утверждённый портрет Татьяны на адаптивные WebP-файлы перед
   сборкой. Исходное лицо и композиция не изменяются: используются версии,
   подготовленные из уже находившегося в репозитории портрета.
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

INDEX_OLD_IMAGE = (
    '<img src="{{ page.hero_photo | relative_url }}" '
    'alt="Татьяна Стерликова, ипотечный брокер" width="640" height="800" '
    'loading="eager" fetchpriority="high">'
)
INDEX_NEW_IMAGE = (
    '<picture>'
    '<source media="(max-width: 760px)" '
    'srcset="{{ \'/assets/img/tatyana-hero-mobile.webp\' | relative_url }}" '
    'type="image/webp">'
    '<img src="{{ page.hero_photo | relative_url }}" '
    'alt="Татьяна Стерликова, ипотечный брокер" width="360" height="450" '
    'loading="eager" fetchpriority="high" decoding="async">'
    '</picture>'
)
ABOUT_OLD_IMAGE = (
    '<img src="{{ \'/assets/img/tatyana-hero.svg\' | relative_url }}" '
    'alt="Татьяна Стерликова, ипотечный брокер" width="640" height="800" '
    'loading="eager">'
)
ABOUT_NEW_IMAGE = (
    '<picture>'
    '<source media="(max-width: 760px)" '
    'srcset="{{ \'/assets/img/tatyana-hero-mobile.webp\' | relative_url }}" '
    'type="image/webp">'
    '<img src="{{ \'/assets/img/tatyana-hero.webp\' | relative_url }}" '
    'alt="Татьяна Стерликова, ипотечный брокер" width="360" height="450" '
    'loading="eager" decoding="async">'
    '</picture>'
)
PRELOAD_OLD = (
    '{% if page.hero_photo %}<link rel="preload" as="image" '
    'href="{{ page.hero_photo | relative_url }}">{% endif %}'
)
PRELOAD_NEW = (
    '{% if page.hero_photo %}<link rel="preload" as="image" '
    'href="{{ page.hero_photo | relative_url }}" type="image/webp" '
    'imagesrcset="{{ \'/assets/img/tatyana-hero-mobile.webp\' | relative_url }} 288w, '
    '{{ page.hero_photo | relative_url }} 360w" '
    'imagesizes="(max-width: 760px) 288px, 360px">{% endif %}'
)
PHOTO_REPLACEMENTS = {
    "index.md": (
        (
            'hero_photo: "/assets/img/tatyana-hero.svg"',
            'hero_photo: "/assets/img/tatyana-hero.webp"',
        ),
        (INDEX_OLD_IMAGE, INDEX_NEW_IMAGE),
    ),
    "o-brokere.md": ((ABOUT_OLD_IMAGE, ABOUT_NEW_IMAGE),),
    "_layouts/default.html": ((PRELOAD_OLD, PRELOAD_NEW),),
}


def front_matter_end(lines: list[str]) -> int | None:
    if not lines or lines[0].strip() != "---":
        return None
    for index in range(1, min(len(lines), 200)):
        if lines[index].strip() == "---":
            return index
    return None


def already_quoted(value: str) -> bool:
    stripped = value.lstrip()
    return not stripped or stripped.startswith(('"', "'", "|", ">", "[", "{"))


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


def apply_photo_replacements(root: Path, write: bool) -> list[Path]:
    changed_paths: list[Path] = []
    for relative_path, replacements in PHOTO_REPLACEMENTS.items():
        path = root / relative_path
        raw = path.read_text(encoding="utf-8-sig")
        updated = raw

        for old, new in replacements:
            if old in updated:
                updated = updated.replace(old, new, 1)
                continue
            if new in updated:
                continue
            raise ValueError(
                f"Не найден ожидаемый маркер фото-разметки: {relative_path}"
            )

        if updated == raw:
            continue
        changed_paths.append(path)
        if write:
            path.write_text(updated, encoding="utf-8", newline="")

    return changed_paths


def iter_markdown(root: Path):
    for path in root.rglob("*.md"):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        yield path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Корень исходников Jekyll")
    parser.add_argument("--write", action="store_true", help="Записать подготовленные файлы")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    changed_files = [path for path in iter_markdown(root) if normalize_file(path, args.write)]
    photo_files = apply_photo_replacements(root, args.write)

    action = "нормализовано" if args.write else "требует нормализации"
    print(f"Front matter: {action} файлов — {len(changed_files)}")
    for path in changed_files[:20]:
        print(path.relative_to(root).as_posix())
    if len(changed_files) > 20:
        print(f"... и ещё {len(changed_files) - 20}")

    photo_action = "подготовлена" if args.write else "требует подготовки"
    print(f"Фото-разметка: {photo_action} файлов — {len(photo_files)}")
    for path in photo_files:
        print(path.relative_to(root).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
