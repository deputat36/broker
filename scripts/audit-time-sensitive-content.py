#!/usr/bin/env python3
"""Блокирует быстро устаревающие ставки, проценты и сроки программ.

По умолчанию числовые ипотечные условия запрещены в клиентском контенте.
Временное исключение возможно только через проверяемый allowlist с HTTPS-источником,
датой проверки и коротким сроком действия.
"""

from __future__ import annotations

import html
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = ROOT / "scripts/time-sensitive-content-allowlist.json"
CLIENT_DIRS = ("uslugi", "geo", "polezno")
EXCLUDED_ROOT_MARKDOWN = {"README.md"}
MONTHS = (
    "января|февраля|марта|апреля|мая|июня|июля|августа|"
    "сентября|октября|ноября|декабря"
)
CONTEXT = r"ипотек\w*|банк\w*|программ\w*|услови\w*|ставк\w*|взнос\w*|субсиди\w*"
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "числовой процент",
        re.compile(r"(?<![\w/])\d{1,3}(?:[.,]\d{1,2})?\s*%", re.IGNORECASE),
    ),
    (
        "числовая ставка без знака процента",
        re.compile(
            r"(?:ставк\w*|процент\w*)\s*(?:—|:|от|до)?\s*\d{1,2}(?:[.,]\d{1,2})?",
            re.IGNORECASE,
        ),
    ),
    (
        "дата окончания программы",
        re.compile(
            rf"(?:{CONTEXT})[^.\n]{{0,100}}(?:до|по)\s+\d{{1,2}}\s+(?:{MONTHS})\s+20\d{{2}}",
            re.IGNORECASE,
        ),
    ),
    (
        "год, привязанный к банковской программе",
        re.compile(
            rf"(?:{CONTEXT})[^.\n]{{0,100}}\b20(?:2[4-9]|3\d)\b|"
            rf"\b20(?:2[4-9]|3\d)\b[^.\n]{{0,100}}(?:{CONTEXT})",
            re.IGNORECASE,
        ),
    ),
    (
        "явный срок действия",
        re.compile(
            rf"(?:действует|продлен\w*|доступн\w*|заверша\w*|срок\w*)"
            rf"[^.\n]{{0,60}}(?:до|по)\s+(?:\d{{1,2}}\s+(?:{MONTHS})\s+)?20\d{{2}}",
            re.IGNORECASE,
        ),
    ),
)
SCRIPT_STYLE_RE = re.compile(r"(?is)<(script|style)\b.*?</\1>")
COMMENT_RE = re.compile(r"(?s)<!--.*?-->")
TAG_RE = re.compile(r"(?s)<[^>]+>")
FENCE_RE = re.compile(r"(?ms)^```.*?^```\s*$|^~~~.*?^~~~\s*$")
SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class AllowEntry:
    source_path: str
    public_text: str
    verified_on: date
    expires_on: date
    source_url: str
    note: str


@dataclass(frozen=True)
class Finding:
    label: str
    matched: str
    snippet: str


def error(message: str, path: Path | None = None) -> None:
    prefix = "::error"
    if path is not None:
        try:
            display = path.relative_to(ROOT).as_posix()
        except ValueError:
            display = path.as_posix()
        prefix += f" file={display}"
    print(f"{prefix}::{message}")


def normalize(text: str) -> str:
    return SPACE_RE.sub(" ", text).strip()


def client_markdown_files() -> list[Path]:
    files = [
        path
        for path in ROOT.glob("*.md")
        if path.name not in EXCLUDED_ROOT_MARKDOWN
    ]
    for directory in CLIENT_DIRS:
        files.extend((ROOT / directory).rglob("*.md"))
    return sorted(set(files))


def source_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    return normalize(FENCE_RE.sub(" ", text))


def html_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    text = SCRIPT_STYLE_RE.sub(" ", text)
    text = COMMENT_RE.sub(" ", text)
    text = TAG_RE.sub(" ", text)
    return normalize(html.unescape(text))


def parse_iso_date(value: object, field: str, manifest: Path, index: int) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        error(f"Allowlist entry {index}: {field} должен быть датой YYYY-MM-DD", manifest)
        return None


