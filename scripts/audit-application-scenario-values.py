#!/usr/bin/env python3
"""Проверяет, что CTA и автоподстановка используют сценарии, существующие в онлайн-анкете."""

from __future__ import annotations

import html
import re
from pathlib import Path
from urllib.parse import unquote_plus


ROOT = Path(__file__).resolve().parents[1]
APPLICATION = ROOT / "online-zayavka.md"
APPLICATION_JS = ROOT / "assets/js/online-application.js"

SELECT_RE = re.compile(r'<select\b[^>]*\bname="scenario"[^>]*>(.*?)</select>', re.IGNORECASE | re.DOTALL)
OPTION_RE = re.compile(r'<option\b([^>]*)>(.*?)</option>', re.IGNORECASE | re.DOTALL)
VALUE_RE = re.compile(r'\bvalue="([^"]*)"', re.IGNORECASE)
TAG_RE = re.compile(r'<[^>]+>')
LIQUID_SCENARIO_RE = re.compile(r"scenario=\{\{\s*'([^']+)'\s*\|\s*url_encode\s*\}\}")
RAW_SCENARIO_RE = re.compile(r"scenario=([^\"'\s<>&]+)")
SCENARIO_MAP_RE = re.compile(r"const\s+SCENARIO_BY_SLUG\s*=\s*\{(.*?)\};", re.DOTALL)
MAP_VALUE_RE = re.compile(r":\s*'([^']+)'")


def error(path: Path, message: str) -> None:
    print(f"::error file={path.as_posix()}::{message}")


def clean_option_text(value: str) -> str:
    return " ".join(html.unescape(TAG_RE.sub("", value)).split())


def allowed_scenarios() -> set[str]:
    source = APPLICATION.read_text(encoding="utf-8", errors="ignore")
    match = SELECT_RE.search(source)
    if not match:
        raise RuntimeError('Не найден <select name="scenario"> в online-zayavka.md')

    allowed: set[str] = set()
    for attrs, body in OPTION_RE.findall(match.group(1)):
        value_match = VALUE_RE.search(attrs)
        if value_match is not None:
            value = html.unescape(value_match.group(1)).strip()
            if value:
                allowed.add(value)
            continue
        value = clean_option_text(body)
        if value:
            allowed.add(value)
    return allowed


def page_sources() -> list[Path]:
    files = [path for path in ROOT.glob("*.md") if path.name != "README.md"]
    for directory in ("polezno", "uslugi", "geo"):
        base = ROOT / directory
        if base.is_dir():
            files.extend(base.rglob("*.md"))
    return sorted(set(files))


def scenarios_from_page(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    values = {match.group(1).strip() for match in LIQUID_SCENARIO_RE.finditer(text)}
    for match in RAW_SCENARIO_RE.finditer(text):
        raw = html.unescape(match.group(1)).strip()
        if not raw or raw.startswith("{{"):
            continue
        decoded = unquote_plus(raw).strip()
        if decoded:
            values.add(decoded)
    return values


def scenarios_from_prefill_map() -> set[str]:
    text = APPLICATION_JS.read_text(encoding="utf-8", errors="ignore")
    match = SCENARIO_MAP_RE.search(text)
    if not match:
        raise RuntimeError("Не найден SCENARIO_BY_SLUG в online-application.js")
    return {value.strip() for value in MAP_VALUE_RE.findall(match.group(1)) if value.strip()}


def main() -> int:
    try:
        allowed = allowed_scenarios()
        mapped = scenarios_from_prefill_map()
    except (OSError, RuntimeError) as exc:
        error(APPLICATION, str(exc))
        return 1

    failures = 0
    checked_links = 0
    pages_with_scenarios = 0

    for path in page_sources():
        values = scenarios_from_page(path)
        if not values:
            continue
        pages_with_scenarios += 1
        checked_links += len(values)
        for value in sorted(values):
            if value not in allowed:
                error(path, f"CTA передаёт сценарий, которого нет в онлайн-анкете: {value}")
                failures += 1

    for value in sorted(mapped):
        if value not in allowed:
            error(APPLICATION_JS, f"SCENARIO_BY_SLUG ссылается на отсутствующий сценарий: {value}")
            failures += 1

    if failures:
        print(
            "Аудит сценариев онлайн-заявки завершён с ошибками: "
            f"{failures}; допустимых сценариев {len(allowed)}"
        )
        return 1

    print(
        "Сценарии онлайн-заявки согласованы: "
        f"допустимых {len(allowed)}, страниц с CTA {pages_with_scenarios}, "
        f"уникальных значений по страницам {checked_links}, автосопоставлений {len(mapped)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
