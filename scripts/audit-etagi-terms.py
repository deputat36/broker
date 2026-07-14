#!/usr/bin/env python3
"""Проверяет ключевые страницы на неподтверждённые обещания по условиям «ЭТАЖИ»."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "docs/etagi-terms-policy.md"

PAGES = {
    "/": ROOT / "index.md",
    "/etagi/": ROOT / "etagi.md",
    "/stoimost/": ROOT / "stoimost.md",
    "/faq/": ROOT / "faq.md",
}

FORBIDDEN = (
    "сопровождение включено в комиссию компании",
    "отдельно клиентом не оплачивается",
    "без доплаты при сделке через",
    "отдельной оплаты за ипотечное сопровождение нет",
    "бесплатно для клиентов этаЖи",
)

REQUIRED = {
    "/": (
        "условия сопровождения через «этажи» уточняются до сделки",
        "проверить условия",
    ),
    "/etagi/": (
        "состав услуги и порядок оплаты",
        "действующих условий компании",
        "уточнить условия",
    ),
    "/stoimost/": (
        "условия сопровождения определяются отдельно",
        "не совпадают автоматически с частными тарифами",
    ),
    "/faq/": (
        "до начала сопровождения нужно отдельно подтвердить",
        "предусмотрена ли дополнительная оплата",
    ),
}


def normalize(text: str) -> str:
    return " ".join(text.casefold().replace("ё", "е").split())


def error(message: str, file: Path) -> None:
    print(f"::error file={file.as_posix()}::{message}")


def built_file(site_dir: Path, page_url: str) -> Path:
    if page_url == "/":
        return site_dir / "index.html"
    return site_dir / page_url.strip("/") / "index.html"


def check_text(text: str, file: Path, page_url: str) -> int:
    normalized = normalize(text)
    errors = 0

    for phrase in FORBIDDEN:
        normalized_phrase = normalize(phrase)
        if normalized_phrase in normalized:
            error(f"Неподтверждённое обещание по условиям ЭТАЖИ на {page_url}: {phrase}", file)
            errors += 1

    for marker in REQUIRED[page_url]:
        if normalize(marker) not in normalized:
            error(f"На {page_url} отсутствует безопасная формулировка: {marker}", file)
            errors += 1

    return errors


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    errors = 0

    if not POLICY.is_file():
        error("Не найден документ правил условий ЭТАЖИ", POLICY)
        return 1

    policy_text = normalize(POLICY.read_text(encoding="utf-8", errors="ignore"))
    for marker in (
        "частная работа ипотечного брокера",
        "порядок оплаты зависит от действующих условий компании",
        "запрещенные неподтвержденные обещания",
        "страница `/etagi/` является основным источником формулировок",
    ):
        if normalize(marker) not in policy_text:
            error(f"В документе правил отсутствует маркер: {marker}", POLICY)
            errors += 1

    for page_url, source_file in PAGES.items():
        if not source_file.is_file():
            error(f"Не найден исходник ключевой страницы {page_url}", source_file)
            errors += 1
            continue

        source_text = source_file.read_text(encoding="utf-8", errors="ignore")
        errors += check_text(source_text, source_file, page_url)

        html_file = built_file(site_dir, page_url)
        if not html_file.is_file():
            error(f"Не найдена собранная страница {page_url}", html_file)
            errors += 1
            continue

        built_text = html_file.read_text(encoding="utf-8", errors="ignore")
        errors += check_text(built_text, html_file, page_url)

    if errors:
        print(f"Аудит условий ЭТАЖИ завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит условий ЭТАЖИ успешно завершён: главная, FAQ, стоимость и профильная страница "
        "не содержат неподтверждённых обещаний о бесплатности или включении в комиссию"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