def load_allowlist(today: date) -> tuple[list[AllowEntry], int]:
    if not ALLOWLIST.is_file():
        error("Не найден allowlist временных условий", ALLOWLIST)
        return [], 1

    try:
        payload = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        error(f"Allowlist не является валидным JSON: {exc}", ALLOWLIST)
        return [], 1

    errors = 0
    if payload.get("version") != 1:
        error("Allowlist должен иметь version: 1", ALLOWLIST)
        errors += 1

    max_days = payload.get("max_validity_days")
    if not isinstance(max_days, int) or not 1 <= max_days <= 60:
        error("max_validity_days должен быть целым числом от 1 до 60", ALLOWLIST)
        errors += 1
        max_days = 45

    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list):
        error("entries должен быть массивом", ALLOWLIST)
        return [], errors + 1

    entries: list[AllowEntry] = []
    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(raw_entries, start=1):
        if not isinstance(raw, dict):
            error(f"Allowlist entry {index} должен быть объектом", ALLOWLIST)
            errors += 1
            continue

        source_path = str(raw.get("source_path", "")).strip()
        public_text = normalize(str(raw.get("public_text", "")))
        source_url = str(raw.get("source_url", "")).strip()
        note = str(raw.get("note", "")).strip()
        verified_on = parse_iso_date(raw.get("verified_on"), "verified_on", ALLOWLIST, index)
        expires_on = parse_iso_date(raw.get("expires_on"), "expires_on", ALLOWLIST, index)

        key = (source_path, public_text.casefold())
        if key in seen:
            error(f"Allowlist entry {index} дублирует source_path/public_text", ALLOWLIST)
            errors += 1
        seen.add(key)

        source = (ROOT / source_path).resolve()
        try:
            source.relative_to(ROOT)
        except ValueError:
            error(f"Allowlist entry {index}: source_path выходит за пределы репозитория", ALLOWLIST)
            errors += 1
            continue
        if not source.is_file() or source.suffix.lower() != ".md":
            error(f"Allowlist entry {index}: source_path не указывает на Markdown-файл", ALLOWLIST)
            errors += 1
        if not public_text or len(public_text) < 8:
            error(f"Allowlist entry {index}: public_text слишком короткий", ALLOWLIST)
            errors += 1
        elif source.is_file() and public_text.casefold() not in source_text(source).casefold():
            error(f"Allowlist entry {index}: public_text отсутствует в source_path", ALLOWLIST)
            errors += 1
        if not source_url.startswith("https://"):
            error(f"Allowlist entry {index}: source_url должен использовать HTTPS", ALLOWLIST)
            errors += 1
        if len(note) < 10:
            error(f"Allowlist entry {index}: note должен объяснять необходимость публикации", ALLOWLIST)
            errors += 1

        if verified_on and expires_on:
            validity = (expires_on - verified_on).days
            if verified_on > today:
                error(f"Allowlist entry {index}: verified_on находится в будущем", ALLOWLIST)
                errors += 1
            if expires_on < today:
                error(f"Allowlist entry {index}: исключение просрочено {expires_on.isoformat()}", ALLOWLIST)
                errors += 1
            if validity < 0 or validity > max_days:
                error(
                    f"Allowlist entry {index}: срок действия должен быть от 0 до {max_days} дней",
                    ALLOWLIST,
                )
                errors += 1

        if verified_on and expires_on:
            entries.append(
                AllowEntry(
                    source_path=source_path,
                    public_text=public_text,
                    verified_on=verified_on,
                    expires_on=expires_on,
                    source_url=source_url,
                    note=note,
                )
            )

    return entries, errors


def findings(text: str) -> list[Finding]:
    result: list[Finding] = []
    for label, pattern in PATTERNS:
        for match in pattern.finditer(text):
            start = max(0, match.start() - 90)
            end = min(len(text), match.end() + 90)
            result.append(
                Finding(
                    label=label,
                    matched=normalize(match.group(0)),
                    snippet=normalize(text[start:end]),
                )
            )
    return result


def allowed_source(path: Path, finding: Finding, entries: list[AllowEntry]) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    snippet_cf = finding.snippet.casefold()
    matched_cf = finding.matched.casefold()
    for entry in entries:
        text_cf = entry.public_text.casefold()
        if entry.source_path == relative and (matched_cf in text_cf or text_cf in snippet_cf):
            return True
    return False


def allowed_built(finding: Finding, entries: list[AllowEntry]) -> bool:
    snippet_cf = finding.snippet.casefold()
    matched_cf = finding.matched.casefold()
    return any(
        matched_cf in entry.public_text.casefold()
        or entry.public_text.casefold() in snippet_cf
        for entry in entries
    )


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    if not site_dir.is_dir():
        error("Каталог собранного сайта не найден", site_dir)
        return 1

    today = date.today()
    entries, errors = load_allowlist(today)
    source_count = 0
    built_count = 0

    source_files = client_markdown_files()
    for path in source_files:
        for finding in findings(source_text(path)):
            if allowed_source(path, finding, entries):
                continue
            error(
                f"Найдено временное условие без действующего источника: {finding.label}; "
                f"фрагмент: {finding.snippet[:240]}",
                path,
            )
            errors += 1
            source_count += 1

    html_files = sorted(site_dir.rglob("*.html"))
    for path in html_files:
        for finding in findings(html_text(path)):
            if allowed_built(finding, entries):
                continue
            error(
                f"В собранном HTML найдено временное условие без allowlist: {finding.label}; "
                f"фрагмент: {finding.snippet[:240]}",
                path,
            )
            errors += 1
            built_count += 1

    if errors:
        print(
            "Аудит временных условий завершён с ошибками: "
            f"{errors}; source findings {source_count}; built findings {built_count}"
        )
        return 1

    print(
        "Аудит временных условий успешно завершён: "
        f"Markdown-файлов {len(source_files)}, HTML-страниц {len(html_files)}, "
        f"действующих исключений {len(entries)}, неподтверждённых ставок и сроков 0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
