#!/usr/bin/env python3
"""Проверяет безопасный резерв онлайн-заявки при сбое JavaScript."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


PHONE = "+79030250807"
VK_URL = "https://vk.com/tatyanasterlikova"


def fail(path: Path, message: str) -> None:
    print(f"::error file={path}::{message}")


def require_markers(path: Path, text: str, markers: tuple[str, ...]) -> int:
    errors = 0
    for marker in markers:
        if marker not in text:
            fail(path, f"Отсутствует обязательный маркер runtime-резерва: {marker}")
            errors += 1
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("site_dir", nargs="?", default="_site")
    args = parser.parse_args()

    site_dir = Path(args.site_dir).resolve()
    page = site_dir / "online-zayavka" / "index.html"
    script = site_dir / "assets" / "js" / "online-application.js"

    errors = 0
    if not page.is_file():
        fail(page, "Страница онлайн-заявки не найдена")
        return 1
    if not script.is_file():
        fail(script, "Контроллер онлайн-заявки не найден")
        return 1

    html = page.read_text(encoding="utf-8-sig")
    js = script.read_text(encoding="utf-8-sig")

    errors += require_markers(
        page,
        html,
        (
            "data-application-runtime-fallback",
            "Онлайн-форма временно не загрузилась",
            f'href="tel:{PHONE}"',
            f'href="sms:{PHONE}"',
            f'href="{VK_URL}"',
            "<noscript>",
            "form.dataset.applicationReady === 'true'",
            "Форма не загрузилась. Используйте резервный способ обращения выше.",
            "data-application-submit",
            "disabled",
            'aria-busy="true"',
            "Загружаем форму…",
        ),
    )

    noscript_match = re.search(r"<noscript>(?P<body>.*?)</noscript>", html, re.DOTALL)
    if not noscript_match:
        fail(page, "Не удалось выделить noscript-резерв")
        errors += 1
    else:
        noscript = noscript_match.group("body")
        for marker in (f"tel:{PHONE}", f"sms:{PHONE}", VK_URL):
            if marker not in noscript:
                fail(page, f"Noscript-резерв не содержит канал: {marker}")
                errors += 1

    button_match = re.search(
        r"<button[^>]*data-application-submit[^>]*>",
        html,
        re.IGNORECASE,
    )
    if not button_match:
        fail(page, "Не найдена основная кнопка подготовки заявки")
        errors += 1
    else:
        button = button_match.group(0)
        if "disabled" not in button or 'aria-busy="true"' not in button:
            fail(page, "Кнопка должна быть заблокирована до успешной инициализации")
            errors += 1

    errors += require_markers(
        script,
        js,
        (
            "const submitButton = form.querySelector('[data-application-submit]');",
            "const runtimeFallback = document.querySelector('[data-application-runtime-fallback]');",
            "form.dataset.applicationReady = 'true';",
            "submitButton.disabled = false;",
            "submitButton.removeAttribute('aria-busy');",
            "runtimeFallback.hidden = true;",
            "setStatus('');",
        ),
    )

    pages_with_runtime_fallback: list[str] = []
    for html_path in site_dir.rglob("*.html"):
        text = html_path.read_text(encoding="utf-8-sig")
        if "data-application-runtime-fallback" in text:
            pages_with_runtime_fallback.append(html_path.relative_to(site_dir).as_posix())

    if pages_with_runtime_fallback != ["online-zayavka/index.html"]:
        fail(
            site_dir,
            "Runtime-резерв должен присутствовать только на онлайн-заявке: "
            + ", ".join(pages_with_runtime_fallback),
        )
        errors += 1

    if errors:
        print(f"Аудит runtime-резерва анкеты завершён с ошибками: {errors}")
        return 1

    print(
        "Runtime-резерв онлайн-заявки подтверждён: "
        "disabled до init, watchdog, noscript, телефон, SMS и ВКонтакте"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
