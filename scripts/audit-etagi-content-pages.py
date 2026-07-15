#!/usr/bin/env python3
"""Проверяет материалы «Полезно» из manifest на безопасные условия «ЭТАЖИ»."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scripts/etagi-content-pages.json"
GROUPS = ("safe", "reviewed")

FORBIDDEN = (
    "ипотечное сопровождение включено в комиссию",
    "сопровождение включено в комиссию компании",
    "работа ипотечного брокера отдельно клиентом не оплачивается",
    "отдельно клиентом не оплачивается",
    "без доплаты при сделке через",
    "отдельной оплаты за ипотечное сопровождение нет",
    "бесплатно для клиентов этажи",
)

SAFE_REQUIRED = (
    "состав ипотечного сопровождения",
    "порядок оплаты зависят",
    "предусмотрена ли отдельная оплата",
)


def normalize(text: str) -> str:
    return " ".join(text.casefold().replace("ё", "е").split())


def error(message: str, file: Path) -> None:
    print(f"::error file={file.as_posix()}::{message}")


def built_file(site_dir: Path, page_url: str) -> Path:
    return site_dir / page_url.strip("/") / "index.html"


def read_manifest() -> tuple[dict[str, dict[str, Path]], int]:
    if not MANIFEST.is_file():
        error("Не найден manifest полезных материалов", MANIFEST)
        return {group: {} for group in GROUPS}, 1

    try:
        payload: Any = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        error(f"Не удалось прочитать manifest: {exc}", MANIFEST)
        return {group: {} for group in GROUPS}, 1

    if not isinstance(payload, dict):
        error("Корень manifest должен быть JSON-объектом", MANIFEST)
        return {group: {} for group in GROUPS}, 1

    errors = 0
    unknown_groups = set(payload) - set(GROUPS)
    for group_name in sorted(unknown_groups):
        error(f"Неизвестная группа manifest: {group_name}", MANIFEST)
        errors += 1

    groups: dict[str, dict[str, Path]] = {group: {} for group in GROUPS}
    seen_paths: dict[Path, str] = {}

    for group_name in GROUPS:
        raw_group = payload.get(group_name)
        if not isinstance(raw_group, dict):
            error(f"В manifest отсутствует объект {group_name}", MANIFEST)
            errors += 1
            continue

        for page_url, relative_path in raw_group.items():
            if (
                not isinstance(page_url, str)
                or not page_url.startswith("/polezno/")
                or not page_url.endswith("/")
            ):
                error(f"Некорректный URL в группе {group_name}: {page_url!r}", MANIFEST)
                errors += 1
                continue

            if not isinstance(relative_path, str) or not relative_path.startswith("polezno/") or not relative_path.endswith(".md"):
                error(f"Некорректный путь для {page_url}: {relative_path!r}", MANIFEST)
                errors += 1
                continue

            source_file = (ROOT / relative_path).resolve()
            if not source_file.is_relative_to(ROOT):
                error(f"Путь выходит за пределы репозитория: {relative_path}", MANIFEST)
                errors += 1
                continue

            previous_url = seen_paths.get(source_file)
            if previous_url is not None:
                error(f"Файл {relative_path} повторно назначен маршруту {page_url}; ранее {previous_url}", MANIFEST)
                errors += 1
                continue

            seen_paths[source_file] = page_url
            groups[group_name][page_url] = source_file

    overlap = set(groups["safe"]) & set(groups["reviewed"])
    for page_url in sorted(overlap):
        error(f"Маршрут одновременно safe и reviewed: {page_url}", MANIFEST)
        errors += 1

    if not groups["safe"]:
        error("Группа safe не должна быть пустой", MANIFEST)
        errors += 1

    return groups, errors


def check_text(text: str, file: Path, page_url: str, require_safe: bool) -> int:
    normalized = normalize(text)
    errors = 0

    for phrase in FORBIDDEN:
        if normalize(phrase) in normalized:
            error(f"Неподтверждённое обещание по условиям ЭТАЖИ на {page_url}: {phrase}", file)
            errors += 1

    if require_safe:
        for marker in SAFE_REQUIRED:
            if normalize(marker) not in normalized:
                error(f"На {page_url} отсутствует безопасный маркер: {marker}", file)
                errors += 1

    return errors


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    groups, errors = read_manifest()

    for group_name in GROUPS:
        for page_url, source_file in groups[group_name].items():
            if not source_file.is_file():
                error(f"Не найден исходник {page_url}", source_file)
                errors += 1
                continue

            source_text = source_file.read_text(encoding="utf-8", errors="ignore")
            errors += check_text(source_text, source_file, page_url, group_name == "safe")

            html_file = built_file(site_dir, page_url)
            if not html_file.is_file():
                error(f"Не найдена собранная страница {page_url}", html_file)
                errors += 1
                continue

            built_text = html_file.read_text(encoding="utf-8", errors="ignore")
            errors += check_text(built_text, html_file, page_url, group_name == "safe")

    if errors:
        print(f"Аудит полезных материалов ЭТАЖИ завершён с ошибками: {errors}")
        return 1

    print(
        "Аудит полезных материалов ЭТАЖИ успешно завершён: "
        f"{len(groups['safe'])} страниц с безопасными условиями и "
        f"{len(groups['reviewed'])} проверенных страниц без корпоративного блока"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
