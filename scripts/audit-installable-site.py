#!/usr/bin/env python3
"""Проверяет manifest, PNG-иконки и глобальные install-метаданные Pages-сборки."""

from __future__ import annotations

import json
import re
import struct
import sys
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

MANIFEST_ICONS = {
    "/assets/img/icon-192.png": (192, 192, "192x192", "any"),
    "/assets/img/icon-512.png": (512, 512, "512x512", "any"),
    "/assets/img/icon-maskable-512.png": (512, 512, "512x512", "maskable"),
}
APPLE_ICON = "/assets/img/apple-touch-icon.png"


def fail(path: Path, message: str) -> None:
    print(f"::error file={path}::{message}")


def png_size(path: Path) -> tuple[int, int] | None:
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 24 or data[:8] != PNG_SIGNATURE or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def purpose_tokens(value: object) -> set[str]:
    return {token for token in str(value or "").split() if token}


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    manifest_path = site_dir / "site.webmanifest"
    errors = 0

    if not manifest_path.is_file():
        fail(manifest_path, "Manifest отсутствует")
        return 1

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        fail(manifest_path, f"Manifest не является корректным JSON: {error}")
        return 1

    expected_values = {
        "id": "/",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "lang": "ru",
    }
    for key, expected in expected_values.items():
        if manifest.get(key) != expected:
            fail(manifest_path, f"Поле {key!r} равно {manifest.get(key)!r}, ожидалось {expected!r}")
            errors += 1

    for key in ("name", "short_name", "description"):
        value = manifest.get(key)
        if not isinstance(value, str) or not value.strip():
            fail(manifest_path, f"Поле {key!r} отсутствует или пусто")
            errors += 1

    for key in ("background_color", "theme_color"):
        value = manifest.get(key)
        if not isinstance(value, str) or not COLOR_RE.fullmatch(value):
            fail(manifest_path, f"Поле {key!r} должно быть цветом #RRGGBB")
            errors += 1

    icons = manifest.get("icons")
    if not isinstance(icons, list):
        fail(manifest_path, "Поле icons должно быть массивом")
        icons = []
        errors += 1

    by_src = {
        icon.get("src"): icon
        for icon in icons
        if isinstance(icon, dict) and isinstance(icon.get("src"), str)
    }

    for src, (width, height, sizes, purpose) in MANIFEST_ICONS.items():
        icon = by_src.get(src)
        icon_path = site_dir / src.lstrip("/")
        if icon is None:
            fail(manifest_path, f"Manifest не содержит обязательную иконку {src}")
            errors += 1
            continue
        if icon.get("sizes") != sizes:
            fail(manifest_path, f"У {src} неверный sizes: {icon.get('sizes')!r}")
            errors += 1
        if icon.get("type") != "image/png":
            fail(manifest_path, f"У {src} должен быть type=image/png")
            errors += 1
        if purpose not in purpose_tokens(icon.get("purpose")):
            fail(manifest_path, f"У {src} отсутствует purpose={purpose}")
            errors += 1

        actual_size = png_size(icon_path)
        if actual_size != (width, height):
            fail(icon_path, f"PNG имеет размер {actual_size!r}, ожидалось {(width, height)!r}")
            errors += 1
        elif icon_path.stat().st_size <= 100:
            fail(icon_path, "PNG подозрительно мал или пуст")
            errors += 1

    apple_path = site_dir / APPLE_ICON.lstrip("/")
    if png_size(apple_path) != (180, 180):
        fail(apple_path, "apple-touch-icon должен быть корректным PNG 180x180")
        errors += 1

    html_files = sorted(site_dir.rglob("*.html"))
    if not html_files:
        fail(site_dir, "HTML-страницы не найдены")
        return errors + 1

    manifest_marker = '<link rel="manifest" href="/site.webmanifest">'
    apple_marker = '<link rel="apple-touch-icon" sizes="180x180" href="/assets/img/apple-touch-icon.png">'
    capable_marker = '<meta name="apple-mobile-web-app-capable" content="yes">'

    for page in html_files:
        text = page.read_text(encoding="utf-8-sig", errors="ignore")
        for marker, label in (
            (manifest_marker, "manifest"),
            (apple_marker, "apple-touch-icon"),
            (capable_marker, "apple-mobile-web-app-capable"),
        ):
            count = text.count(marker)
            if count != 1:
                fail(page, f"Маркер {label} встречается {count} раз, ожидался ровно один")
                errors += 1

    if errors:
        print(f"Аудит install-метаданных завершён с ошибками: {errors}")
        return 1

    print(
        "Install-метаданные подтверждены: "
        f"{len(html_files)} HTML-страниц, PNG 180/192/512 и отдельная maskable-иконка"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
