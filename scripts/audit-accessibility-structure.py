#!/usr/bin/env python3
"""Проверяет базовую доступность всех собранных HTML-страниц без браузера."""

from __future__ import annotations

import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POSITIVE_INT_RE = re.compile(r"^[1-9][0-9]*$")
ARIA_REFERENCE_ATTRS = ("aria-controls", "aria-labelledby", "aria-describedby")


def error(message: str, path: Path | None = None) -> None:
    prefix = "::error"
    if path is not None:
        try:
            display = path.relative_to(ROOT).as_posix()
        except ValueError:
            display = path.as_posix()
        prefix += f" file={display}"
    print(f"{prefix}::{message}")


class AccessibilityParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lang = ""
        self.ids: list[str] = []
        self.label_for: set[str] = set()
        self.controls: list[dict[str, str | bool]] = []
        self.references: list[tuple[str, str]] = []
        self.interactive_stack: list[dict[str, object]] = []
        self.interactives: list[dict[str, object]] = []
        self.main_count = 0
        self.main_valid = False
        self.main_depth = 0
        self.label_depth = 0
        self.skip_link = False
        self.nav_total = 0
        self.nav_named = 0
        self.headings: list[int] = []
        self.image_count = 0
        self.violations: list[str] = []

    @property
    def in_main(self) -> bool:
        return self.main_depth > 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key: value or "" for key, value in attrs}
        classes = set(data.get("class", "").split())

        if tag == "html":
            self.lang = data.get("lang", "")
        element_id = data.get("id")
        if element_id:
            self.ids.append(element_id)
        for attr in ARIA_REFERENCE_ATTRS:
            for reference in data.get(attr, "").split():
                self.references.append((attr, reference))

        if tag == "main":
            self.main_count += 1
            self.main_depth += 1
            if data.get("id") == "main-content" and data.get("tabindex") == "-1":
                self.main_valid = True
        elif self.in_main and re.fullmatch(r"h[1-6]", tag):
            self.headings.append(int(tag[1]))

        if tag == "label":
            self.label_depth += 1
            if data.get("for"):
                self.label_for.add(data["for"])

        if tag == "nav":
            self.nav_total += 1
            if data.get("aria-label") or data.get("aria-labelledby"):
                self.nav_named += 1

        if tag == "a" and "skip-link" in classes and data.get("href") == "#main-content":
            self.skip_link = True

        if tag in {"a", "button"}:
            item: dict[str, object] = {
                "tag": tag,
                "text": [],
                "aria_label": data.get("aria-label", "").strip(),
                "href": data.get("href", "").strip(),
                "target": data.get("target", "").strip(),
                "rel": set(data.get("rel", "").split()),
                "type": data.get("type", "").strip(),
            }
            self.interactive_stack.append(item)

        if tag == "img":
            self.image_count += 1
            alt = data.get("alt")
            src = data.get("src", "")
            if alt is None:
                self.violations.append(f"Изображение без alt: {src or '[без src]'}")
            if src.startswith("/"):
                for dimension in ("width", "height"):
                    if not POSITIVE_INT_RE.fullmatch(data.get(dimension, "")):
                        self.violations.append(
                            f"Локальное изображение без положительного {dimension}: {src or '[без src]'}"
                        )
            if self.interactive_stack and alt:
                self.interactive_stack[-1]["text"].append(alt)

        if tag in {"input", "select", "textarea"}:
            if tag == "input" and data.get("type", "").lower() == "hidden":
                return
            self.controls.append(
                {
                    "tag": tag,
                    "id": data.get("id", ""),
                    "name": data.get("name", ""),
                    "nested": self.label_depth > 0,
                    "aria_label": data.get("aria-label", ""),
                    "aria_labelledby": data.get("aria-labelledby", ""),
                }
            )

    def handle_endtag(self, tag: str) -> None:
        if tag in {"a", "button"} and self.interactive_stack:
            self.interactives.append(self.interactive_stack.pop())
        if tag == "label" and self.label_depth:
            self.label_depth -= 1
        if tag == "main" and self.main_depth:
            self.main_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.interactive_stack and data.strip():
            self.interactive_stack[-1]["text"].append(data.strip())


