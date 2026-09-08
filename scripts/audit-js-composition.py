#!/usr/bin/env python3
"""Контролирует состав и общий вес браузерного JavaScript до сборки сайта."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS_DIR = ROOT / "assets" / "js"
BUDGET_PATH = ROOT / "scripts" / "performance-budget.json"

GROUPS = {
    "global": {
        "main.js",
    },
    "calculator": {
        "mortgage-calculator.js",
        "calculator-application-prefill.js",
        "calculator-application-prefill-runtime.js",
    },
    "application": {
        "application-delivery-keepalive.js",
        "application-inputs.js",
        "application-preparation.js",
        "online-application.js",
    },
    "thankyou": {
        "thankyou-storage-privacy.js",
    },
}


def error(message: str) -> None:
    print(f"::error::{message}")


def main() -> int:
    try:
        budget = json.loads(BUDGET_PATH.read_text(encoding="utf-8"))
        total_limit = int(budget["js_total_bytes"])
        file_limit = int(budget["max_js_bytes"])
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        error(f"Не удалось прочитать JS budget: {exc}")
        return 1

    if not JS_DIR.is_dir():
        error("Каталог assets/js не найден")
        return 1

    actual = {path.name: path for path in JS_DIR.glob("*.js") if path.is_file()}
    expected = set().union(*GROUPS.values())
    errors: list[str] = []

    missing = sorted(expected - set(actual))
    unexpected = sorted(set(actual) - expected)
    if missing:
        errors.append("Отсутствуют ожидаемые JS-модули: " + ", ".join(missing))
    if unexpected:
        errors.append(
            "Найдены новые неклассифицированные JS-модули: " + ", ".join(unexpected)
            + ". Явно добавьте их в GROUPS после проверки необходимости."
        )

    sizes = {name: path.stat().st_size for name, path in actual.items()}
    total = sum(sizes.values())

    if total > total_limit:
        errors.append(f"Общий JS: {total} байт при лимите {total_limit}")

    oversized = sorted((name, size) for name, size in sizes.items() if size > file_limit)
    for name, size in oversized:
        errors.append(f"JS-модуль {name}: {size} байт при лимите {file_limit}")

    print(f"JS composition: total {total}/{total_limit} байт; запас {total_limit - total} байт")
    for group, names in GROUPS.items():
        group_size = sum(sizes.get(name, 0) for name in names)
        modules = ", ".join(f"{name}={sizes.get(name, 0)}" for name in sorted(names))
        print(f"  {group}: {group_size} байт ({modules})")

    if errors:
        for message in errors:
            error(message)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
