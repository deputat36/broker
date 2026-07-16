#!/usr/bin/env python3
"""Проверяет согласованность публичного раскрытия и privacy-контракта атрибуции."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_POLICY = ROOT / "policy.md"
MAIN_JS = ROOT / "assets/js/main.js"
TECHNICAL_DOC = ROOT / "docs/tracking-attribution-privacy.md"
POST_BUILD = ROOT / "scripts/post-build-check.sh"


def fail(path: Path, message: str) -> None:
    print(f"::error file={path.as_posix()}::{message}")


def require(text: str, markers: tuple[str, ...], path: Path, label: str) -> int:
    errors = 0
    for marker in markers:
        if marker not in text:
            fail(path, f"{label}: отсутствует маркер {marker}")
            errors += 1
    return errors


def forbid(text: str, markers: tuple[str, ...], path: Path, label: str) -> int:
    errors = 0
    for marker in markers:
        if marker in text:
            fail(path, f"{label}: найден устаревший или запрещённый маркер {marker}")
            errors += 1
    return errors


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    built_policy = site_dir / "policy/index.html"
    required_files = (SOURCE_POLICY, MAIN_JS, TECHNICAL_DOC, POST_BUILD, built_policy)
    errors = 0

    for path in required_files:
        if not path.is_file() or path.stat().st_size == 0:
            fail(path, "Обязательный файл отсутствует или пуст")
            errors += 1
    if errors:
        return 1

    source_policy = SOURCE_POLICY.read_text(encoding="utf-8")
    built = built_policy.read_text(encoding="utf-8-sig", errors="ignore")
    main_js = MAIN_JS.read_text(encoding="utf-8")
    documentation = TECHNICAL_DOC.read_text(encoding="utf-8")
    post_build = POST_BUILD.read_text(encoding="utf-8")

    disclosure_markers = (
        "без query-параметров и fragment",
        "Для внешнего сайта сохраняется только origin",
        "Произвольные параметры URL не записываются в локальную атрибуцию",
        "Legacy-запись",
        "искусственно завышенный срок",
        "не отменяет сведения, которые пользователь отдельно проверил и уже отправил",
        "sterlikovaMortgageTracking",
        "sterlikovaMortgageLastLead",
    )
    errors += require(source_policy, disclosure_markers, SOURCE_POLICY, "Исходная политика")
    errors += require(built, disclosure_markers, built_policy, "Собранная политика")

    outdated_markers = (
        "страницу входа, referrer и страницу перед открытием формы",
        "Запись получает техническое поле <code>expires_at</code>",
    )
    errors += forbid(source_policy, outdated_markers, SOURCE_POLICY, "Исходная политика")
    errors += forbid(built, outdated_markers, built_policy, "Собранная политика")

    implementation_markers = (
        "const TRACKING_STORAGE_VERSION = 2;",
        "url.search = '';",
        "url.hash = '';",
        "options.externalOriginOnly",
        "stored.storage_version !== TRACKING_STORAGE_VERSION",
        "expiresAt > storedAt + TRACKING_RETENTION_MS + TRACKING_CLOCK_SKEW_MS",
        "window.getSiteSafePageContext = getSafePageContext;",
    )
    errors += require(main_js, implementation_markers, MAIN_JS, "Реализация атрибуции")
    errors += forbid(
        main_js,
        ("page_url: window.location.href", "referrer: document.referrer || ''"),
        MAIN_JS,
        "Реализация атрибуции",
    )

    documentation_markers = (
        "storage_version: 2",
        "Query-параметры, fragment, credentials URL",
        "Fail-closed чтение",
        "node scripts/test-tracking-privacy.js assets/js/main.js",
        "Pages-артефакта",
    )
    errors += require(documentation, documentation_markers, TECHNICAL_DOC, "Техническая документация")

    audit_command = 'python3 scripts/audit-tracking-privacy-disclosure.py "$SITE_DIR"'
    if audit_command not in post_build:
        fail(POST_BUILD, "Аудит раскрытия privacy не подключён к post-build")
        errors += 1

    if errors:
        print(f"Аудит раскрытия privacy атрибуции завершён с ошибками: {errors}")
        return 1

    print("Раскрытие privacy атрибуции согласовано с main.js и готовой страницей /policy/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
