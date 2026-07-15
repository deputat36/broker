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
    "/uslugi/": ROOT / "uslugi.md",
    "/online-zayavka/": ROOT / "online-zayavka.md",
    "/kontakty/": ROOT / "kontakty.md",
    "/o-brokere/": ROOT / "o-brokere.md",
    "/geo/": ROOT / "geo.md",
    "/geo/borisoglebsk/": ROOT / "geo/borisoglebsk.md",
    "/geo/gribanovskiy/": ROOT / "geo/gribanovskiy.md",
    "/geo/povorino/": ROOT / "geo/povorino.md",
    "/kalkulyator-ipoteki/": ROOT / "kalkulyator-ipoteki.md",
    "/kak-prohodit-rabota/": ROOT / "kak-prohodit-rabota.md",
    "/konsultaciya/": ROOT / "konsultaciya.md",
}

REGIONAL_SAFE_PAGES = {
    "/geo/borisoglebsk/ipoteka-na-stroitelstvo-doma/": ROOT / "geo/borisoglebsk/ipoteka-na-stroitelstvo-doma.md",
    "/geo/gribanovskiy/ipoteka-na-stroitelstvo-doma/": ROOT / "geo/gribanovskiy/ipoteka-na-stroitelstvo-doma.md",
    "/geo/povorino/ipoteka-na-stroitelstvo-doma/": ROOT / "geo/povorino/ipoteka-na-stroitelstvo-doma.md",
    "/geo/borisoglebsk/semeynaya-ipoteka/": ROOT / "geo/borisoglebsk/semeynaya-ipoteka.md",
    "/geo/gribanovskiy/semeynaya-ipoteka/": ROOT / "geo/gribanovskiy/semeynaya-ipoteka.md",
    "/geo/povorino/semeynaya-ipoteka/": ROOT / "geo/povorino/semeynaya-ipoteka.md",
    "/geo/borisoglebsk/ipoteka-s-materinskim-kapitalom/": ROOT / "geo/borisoglebsk/ipoteka-s-materinskim-kapitalom.md",
    "/geo/gribanovskiy/ipoteka-s-materinskim-kapitalom/": ROOT / "geo/gribanovskiy/ipoteka-s-materinskim-kapitalom.md",
    "/geo/povorino/ipoteka-s-materinskim-kapitalom/": ROOT / "geo/povorino/ipoteka-s-materinskim-kapitalom.md",
    "/geo/gribanovskiy/ipoteka-na-dom/": ROOT / "geo/gribanovskiy/ipoteka-na-dom.md",
    "/geo/povorino/ipoteka-na-dom/": ROOT / "geo/povorino/ipoteka-na-dom.md",
}

REGIONAL_REVIEWED_PAGES = {
    "/geo/borisoglebsk/ipoteka-na-dom/": ROOT / "geo/borisoglebsk-ipoteka-na-dom.md",
}

PAGES.update(REGIONAL_SAFE_PAGES)
PAGES.update(REGIONAL_REVIEWED_PAGES)

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

for page_url in REGIONAL_SAFE_PAGES:
    REQUIRED[page_url] = (
        "состав ипотечного сопровождения и порядок оплаты зависят",
        "предусмотрена ли отдельная оплата",
    )

for page_url in REGIONAL_REVIEWED_PAGES:
    REQUIRED[page_url] = ()

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


def check_text(text: str, file: Path, page_url: str) -> int:
    normalized = normalize(text)
    errors = check_forbidden(text, file, page_url)

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
        f"{len(PAGES)} ключевых страниц, включая {len(REGIONAL_SAFE_PAGES)} дочерних региональных "
        f"маршрутов с безопасной формулировкой и {len(REGIONAL_REVIEWED_PAGES)} проверенных маршрутов "
        "без корпоративного блока, а также три публичных документа, не содержат неподтверждённых обещаний"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
