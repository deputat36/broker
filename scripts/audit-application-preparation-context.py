#!/usr/bin/env python3
"""Проверяет передачу этапа подготовки из сложных маршрутов в онлайн-заявку."""

from __future__ import annotations

import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

APPLICATION_URL = "/online-zayavka/"
REGIONS = ("borisoglebsk", "gribanovskiy", "povorino")
SCENARIOS = (
    "otkazali-v-ipoteke",
    "ipoteka-s-plohoy-kreditnoy-istoriey",
    "ipoteka-bez-oficialnogo-dohoda",
    "ipoteka-bez-pervonachalnogo-vznosa",
)
REQUIRED_FIELDS = {
    "journey_type",
    "journey_stage",
    "journey_scenario_slug",
    "preparation_check",
    "remaining_questions",
}
REQUIRED_LABEL_KEYS = {"diagnosis", "finances", "documents", "next_step"}
REPO_ROOT = Path(__file__).resolve().parents[1]


class ApplicationParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.fields: Counter[str] = Counter()
        self.scripts: set[str] = set()
        self.markers: set[str] = set()
        self.preparation_labels: set[str] = set()
        self.preparation_hidden = False
        self.context_version = ""
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.lower(): value for key, value in attrs}
        if tag.lower() == "script":
            src = attrs_map.get("src") or ""
            if src:
                self.scripts.add(urlparse(src).path or src)
        name = attrs_map.get("name")
        if name:
            self.fields[name] += 1
        for key in attrs_map:
            if key.startswith("data-"):
                self.markers.add(key)
        label_key = attrs_map.get("data-preparation-label")
        if label_key:
            self.preparation_labels.add(label_key)
        if "data-application-preparation" in attrs_map:
            self.context_version = attrs_map.get("data-preparation-context-version") or ""
            if "hidden" in attrs_map:
                self.preparation_hidden = True

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)

    @property
    def text(self) -> str:
        return " ".join(" ".join(self.text_parts).casefold().replace("ё", "е").split())


class RouteLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attrs_map = {key.lower(): value for key, value in attrs}
        if "data-complex-application-link" in attrs_map:
            href = attrs_map.get("href") or ""
            if href:
                self.links.append(href)


def annotation(message: str, file: Path | None = None) -> None:
    prefix = "::error"
    if file is not None:
        prefix += f" file={file.as_posix()}"
    print(f"{prefix}::{message}")


def url_to_file(site_dir: Path, page_url: str) -> Path:
    return site_dir / page_url.lstrip("/") / "index.html"


def expected_complex_pages() -> list[str]:
    return [f"/geo/{region}/{scenario}/" for region in REGIONS for scenario in SCENARIOS]


