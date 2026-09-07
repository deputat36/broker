#!/usr/bin/env python3
"""Проверяет, что мобильная панель быстрых контактов остаётся в один ряд."""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LAYOUT_PATH = REPO_ROOT / "_layouts/default.html"
SOURCE_CSS_PATH = REPO_ROOT / "assets/css/nav-state.css"
SEO_CSS_MARKER = "{{ '/assets/css/seo.css' | relative_url }}"
OVERRIDE_CSS_MARKER = "{{ '/assets/css/nav-state.css' | relative_url }}"
MOBILE_MEDIA_MARKER = "@media (max-width: 760px)"
EXPECTED_GRID = "minmax(0, 1.15fr) minmax(0, 1fr) repeat(2, minmax(0, .7fr))"
EXPECTED_LABELS = ["Заявка", "Позвонить", "MAX", "ВК"]
STICKY_RULE_RE = re.compile(r"\.sticky-contacts\s*\{([^{}]*)\}", re.DOTALL)
GRID_RE = re.compile(r"grid-template-columns\s*:\s*([^;]+);", re.IGNORECASE)


class StickyContactsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.container_depth = 0
        self.container_count = 0
        self.action_depth = 0
        self.current_label: list[str] = []
        self.labels: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.lower(): value or "" for key, value in attrs}
        classes = set(attrs_map.get("class", "").split())

        if self.container_depth:
            self.container_depth += 1
        elif "sticky-contacts" in classes:
            self.container_depth = 1
            self.container_count += 1

        if self.container_depth and "sticky-action" in classes:
            self.action_depth = self.container_depth
            self.current_label = []

    def handle_data(self, data: str) -> None:
        if self.action_depth:
            self.current_label.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self.container_depth:
            return

        if self.action_depth == self.container_depth:
            label = " ".join("".join(self.current_label).split())
            self.labels.append(label)
            self.action_depth = 0
            self.current_label = []

        self.container_depth -= 1


def fail(path: Path, message: str) -> None:
    print(f"::error file={path.as_posix()}::{message}")


def normalize_grid(value: str) -> str:
    """Сравнивает CSS-значение по смыслу, не по косметическому форматированию."""
    normalized = " ".join(value.split())
    normalized = re.sub(r"\s*,\s*", ", ", normalized)
    normalized = re.sub(r"\(\s*", "(", normalized)
    normalized = re.sub(r"\s*\)", ")", normalized)
    normalized = normalized.replace("0.7fr", ".7fr")
    return normalized


def matching_brace(css: str, opening: int) -> int | None:
    depth = 0
    for index in range(opening, len(css)):
        char = css[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return None


def mobile_sticky_grids(css: str) -> list[str]:
    """Возвращает grid-template-columns sticky-панели только из mobile media query."""
    values: list[str] = []
    search_from = 0

    while True:
        media_index = css.find(MOBILE_MEDIA_MARKER, search_from)
        if media_index == -1:
            break
        opening = css.find("{", media_index + len(MOBILE_MEDIA_MARKER))
        if opening == -1:
            break
        closing = matching_brace(css, opening)
        if closing is None:
            break

        media_body = css[opening + 1 : closing]
        for sticky_match in STICKY_RULE_RE.finditer(media_body):
            grid_match = GRID_RE.search(sticky_match.group(1))
            if grid_match:
                values.append(normalize_grid(grid_match.group(1)))

        search_from = closing + 1

    return values


def validate_mobile_override(css: str, path: Path) -> int:
    expected = normalize_grid(EXPECTED_GRID)
    values = mobile_sticky_grids(css)
    if values != [expected]:
        fail(
            path,
            "Ожидался один mobile override sticky-панели на четыре колонки; "
            f"получено {values!r}, ожидалось {[expected]!r}",
        )
        return 1
    return 0


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    errors = 0

    if not LAYOUT_PATH.is_file():
        fail(LAYOUT_PATH, "Канонический layout не найден")
        return 1
    if not SOURCE_CSS_PATH.is_file():
        fail(SOURCE_CSS_PATH, "CSS с мобильным override не найден")
        return 1

    layout = LAYOUT_PATH.read_text(encoding="utf-8")
    source_css = SOURCE_CSS_PATH.read_text(encoding="utf-8")
    errors += validate_mobile_override(source_css, SOURCE_CSS_PATH)

    seo_index = layout.find(SEO_CSS_MARKER)
    override_index = layout.find(OVERRIDE_CSS_MARKER)
    if seo_index == -1 or override_index == -1 or override_index <= seo_index:
        fail(
            LAYOUT_PATH,
            "nav-state.css должен подключаться после seo.css, чтобы four-column override имел приоритет",
        )
        errors += 1

    built_css_path = site_dir / "assets/css/nav-state.css"
    if not built_css_path.is_file():
        fail(built_css_path, "Собранный nav-state.css не найден")
        errors += 1
    else:
        built_css = built_css_path.read_text(encoding="utf-8-sig", errors="ignore")
        errors += validate_mobile_override(built_css, built_css_path)

    html_files = sorted(site_dir.rglob("*.html"))
    if not html_files:
        fail(site_dir, "Собранные HTML-страницы не найдены")
        return 1

    for html_file in html_files:
        parser = StickyContactsParser()
        parser.feed(html_file.read_text(encoding="utf-8-sig", errors="ignore"))

        if parser.container_count != 1:
            fail(
                html_file,
                f"Найдено панелей sticky-contacts: {parser.container_count}, ожидалась одна",
            )
            errors += 1
            continue

        if parser.labels != EXPECTED_LABELS:
            fail(
                html_file,
                "Состав мобильной панели изменён: "
                f"получено {parser.labels!r}, ожидалось {EXPECTED_LABELS!r}",
            )
            errors += 1

    if errors:
        print(f"Аудит мобильной панели контактов завершён с ошибками: {errors}")
        return 1

    print(
        "Мобильная панель контактов подтверждена: "
        f"{len(html_files)} HTML-страниц, четыре действия в одном CSS-ряду"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
