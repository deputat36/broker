#!/usr/bin/env python3
"""Проверяет бинарные фото-asset и их подключение в собранном сайте."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "tatyana-hero.webp": ("webp", (360, 450), 20_000),
    "tatyana-hero-mobile.webp": ("webp", (288, 360), 20_000),
    "tatyana-avatar.webp": ("webp", (320, 320), 20_000),
    "tatyana-social.jpg": ("jpeg", (1200, 630), 50_000),
}
SOF_MARKERS = {
    0xC0,
    0xC1,
    0xC2,
    0xC3,
    0xC5,
    0xC6,
    0xC7,
    0xC9,
    0xCA,
    0xCB,
    0xCD,
    0xCE,
    0xCF,
}


def fail(message: str, path: Path | None = None) -> None:
    prefix = "::error"
    if path is not None:
        try:
            display = path.relative_to(ROOT).as_posix()
        except ValueError:
            display = path.as_posix()
        prefix += f" file={display}"
    print(f"{prefix}::{message}")


def webp_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("отсутствует сигнатура RIFF/WEBP")

    declared_size = int.from_bytes(data[4:8], "little") + 8
    if declared_size != len(data):
        raise ValueError(
            f"RIFF объявляет {declared_size} байт, фактически {len(data)}"
        )

    offset = 12
    while offset + 8 <= len(data):
        chunk = data[offset : offset + 4]
        size = int.from_bytes(data[offset + 4 : offset + 8], "little")
        start = offset + 8
        end = start + size
        if end > len(data):
            raise ValueError(f"обрезан chunk {chunk!r}")
        payload = data[start:end]

        if chunk == b"VP8X" and len(payload) >= 10:
            width = int.from_bytes(payload[4:7], "little") + 1
            height = int.from_bytes(payload[7:10], "little") + 1
            return width, height
        if chunk == b"VP8 " and len(payload) >= 10 and payload[3:6] == b"\x9d\x01\x2a":
            width = int.from_bytes(payload[6:8], "little") & 0x3FFF
            height = int.from_bytes(payload[8:10], "little") & 0x3FFF
            return width, height
        if chunk == b"VP8L" and len(payload) >= 5 and payload[0] == 0x2F:
            bits = int.from_bytes(payload[1:5], "little")
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
            return width, height

        offset = end + (size & 1)

    raise ValueError("не найден поддерживаемый WebP image chunk")


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 4 or not data.startswith(b"\xff\xd8"):
        raise ValueError("отсутствует JPEG SOI")
    if not data.endswith(b"\xff\xd9"):
        raise ValueError("отсутствует JPEG EOI")

    offset = 2
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            break

        marker = data[offset]
        offset += 1
        if marker in {0x01, *range(0xD0, 0xD9)}:
            continue
        if offset + 2 > len(data):
            raise ValueError("обрезана длина JPEG-сегмента")

        segment_size = int.from_bytes(data[offset : offset + 2], "big")
        if segment_size < 2 or offset + segment_size > len(data):
            raise ValueError(f"обрезан JPEG-сегмент FF {marker:02X}")
        if marker in SOF_MARKERS:
            if segment_size < 7:
                raise ValueError("слишком короткий JPEG SOF")
            height = int.from_bytes(data[offset + 3 : offset + 5], "big")
            width = int.from_bytes(data[offset + 5 : offset + 7], "big")
            return width, height
        offset += segment_size

    raise ValueError("не найден JPEG SOF с размерами")


def inspect_image(path: Path, kind: str) -> tuple[int, int]:
    data = path.read_bytes()
    if kind == "webp":
        return webp_dimensions(data)
    return jpeg_dimensions(data)


def check_assets(site_dir: Path) -> int:
    errors = 0
    for filename, (kind, expected_dimensions, max_size) in EXPECTED.items():
        source = ROOT / "assets" / "img" / filename
        built = site_dir / "assets" / "img" / filename
        for label, path in (("исходник", source), ("сборка", built)):
            if not path.is_file():
                fail(f"Отсутствует фото-asset ({label}): {filename}", path)
                errors += 1
                continue
            size = path.stat().st_size
            if size > max_size:
                fail(
                    f"{filename} весит {size} байт, лимит {max_size}",
                    path,
                )
                errors += 1
            try:
                dimensions = inspect_image(path, kind)
            except (OSError, ValueError) as error:
                fail(f"{filename} не является целым {kind.upper()}: {error}", path)
                errors += 1
                continue
            if dimensions != expected_dimensions:
                fail(
                    f"{filename}: получено {dimensions[0]}×{dimensions[1]}, "
                    f"ожидалось {expected_dimensions[0]}×{expected_dimensions[1]}",
                    path,
                )
                errors += 1
    return errors


def check_html(site_dir: Path) -> int:
    errors = 0
    pages = {
        "главная": site_dir / "index.html",
        "о брокере": site_dir / "o-brokere" / "index.html",
    }
    common_markers = (
        "<picture>",
        "tatyana-hero.webp",
        "tatyana-hero-mobile.webp",
        "tatyana-social.jpg",
        'alt="Татьяна Стерликова, ипотечный брокер"',
    )

    for label, path in pages.items():
        if not path.is_file():
            fail(f"Не найдена страница для проверки фото: {label}", path)
            errors += 1
            continue
        text = path.read_text(encoding="utf-8")
        for marker in common_markers:
            if marker not in text:
                fail(f"Страница «{label}» не содержит маркер: {marker}", path)
                errors += 1
        if "tatyana-hero.svg" in text:
            fail(f"Страница «{label}» продолжает использовать старый SVG-портрет", path)
            errors += 1

    index = pages["главная"]
    if index.is_file():
        text = index.read_text(encoding="utf-8")
        for marker in (
            "imagesrcset=",
            'content="1200"',
            'content="630"',
            'type="image/webp"',
            'width="360" height="450"',
        ):
            if marker not in text:
                fail(f"Главная не содержит обязательный фото-маркер: {marker}", index)
                errors += 1
    return errors


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    if not site_dir.is_dir():
        fail("Каталог собранного сайта не найден", site_dir)
        return 1

    errors = check_assets(site_dir) + check_html(site_dir)
    if errors:
        print(f"Аудит фотографий завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит фотографий успешно завершён: "
        f"asset-файлов {len(EXPECTED)}, страниц 2"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