def validate_application_page(site_dir: Path) -> int:
    html_file = url_to_file(site_dir, APPLICATION_URL)
    if not html_file.is_file():
        annotation("Не найдена онлайн-заявка", html_file)
        return 1

    parser = ApplicationParser()
    try:
        parser.feed(html_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        annotation(f"Не удалось прочитать онлайн-заявку: {error}", html_file)
        return 1

    errors = 0
    missing_fields = REQUIRED_FIELDS - set(parser.fields)
    if missing_fields:
        annotation(f"В форме отсутствуют поля подготовки: {', '.join(sorted(missing_fields))}", html_file)
        errors += 1
    if parser.fields["preparation_check"] != 4:
        annotation(f"Ожидалось четыре отметки подготовки, найдено: {parser.fields['preparation_check']}", html_file)
        errors += 1
    if not parser.preparation_hidden:
        annotation("Блок подготовки должен быть скрыт при обычном переходе", html_file)
        errors += 1
    if parser.context_version != "1":
        annotation(f"Некорректная версия контекста подготовки: {parser.context_version or 'отсутствует'}", html_file)
        errors += 1
    missing_labels = REQUIRED_LABEL_KEYS - parser.preparation_labels
    if missing_labels:
        annotation("Не хватает сценарных подписей подготовки: " + ", ".join(sorted(missing_labels)), html_file)
        errors += 1
    required_markers = {
        "data-application-preparation",
        "data-preparation-context-version",
        "data-preparation-intro",
        "data-preparation-options",
    }
    if required_markers - parser.markers:
        annotation(f"Не хватает маркеров блока подготовки: {', '.join(sorted(required_markers - parser.markers))}", html_file)
        errors += 1
    if "/assets/js/application-preparation.js" not in parser.scripts:
        annotation("Не подключён сценарный скрипт подготовки", html_file)
        errors += 1
    required_texts = (
        "что уже успели проверить",
        "что осталось непонятно или требует проверки",
        "не указывайте паспортные данные",
    )
    for marker in required_texts:
        if marker not in parser.text:
            annotation(f"В форме отсутствует текст блока подготовки: {marker}", html_file)
            errors += 1
    return errors


def validate_complex_links(site_dir: Path) -> int:
    errors = 0
    for page_url in expected_complex_pages():
        html_file = url_to_file(site_dir, page_url)
        if not html_file.is_file():
            annotation(f"Не найдена сложная региональная страница: {page_url}", html_file)
            errors += 1
            continue
        parser = RouteLinkParser()
        try:
            parser.feed(html_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as error:
            annotation(f"Не удалось прочитать страницу: {error}", html_file)
            errors += 1
            continue
        if len(parser.links) != 1:
            annotation(f"Ожидалась одна контекстная ссылка на форму, найдено: {len(parser.links)}", html_file)
            errors += 1
            continue
        parsed = urlparse(parser.links[0])
        query = parse_qs(parsed.query)
        if parsed.path != APPLICATION_URL:
            annotation(f"Сложный маршрут ведёт не на {APPLICATION_URL}", html_file)
            errors += 1
        if query.get("source") != [page_url]:
            annotation(f"Неверный source сложного маршрута: {query.get('source')}", html_file)
            errors += 1
        if query.get("journey") != ["complex"]:
            annotation("Сложный маршрут не передаёт journey=complex", html_file)
            errors += 1
        if query.get("stage") != ["route"]:
            annotation("Сложный маршрут не передаёт stage=route", html_file)
            errors += 1
    return errors


def validate_script_source() -> int:
    js_file = REPO_ROOT / "assets/js/application-preparation.js"
    if not js_file.is_file():
        annotation("Не найден application-preparation.js", js_file)
        return 1
    source = js_file.read_text(encoding="utf-8", errors="ignore")
    errors = 0
    required_markers = (
        "CONFIG_BY_SLUG",
        "getApplicationPreparationData",
        "context_version",
        "journey_scenario_slug",
        "completed_checks",
        "completed_labels",
        "remaining_questions",
        "preparation_json",
        "fields.preparation = data",
        "payload.preparation = data",
        "ПОДГОТОВКА ДО ОБРАЩЕНИЯ",
        "online_application_complex_prefill",
        "online_application_preparation_check",
        "После изучения маршрута подготовки",
        "detailsStepNumber.textContent = '3'",
    ) + SCENARIOS
    for marker in required_markers:
        if marker not in source:
            annotation(f"В application-preparation.js отсутствует маркер: {marker}", js_file)
            errors += 1

    forbidden_markers = (
        "commentField.value =",
        "Комментарий клиента:",
        "MAX_COMBINED_COMMENT_LENGTH",
    )
    for marker in forbidden_markers:
        if marker in source:
            annotation(f"Контекст подготовки снова подмешивается в комментарий: {marker}", js_file)
            errors += 1
    return errors


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    if not site_dir.is_dir():
        annotation(f"Каталог сборки не найден: {site_dir}")
        return 1

    errors = validate_application_page(site_dir)
    errors += validate_complex_links(site_dir)
    errors += validate_script_source()

    if errors:
        print(f"Аудит контекста подготовки заявки завершен с ошибками: {errors}")
        return 1

    print(
        "Аудит контекста подготовки заявки успешно завершен: "
        f"проверено сложных входов {len(expected_complex_pages())}, сценариев {len(SCENARIOS)}, "
        "отметок 4, transport-полей Web3Forms и preparation JSON"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())