def check_page(path: Path) -> tuple[int, dict[str, int]]:
    parser = AccessibilityParser()
    try:
        parser.feed(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        error(f"Не удалось прочитать HTML: {exc}", path)
        return 1, {}

    failures = 0
    if parser.lang != "ru":
        error(f"Ожидается <html lang=\"ru\">, найдено: {parser.lang or '[пусто]'}", path)
        failures += 1
    if parser.main_count != 1:
        error(f"Ожидается ровно один <main>, найдено: {parser.main_count}", path)
        failures += 1
    elif not parser.main_valid:
        error("Main должен иметь id=main-content и tabindex=-1", path)
        failures += 1
    if not parser.skip_link:
        error("Не найдена skip-link на #main-content", path)
        failures += 1

    duplicates = [element_id for element_id, count in Counter(parser.ids).items() if count > 1]
    if duplicates:
        error(f"Повторяющиеся id: {', '.join(sorted(duplicates))}", path)
        failures += 1

    id_set = set(parser.ids)
    for attr, reference in parser.references:
        if reference not in id_set:
            error(f"{attr} ссылается на отсутствующий id: {reference}", path)
            failures += 1

    if parser.nav_named != parser.nav_total:
        error(
            f"Навигационных областей без доступного имени: {parser.nav_total - parser.nav_named}",
            path,
        )
        failures += 1

    h1_count = parser.headings.count(1)
    if h1_count != 1:
        error(f"Ожидается ровно один H1 внутри main, найдено: {h1_count}", path)
        failures += 1
    for previous, current in zip(parser.headings, parser.headings[1:]):
        if current > previous + 1:
            error(f"Пропущен уровень заголовка: H{previous} → H{current}", path)
            failures += 1
            break

    for message in parser.violations:
        error(message, path)
        failures += 1

    for control in parser.controls:
        control_id = str(control["id"])
        labelled = (
            bool(control_id and control_id in parser.label_for)
            or bool(control["nested"])
            or bool(str(control["aria_label"]).strip())
            or bool(str(control["aria_labelledby"]).strip())
        )
        if not labelled:
            descriptor = str(control["name"] or control_id or control["tag"])
            error(f"Поле формы без label или ARIA-имени: {descriptor}", path)
            failures += 1

    for interactive in parser.interactives:
        tag = str(interactive["tag"])
        text = " ".join(str(item) for item in interactive["text"]).strip()
        accessible_name = str(interactive["aria_label"]).strip() or text
        if not accessible_name:
            error(f"{tag} без доступного имени", path)
            failures += 1
        if tag == "a":
            href = str(interactive["href"])
            if not href:
                error("Ссылка без href", path)
                failures += 1
            if interactive["target"] == "_blank" and "noopener" not in interactive["rel"]:
                error("Ссылка target=_blank без rel=noopener", path)
                failures += 1
        else:
            button_type = str(interactive["type"])
            if button_type not in {"button", "submit", "reset"}:
                error(f"Кнопка без явного корректного type: {button_type or '[пусто]'}", path)
                failures += 1

    return failures, {
        "images": parser.image_count,
        "controls": len(parser.controls),
        "interactives": len(parser.interactives),
    }


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    if not site_dir.is_dir():
        error("Каталог собранного сайта не найден", site_dir)
        return 1

    pages = sorted(site_dir.rglob("*.html"))
    if not pages:
        error("В сборке не найдено HTML-страниц", site_dir)
        return 1

    failures = 0
    images = 0
    controls = 0
    interactives = 0
    for path in pages:
        page_failures, stats = check_page(path)
        failures += page_failures
        images += stats.get("images", 0)
        controls += stats.get("controls", 0)
        interactives += stats.get("interactives", 0)

    if failures:
        print(f"Аудит доступности HTML завершён с ошибками: {failures}")
        return 1

    print(
        "Аудит доступности HTML успешно завершён: "
        f"страниц {len(pages)}, изображений {images}, "
        f"полей формы {controls}, интерактивных элементов {interactives}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
