#!/usr/bin/env python3
"""Проверяет, что общий layout уже хранит подготовленную безопасную разметку."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "_layouts" / "default.html"

REQUIRED = {
    "условный CSS анкеты": """  {% if page.url == '/online-zayavka/' %}
  <link rel=\"stylesheet\" href=\"{{ '/assets/css/online-application.css' | relative_url }}\">
  {% endif %}""",
    "условный JavaScript анкеты": """  {% if page.url == '/online-zayavka/' %}
  <script src=\"{{ '/assets/js/online-application.js' | relative_url }}\" defer></script>
  {% endif %}""",
    "responsive preload": "imagesrcset=\"{{ '/assets/img/tatyana-hero-mobile.webp' | relative_url }} 288w, {{ page.hero_photo | relative_url }} 360w\"",
    "fragment request ID": "fragmentParams.get('id') || legacyParams.get('id') || ''",
}

FORBIDDEN = {
    "глобальный CSS анкеты": "  <link rel=\"stylesheet\" href=\"{{ '/assets/css/online-application.css' | relative_url }}\">\n  <link rel=\"stylesheet\" href=\"{{ '/assets/css/print.css' | relative_url }}\" media=\"print\">",
    "глобальный JavaScript анкеты": "  <script src=\"{{ '/assets/js/main.js' | relative_url }}\" defer></script>\n  <script src=\"{{ '/assets/js/online-application.js' | relative_url }}\" defer></script>",
    "старый preload": "{% if page.hero_photo %}<link rel=\"preload\" as=\"image\" href=\"{{ page.hero_photo | relative_url }}\">{% endif %}",
    "scenario в thank-you parser": "scenario: params.get('scenario')",
    "status в thank-you parser": "status: params.get('status')",
}


def fail(message: str) -> None:
    print(f"::error file={LAYOUT.relative_to(ROOT)}::{message}")


def main() -> int:
    if not LAYOUT.is_file():
        fail("Канонический layout не найден")
        return 1

    text = LAYOUT.read_text(encoding="utf-8-sig")
    errors = 0

    for label, marker in REQUIRED.items():
        if marker not in text:
            fail(f"Отсутствует обязательный маркер: {label}")
            errors += 1

    for label, marker in FORBIDDEN.items():
        if marker in text:
            fail(f"Найден устаревший маркер: {label}")
            errors += 1

    if errors:
        print(f"Аудит канонического layout завершён с ошибками: {errors}")
        return 1

    print("Канонический layout подтверждён: условные asset, responsive preload и минимальный thank-you context")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
