#!/usr/bin/env python3
"""Проверяет атрибуцию переходов с главной страницы в онлайн-заявку."""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_HOME = ROOT / "index.md"
TRACKING_JS = ROOT / "assets" / "js" / "main.js"
APPLICATION_JS = ROOT / "assets" / "js" / "online-application.js"

REQUIRED_PLACEMENTS = (
    "home_hero_primary",
    "home_quick_route",
    "home_calc_intro",
    "home_intent_online",
    "home_search_cloud",
    "home_complex_inline",
    "home_trust_panel",
    "home_services_footer",
    "home_geography_online",
    "home_prices_intro",
    "home_useful_footer",
    "home_final_cta",
)

GENERIC_SCENARIO = "%D0%9F%D0%B5%D1%80%D0%B2%D0%B8%D1%87%D0%BD%D0%B0%D1%8F%20%D0%BA%D0%BE%D0%BD%D1%81%D1%83%D0%BB%D1%8C%D1%82%D0%B0%D1%86%D0%B8%D1%8F%20%D0%B8%20%D0%BF%D0%BE%D0%B4%D0%B1%D0%BE%D1%80%20%D0%B8%D0%BF%D0%BE%D1%82%D0%B5%D0%BA%D0%B8"
COMPLEX_SCENARIO = "%D0%94%D1%80%D1%83%D0%B3%D0%B0%D1%8F%20%D1%81%D0%B8%D1%82%D1%83%D0%B0%D1%86%D0%B8%D1%8F"
FORBIDDEN_INTERNAL_ATTRIBUTION = (
    "utm_source=site",
    "utm_medium=internal",
    "lead_source=homepage",
)


def display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def fail(path: Path, message: str) -> None:
    print(f"::error file={display_path(path)}::{message}")


def read_text(path: Path) -> str:
    if not path.is_file():
        fail(path, "Файл отсутствует")
        return ""
    return html.unescape(path.read_text(encoding="utf-8"))


def application_hrefs(content: str) -> list[str]:
    return re.findall(r'href="([^"]*?/online-zayavka/[^"]*)"', content)


def validate_home(path: Path, built: bool = False) -> int:
    content = read_text(path)
    if not content:
        return 1

    errors = 0
    hrefs = application_hrefs(content)

    if len(hrefs) != len(REQUIRED_PLACEMENTS):
        fail(
            path,
            f"Ожидалось {len(REQUIRED_PLACEMENTS)} размеченных ссылок на заявку, найдено {len(hrefs)}",
        )
        errors += 1

    for placement in REQUIRED_PLACEMENTS:
        token = f"placement={placement}"
        count = content.count(token)
        if count != 1:
            fail(path, f"Маркер {token} должен встречаться один раз, найдено {count}")
            errors += 1

    for href in hrefs:
        if "source=%2F" not in href:
            fail(path, f"Ссылка не передаёт source главной: {href}")
            errors += 1
        if "scenario=" not in href:
            fail(path, f"Ссылка не передаёт сценарий формы: {href}")
            errors += 1
        if "placement=home_" not in href:
            fail(path, f"Ссылка не передаёт placement главной: {href}")
            errors += 1

    complex_link = next((href for href in hrefs if "placement=home_complex_inline" in href), "")
    if COMPLEX_SCENARIO not in complex_link:
        fail(path, "CTA сложной ситуации должен предзаполнять сценарий «Другая ситуация»")
        errors += 1

    generic_hrefs = [href for href in hrefs if "placement=home_complex_inline" not in href]
    for href in generic_hrefs:
        if GENERIC_SCENARIO not in href:
            fail(path, f"Общий CTA не предзаполняет первичную консультацию: {href}")
            errors += 1

    lowered = content.lower()
    for marker in FORBIDDEN_INTERNAL_ATTRIBUTION:
        if marker in lowered:
            fail(path, f"Внутренний переход не должен перезаписывать рекламную атрибуцию: {marker}")
            errors += 1

    if built and "Татьяна Стерликова" not in content:
        fail(path, "Собранная главная не содержит имя брокера")
        errors += 1

    return errors


def validate_runtime() -> int:
    errors = 0
    tracking = read_text(TRACKING_JS)
    application = read_text(APPLICATION_JS)

    if "'placement'" not in tracking and '"placement"' not in tracking:
        fail(TRACKING_JS, "placement отсутствует в allowlist параметров атрибуции")
        errors += 1

    required_application_markers = (
        "new URLSearchParams(window.location.search)",
        "params.get('scenario')",
        "params.get('source')",
        "tracking_json: JSON.stringify(tracking)",
    )
    for marker in required_application_markers:
        if marker not in application:
            fail(APPLICATION_JS, f"Форма не сохраняет необходимый контекст: {marker}")
            errors += 1

    return errors


def main() -> int:
    site_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site"
    if not site_dir.is_absolute():
        site_dir = ROOT / site_dir

    errors = validate_home(SOURCE_HOME)
    errors += validate_home(site_dir / "index.html", built=True)
    errors += validate_runtime()

    if errors:
        print(f"Аудит маршрутов главной завершён с ошибками: {errors}")
        return 1

    print(
        "Маршруты главной проверены: "
        f"{len(REQUIRED_PLACEMENTS)} CTA передают source, scenario и placement без подмены UTM"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
