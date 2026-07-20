#!/usr/bin/env python3
"""Проверяет, что только онлайн-заявка использует компактный целевой подвал."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "_layouts" / "default.html"
CSS = ROOT / "assets" / "css" / "footer-trust.css"

SOURCE_MARKERS = (
    "site-footer-compact",
    "footer-grid-compact",
    "Политика обработки данных",
    "Помощь и связь",
    "page.url == '/online-zayavka/'",
    '<meta name="theme-color" content="#17283d">',
)
CSS_MARKERS = (
    ".site-footer-compact",
    ".footer-grid-compact",
    "grid-template-columns: repeat(2",
)
ESSENTIAL_MARKERS = (
    'class="footer-person"',
    'src="/assets/img/tatyana-avatar.webp"',
    'href="/policy/"',
    'href="/o-brokere/"',
    'href="/kontakty/"',
    'href="tel:+79030250807"',
    'href="https://vk.com/tatyanasterlikova"',
)
FULL_NAV_MARKERS = (
    "<strong>Услуги</strong>",
    "<strong>Сложные случаи</strong>",
    "<strong>География</strong>",
)


def fail(path: Path, message: str) -> None:
    try:
        display = path.relative_to(ROOT).as_posix()
    except ValueError:
        display = path.as_posix()
    print(f"::error file={display}::{message}")


def footer_fragment(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    start = text.find("<footer")
    end = text.find("</footer>", start)
    if start == -1 or end == -1:
        return ""
    return text[start : end + len("</footer>")]


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    application = site_dir / "online-zayavka" / "index.html"
    homepage = site_dir / "index.html"
    errors = 0

    for path, markers, label in (
        (LAYOUT, SOURCE_MARKERS, "layout"),
        (CSS, CSS_MARKERS, "CSS"),
    ):
        if not path.is_file():
            fail(path, f"Не найден {label}")
            errors += 1
            continue
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                fail(path, f"В {label} отсутствует маркер: {marker}")
                errors += 1

    if not application.is_file() or not homepage.is_file():
        fail(site_dir, "Не найдены собранные главная или онлайн-заявка")
        return 1

    application_footer = footer_fragment(application)
    homepage_footer = footer_fragment(homepage)
    if not application_footer:
        fail(application, "Не найден footer")
        errors += 1
    if not homepage_footer:
        fail(homepage, "Не найден footer")
        errors += 1

    if application_footer.count("site-footer-compact") != 1:
        fail(application, "Онлайн-заявка должна содержать один компактный footer")
        errors += 1
    if application_footer.count("footer-grid-compact") != 1:
        fail(application, "Онлайн-заявка должна содержать одну компактную footer-сетку")
        errors += 1
    for marker in ESSENTIAL_MARKERS:
        if marker not in application_footer:
            fail(application, f"В компактном footer отсутствует обязательный маркер: {marker}")
            errors += 1
    for marker in FULL_NAV_MARKERS:
        if marker in application_footer:
            fail(application, f"В компактном footer осталась полная навигация: {marker}")
            errors += 1

    if "site-footer-compact" in homepage_footer or "footer-grid-compact" in homepage_footer:
        fail(homepage, "Компактный footer не должен применяться к главной")
        errors += 1
    for marker in FULL_NAV_MARKERS:
        if marker not in homepage_footer:
            fail(homepage, f"Главная потеряла раздел полного footer: {marker}")
            errors += 1

    if errors:
        print(f"Аудит компактного footer завершён с ошибками: {errors}")
        return 1

    saved = len(homepage_footer.encode("utf-8")) - len(application_footer.encode("utf-8"))
    print(
        "Компактный footer подтверждён: "
        f"онлайн-заявка сохраняет контакты и политику, HTML короче полного footer на {saved} байт"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
