#!/usr/bin/env python3
"""Проверяет, что ранее генерируемые prebuild-изменения уже записаны в исходники."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def fail(path: Path, message: str) -> None:
    print(f"::error file={path.relative_to(ROOT)}::{message}")


def read(relative: str) -> tuple[Path, str]:
    path = ROOT / relative
    if not path.is_file():
        fail(path, "Файл не найден")
        return path, ""
    return path, path.read_text(encoding="utf-8-sig")


def check_application() -> int:
    path, text = read("assets/js/online-application.js")
    if not text:
        return 1

    errors = 0
    required = (
        "function saveLastLead(payload) {",
        "saveLastLead(preparedPayload);",
        "url.hash = new URLSearchParams({ id: payload.request_id }).toString();",
        "request_id: payload.request_id",
        "expires_at: new Date(Date.now() + LAST_LEAD_RETENTION_MS).toISOString()",
    )
    forbidden = (
        "function saveLastLead(payload, channels)",
        "saveLastLead(preparedPayload, channels)",
        "url.searchParams.set('status'",
        "url.searchParams.set('scenario'",
    )

    for marker in required:
        if marker not in text:
            fail(path, f"Отсутствует канонический privacy-маркер: {marker}")
            errors += 1
    for marker in forbidden:
        if marker in text:
            fail(path, f"Найден устаревший privacy-маркер: {marker}")
            errors += 1

    match = re.search(
        r"function saveLastLead\(payload\) \{(?P<body>.*?)\n  \}\n\n  function buildThankYouUrl",
        text,
        re.DOTALL,
    )
    if not match:
        fail(path, "Не удалось выделить минимальный блок saveLastLead")
        return errors + 1

    safe_body = match.group("body")
    for forbidden_field in ("scenario", "object_type", "city", "qualification", "submitted_at", "channels"):
        if forbidden_field in safe_body:
            fail(path, f"В минимальном localStorage-блоке найдено лишнее поле: {forbidden_field}")
            errors += 1
    return errors


def check_photo_source(relative: str, uses_front_matter: bool) -> int:
    path, text = read(relative)
    if not text:
        return 1

    errors = 0
    required = [
        "<picture>",
        "tatyana-hero-mobile.webp",
        "tatyana-hero.webp",
        'width="360" height="450"',
        'type="image/webp"',
    ]

    for marker in required:
        if marker not in text:
            fail(path, f"Отсутствует канонический фото-маркер: {marker}")
            errors += 1

    if uses_front_matter and not re.search(
        r'^hero_photo:\s*["\']?/assets/img/tatyana-hero\.webp["\']?\s*$',
        text,
        re.MULTILINE,
    ):
        fail(path, "Front matter не указывает канонический WebP-портрет")
        errors += 1

    if "tatyana-hero.svg" in text:
        fail(path, "Исходник продолжает ссылаться на удалённый SVG-портрет")
        errors += 1
    return errors


def check_audit_marker(relative: str) -> int:
    path, text = read(relative)
    if not text:
        return 1
    errors = 0
    if "saveLastLead(preparedPayload)" not in text:
        fail(path, "Аудит не ожидает канонический вызов saveLastLead")
        errors += 1
    if "saveLastLead(preparedPayload, channels)" in text:
        fail(path, "Аудит содержит устаревший вызов saveLastLead с channels")
        errors += 1
    return errors


def main() -> int:
    errors = 0
    errors += check_application()
    errors += check_photo_source("index.md", uses_front_matter=True)
    errors += check_photo_source("o-brokere.md", uses_front_matter=False)
    errors += check_audit_marker("scripts/audit-public-lead-response.py")
    errors += check_audit_marker("scripts/audit-hybrid-delivery-state.py")

    if errors:
        print(f"Аудит канонических prepared-source завершён с ошибками: {errors}")
        return 1

    print("Канонические prepared-source подтверждены: privacy JS, фото-разметка и audit-маркеры")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
