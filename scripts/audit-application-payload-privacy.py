#!/usr/bin/env python3
"""Проверяет, что явный payload заявки не передаёт сырые URL и referrer."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_APP = ROOT / "assets/js/online-application.js"
MAIN_JS = ROOT / "assets/js/main.js"
SOURCE_POLICY = ROOT / "policy.md"
TECHNICAL_DOC = ROOT / "docs/application-payload-privacy.md"
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
            fail(path, f"{label}: найден запрещённый маркер {marker}")
            errors += 1
    return errors


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    built_app = site_dir / "assets/js/online-application.js"
    built_policy = site_dir / "policy/index.html"
    required_files = (
        SOURCE_APP,
        MAIN_JS,
        SOURCE_POLICY,
        TECHNICAL_DOC,
        POST_BUILD,
        built_app,
        built_policy,
    )
    errors = 0

    for path in required_files:
        if not path.is_file() or path.stat().st_size == 0:
            fail(path, "Обязательный файл отсутствует или пуст")
            errors += 1
    if errors:
        return 1

    source_app = SOURCE_APP.read_text(encoding="utf-8")
    built_app_text = built_app.read_text(encoding="utf-8-sig", errors="ignore")
    main_js = MAIN_JS.read_text(encoding="utf-8")
    source_policy = SOURCE_POLICY.read_text(encoding="utf-8")
    built_policy_text = built_policy.read_text(encoding="utf-8-sig", errors="ignore")
    documentation = TECHNICAL_DOC.read_text(encoding="utf-8")
    post_build = POST_BUILD.read_text(encoding="utf-8")

    implementation_markers = (
        "function getSafePageContext()",
        "window.getSiteSafePageContext",
        "const pageContext = getSafePageContext();",
        "page_url: pageContext.page_url",
        "referrer: pageContext.referrer",
        "utm_source: current.utm_source || ''",
        "utm_medium: current.utm_medium || ''",
        "tracking_json: JSON.stringify(tracking)",
        "fields_json: JSON.stringify(payload, null, 2)",
    )
    forbidden_markers = (
        "page_url: window.location.href",
        "referrer: document.referrer || ''",
    )
    errors += require(source_app, implementation_markers, SOURCE_APP, "Исходный payload")
    errors += require(built_app_text, implementation_markers, built_app, "Собранный payload")
    errors += forbid(source_app, forbidden_markers, SOURCE_APP, "Исходный payload")
    errors += forbid(built_app_text, forbidden_markers, built_app, "Собранный payload")

    main_markers = (
        "function getSafePageContext()",
        "window.getSiteSafePageContext = getSafePageContext;",
        "url.search = '';",
        "url.hash = '';",
        "options.externalOriginOnly",
    )
    errors += require(main_js, main_markers, MAIN_JS, "Общий safe context")

    policy_markers = (
        "страница обращения без query-параметров и fragment",
        "В технический контекст заявки передаётся безопасный адрес текущей страницы",
        "Внутренний referrer сокращается до origin и пути, внешний — до origin",
        "UTM-метки и рекламные click-id передаются отдельно только по фиксированному списку",
    )
    errors += require(source_policy, policy_markers, SOURCE_POLICY, "Исходная политика")
    errors += require(built_policy_text, policy_markers, built_policy, "Собранная политика")

    documentation_markers = (
        "Явный payload онлайн-заявки",
        "getSiteSafePageContext",
        "Fail-closed fallback",
        "audit-application-payload-privacy.py",
        "Pages-артефакта",
    )
    errors += require(documentation, documentation_markers, TECHNICAL_DOC, "Документация")

    audit_command = 'python3 scripts/audit-application-payload-privacy.py "$SITE_DIR"'
    if audit_command not in post_build:
        fail(POST_BUILD, "Аудит privacy payload не подключён к post-build")
        errors += 1

    if errors:
        print(f"Аудит privacy payload заявки завершён с ошибками: {errors}")
        return 1

    print("Privacy payload заявки подтверждён: raw URL/referrer исключены, UTM allowlist сохранён")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
