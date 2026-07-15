#!/usr/bin/env python3
"""Проверяет ключевые страницы на неподтверждённые обещания по условиям «ЭТАЖИ»."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "docs/etagi-terms-policy.md"
REGIONAL_MANIFEST = ROOT / "scripts/etagi-regional-pages.json"

CORE_PAGES = {
    "/": ROOT / "index.md",
    "/etagi/": ROOT / "etagi.md",
    "/stoimost/": ROOT / "stoimost.md",
    "/faq/": ROOT / "faq.md",
    "/uslugi/": ROOT / "uslugi.md",
    "/online-zayavka/": ROOT / "online-zayavka.md",
    "/kontakty/": ROOT / "kontakty.md",
    "/o-brokere/": ROOT / "o-brokere.md",
    "/geo/": ROOT / "geo.md",
    "/geo/borisoglebsk/": ROOT / "geo/borisoglebsk.md",
    "/geo/gribanovskiy/": ROOT / "geo/gribanovskiy.md",
    "/geo/povorino/": ROOT / "geo/povorino.md",
    "/polezno/dokumenty-dlya-ipoteki/": ROOT / "polezno/dokumenty-dlya-ipoteki.md",
    "/kalkulyator-ipoteki/": ROOT / "kalkulyator-ipoteki.md",
    "/kak-prohodit-rabota/": ROOT / "kak-prohodit-rabota.md",
    "/konsultaciya/": ROOT / "konsultaciya.md",
}

SOURCE_ONLY = {
    "README.md": ROOT / "README.md",
    "humans.txt": ROOT / "humans.txt",
    "docs/README.md": ROOT / "docs/README.md",
}

FORBIDDEN = (
    "сопровождение включено в комиссию компании",
    "отдельно клиентом не оплачивается",
    "без доплаты при сделке через",
    "отдельной оплаты за ипотечное сопровождение нет",
    "бесплатно для клиентов этажи",
)

CORE_REQUIRED = {
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
    "/uslugi/": (
        "состав ипотечного сопровождения и порядок оплаты нужно подтвердить",
        "действующим условиям компании",
    ),
    "/online-zayavka/": (
        "состав услуги и порядок оплаты подтверждаются",
        "предусмотрена ли отдельная оплата",
    ),
    "/kontakty/": (
        "условия зависят от действующих тарифов компании",
        "предусмотрена ли отдельная оплата",
    ),
    "/o-brokere/": (
        "состав ипотечного сопровождения и порядок оплаты определяются",
        "подтверждаются до начала работы",
    ),
    "/geo/": (
        "состав помощи ипотечного брокера и порядок оплаты зависят",
        "предусмотрена ли отдельная оплата",
    ),
    "/geo/borisoglebsk/": (
        "состав ипотечного сопровождения и порядок оплаты зависят",
        "подтверждаются до начала работы",
    ),
    "/geo/gribanovskiy/": (
        "условия сопровождения подтверждаются до начала работы",
        "предусмотрена ли отдельная оплата",
    ),
    "/geo/povorino/": (
        "условия сопровождения подтверждаются до начала работы",
        "предусмотрена ли отдельная оплата",
    ),
    "/polezno/dokumenty-dlya-ipoteki/": (
        "состав ипотечного сопровождения, перечень документов и порядок оплаты зависят",
        "предусмотрена ли отдельная оплата",
    ),
    "/kalkulyator-ipoteki/": (
        "условия сопровождения уточняются до начала работы",
        "порядок оплаты зависят от действующих условий компании",
    ),
    "/kak-prohodit-rabota/": (
        "состав сопровождения и порядок оплаты подтверждаются",
        "возможная дополнительная стоимость",
    ),
    "/konsultaciya/": (
        "условия ипотечного сопровождения подтверждаются отдельно",
        "не означает, что любое дальнейшее сопровождение предоставляется без отдельной оплаты",
        "действующих условий компании",
    ),
}

SAFE_REGIONAL_REQUIRED = (
    "состав ипотечного сопровождения и порядок оплаты зависят",
    "предусмотрена ли отдельная оплата",
)

SOURCE_REQUIRED = {
    "README.md": (
        "состав ипотечного сопровождения и порядок оплаты зависят",
        "подтверждаются до начала работы",
    ),
    "humans.txt": (
        "состав ипотечного сопровождения и порядок оплаты подтверждаются",
        "до начала работы",
    ),
    "docs/README.md": (
        "не обещать, что ипотечное сопровождение",
        "подтверждаются до начала работы",
        "scripts/audit-etagi-terms.py",
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


def check_forbidden(text: str, file: Path, label: str) -> int:
    normalized = normalize(text)
    errors = 0
    for phrase in FORBIDDEN:
        if normalize(phrase) in normalized:
            error(f"Неподтверждённое обещание по условиям ЭТАЖИ в {label}: {phrase}", file)
            errors += 1
    return errors


def check_text(
    text: str,
    file: Path,
    page_url: str,
    required_markers: tuple[str, ...],
) -> int:
    normalized = normalize(text)
    errors = check_forbidden(text, file, page_url)

    for marker in required_markers:
        if normalize(marker) not in normalized:
            error(f"На {page_url} отсутствует безопасная формулировка: {marker}", file)
            errors += 1

    return errors


def load_regional_pages() -> tuple[dict[str, Path], dict[str, Path], int]:
    if not REGIONAL_MANIFEST.is_file():
        error("Не найден manifest региональных страниц", REGIONAL_MANIFEST)
        return {}, {}, 1

    try:
        payload = json.loads(REGIONAL_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        error(f"Не удалось прочитать manifest региональных страниц: {exc}", REGIONAL_MANIFEST)
        return {}, {}, 1

    errors = 0
    groups: dict[str, dict[str, Path]] = {"safe": {}, "reviewed": {}}

    for group_name in groups:
        raw_group = payload.get(group_name)
        if not isinstance(raw_group, dict):
            error(f"В manifest отсутствует объект {group_name}", REGIONAL_MANIFEST)
            errors += 1
            continue

        for page_url, relative_path in raw_group.items():
            if not isinstance(page_url, str) or not page_url.startswith("/") or not page_url.endswith("/"):
                error(f"Некорректный URL в группе {group_name}: {page_url!r}", REGIONAL_MANIFEST)
                errors += 1
                continue
            if not isinstance(relative_path, str) or not relative_path.endswith(".md"):
                error(f"Некорректный путь для {page_url}: {relative_path!r}", REGIONAL_MANIFEST)
                errors += 1
                continue

            source_file = (ROOT / relative_path).resolve()
            if not source_file.is_relative_to(ROOT):
                error(f"Путь выходит за пределы репозитория: {relative_path}", REGIONAL_MANIFEST)
                errors += 1
                continue
            groups[group_name][page_url] = source_file

    overlap = set(groups["safe"]) & set(groups["reviewed"])
    for page_url in sorted(overlap):
        error(f"Региональная страница одновременно safe и reviewed: {page_url}", REGIONAL_MANIFEST)
        errors += 1

    return groups["safe"], groups["reviewed"], errors


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    errors = 0

    if not POLICY.is_file():
        error("Не найден документ правил условий ЭТАЖИ", POLICY)
        return 1

    safe_pages, reviewed_pages, manifest_errors = load_regional_pages()
    errors += manifest_errors

    pages = dict(CORE_PAGES)
    pages.update(safe_pages)
    pages.update(reviewed_pages)

    required = dict(CORE_REQUIRED)
    required.update({page_url: SAFE_REGIONAL_REQUIRED for page_url in safe_pages})
    required.update({page_url: () for page_url in reviewed_pages})

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

    for page_url, source_file in pages.items():
        if not source_file.is_file():
            error(f"Не найден исходник ключевой страницы {page_url}", source_file)
            errors += 1
            continue

        source_text = source_file.read_text(encoding="utf-8", errors="ignore")
        errors += check_text(source_text, source_file, page_url, required[page_url])

        html_file = built_file(site_dir, page_url)
        if not html_file.is_file():
            error(f"Не найдена собранная страница {page_url}", html_file)
            errors += 1
            continue

        built_text = html_file.read_text(encoding="utf-8", errors="ignore")
        errors += check_text(built_text, html_file, page_url, required[page_url])

    for label, source_file in SOURCE_ONLY.items():
        if not source_file.is_file():
            error(f"Не найден обязательный публичный документ {label}", source_file)
            errors += 1
            continue

        source_text = source_file.read_text(encoding="utf-8", errors="ignore")
        normalized = normalize(source_text)
        errors += check_forbidden(source_text, source_file, label)
        for marker in SOURCE_REQUIRED[label]:
            if normalize(marker) not in normalized:
                error(f"В {label} отсутствует безопасная формулировка: {marker}", source_file)
                errors += 1

    if errors:
        print(f"Аудит условий ЭТАЖИ завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит условий ЭТАЖИ успешно завершён: "
        f"{len(pages)} ключевых страниц, включая {len(safe_pages)} дочерних региональных "
        f"маршрутов с безопасной формулировкой и {len(reviewed_pages)} проверенных маршрутов "
        "без корпоративного блока, а также три публичных документа, не содержат неподтверждённых обещаний"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
