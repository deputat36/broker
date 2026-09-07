#!/usr/bin/env python3
"""Проверяет вес Pages-артефакта и реально подключённых ресурсов страниц."""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "scripts" / "performance-budget.json"
ASSET_PREFIXES = ("assets/css/", "assets/js/", "assets/img/")
TRACKED_SUFFIXES = {".html", ".css", ".js", ".jpg", ".jpeg", ".png", ".webp", ".svg"}
DYNAMIC_ASSET_RE = re.compile(
    r"(?P<quote>['\"])(?P<path>(?:/)?assets/[A-Za-z0-9_./-]+|[A-Za-z0-9_.-]+\.(?:js|css|png|jpg|jpeg|webp|svg))(?P=quote)"
)


def fail(message: str, path: Path | None = None) -> None:
    prefix = "::error"
    if path is not None:
        try:
            display = path.relative_to(ROOT).as_posix()
        except ValueError:
            display = path.as_posix()
        prefix += f" file={display}"
    print(f"{prefix}::{message}")


class ResourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.resources: list[str] = []
        self.references: list[str] = []

    def add_resource(self, url: str, *, page_load: bool = True) -> None:
        self.references.append(url)
        if page_load:
            self.resources.append(url)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key.lower(): value for key, value in attrs if value is not None}
        tag = tag.lower()

        if tag == "link":
            rel = {item.lower() for item in data.get("rel", "").split()}
            href = data.get("href")
            if not href:
                return

            if rel.intersection({"stylesheet", "icon", "apple-touch-icon", "manifest", "preload"}):
                page_load = bool(rel.intersection({"stylesheet", "icon", "preload"}))
                if "apple-touch-icon" in rel or "manifest" in rel:
                    page_load = False
                self.add_resource(href, page_load=page_load)
            return

        if tag == "meta":
            marker = (data.get("property") or data.get("name") or "").lower()
            if marker in {"og:image", "og:image:secure_url", "twitter:image"} and data.get("content"):
                self.add_resource(data["content"], page_load=False)
            return

        if tag == "script" and data.get("src"):
            self.add_resource(data["src"])
            return

        if tag == "img" and data.get("src"):
            self.add_resource(data["src"])
            return

        if tag == "source" and data.get("srcset"):
            for candidate in data["srcset"].split(","):
                url = candidate.strip().split()[0] if candidate.strip() else ""
                if url:
                    self.add_resource(url)


def load_config() -> dict:
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Не удалось прочитать {CONFIG_PATH}: {error}") from error

    required = {
        "total_bytes",
        "html_total_bytes",
        "css_total_bytes",
        "js_total_bytes",
        "image_total_bytes",
        "max_html_bytes",
        "max_css_bytes",
        "max_js_bytes",
        "max_image_bytes",
        "max_page_local_bytes",
        "p95_page_local_bytes",
        "allowed_orphans",
    }
    missing = sorted(required - config.keys())
    if missing:
        raise ValueError(f"В performance budget отсутствуют поля: {', '.join(missing)}")
    if not isinstance(config["allowed_orphans"], list):
        raise ValueError("allowed_orphans должен быть массивом")
    return config


def percentile(values: list[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    value = ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)
    return math.ceil(value)


def local_path(site_dir: Path, raw_url: str) -> Path | None:
    parsed = urlparse(raw_url)
    if parsed.netloc and parsed.netloc not in {"sterlikova-ipoteka.ru", "www.sterlikova-ipoteka.ru"}:
        return None
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return None
    path = parsed.path
    if not path.startswith("/"):
        return None
    candidate = (site_dir / path.lstrip("/")).resolve()
    try:
        candidate.relative_to(site_dir)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def collect_files(site_dir: Path) -> list[Path]:
    return sorted(
        path for path in site_dir.rglob("*")
        if path.is_file() and path.name != "artifact.tar"
    )


def sum_suffix(files: list[Path], suffixes: set[str]) -> int:
    return sum(path.stat().st_size for path in files if path.suffix.lower() in suffixes)


def check_budget(label: str, actual: int, limit: int, errors: list[str]) -> None:
    if actual > limit:
        errors.append(f"{label}: {actual} байт при лимите {limit}")


def check_file_limits(
    files: list[Path],
    suffixes: set[str],
    limit: int,
    label: str,
    errors: list[str],
) -> None:
    for path in files:
        if path.suffix.lower() not in suffixes:
            continue
        size = path.stat().st_size
        if size > limit:
            errors.append(f"{label} {path.name}: {size} байт при лимите {limit}")


def add_manifest_references(site_dir: Path, referenced: Counter[str], errors: list[str]) -> None:
    manifest_path = site_dir / "site.webmanifest"
    if not manifest_path.is_file():
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"Не удалось прочитать manifest для графа ресурсов: {error}")
        return

    icons = manifest.get("icons", [])
    if not isinstance(icons, list):
        errors.append("Manifest icons должен быть массивом для графа ресурсов")
        return

    for icon in icons:
        if not isinstance(icon, dict) or not isinstance(icon.get("src"), str):
            continue
        resource = local_path(site_dir, icon["src"])
        if resource is None:
            continue
        referenced[resource.relative_to(site_dir).as_posix()] += 1


def add_dynamic_js_references(site_dir: Path, files: list[Path], referenced: Counter[str]) -> None:
    """Учитывает asset-файлы, которые JS подгружает после первого HTML-запроса.

    Такие зависимости считаются используемыми для orphan-аудита, но не добавляются
    к first-load весу страницы до фактического runtime-условия.
    """
    for script_path in files:
        if script_path.suffix.lower() != ".js":
            continue
        try:
            text = script_path.read_text(encoding="utf-8-sig", errors="ignore")
        except OSError:
            continue
        for match in DYNAMIC_ASSET_RE.finditer(text):
            raw_path = match.group("path")
            if raw_path.startswith("/"):
                candidate = local_path(site_dir, raw_path)
            elif raw_path.startswith("assets/"):
                candidate = (site_dir / raw_path).resolve()
            else:
                candidate = (script_path.parent / raw_path).resolve()
            if candidate is None or not candidate.is_file():
                continue
            try:
                relative = candidate.relative_to(site_dir).as_posix()
            except ValueError:
                continue
            if candidate == script_path:
                continue
            referenced[relative] += 1


def main() -> int:
    site_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "_site").resolve()
    if not site_dir.is_dir():
        fail("Каталог собранного сайта не найден", site_dir)
        return 1

    try:
        config = load_config()
    except ValueError as error:
        fail(str(error), CONFIG_PATH)
        return 1

    files = collect_files(site_dir)
    html_files = [path for path in files if path.suffix.lower() == ".html"]
    errors: list[str] = []

    total_bytes = sum(path.stat().st_size for path in files)
    html_total = sum_suffix(files, {".html"})
    css_total = sum_suffix(files, {".css"})
    js_total = sum_suffix(files, {".js"})
    image_total = sum_suffix(files, {".jpg", ".jpeg", ".png", ".webp", ".svg"})

    check_budget("Общий вес артефакта", total_bytes, int(config["total_bytes"]), errors)
    check_budget("Общий вес HTML", html_total, int(config["html_total_bytes"]), errors)
    check_budget("Общий вес CSS", css_total, int(config["css_total_bytes"]), errors)
    check_budget("Общий вес JS", js_total, int(config["js_total_bytes"]), errors)
    check_budget("Общий вес изображений", image_total, int(config["image_total_bytes"]), errors)

    check_file_limits(files, {".html"}, int(config["max_html_bytes"]), "HTML-файл", errors)
    check_file_limits(files, {".css"}, int(config["max_css_bytes"]), "CSS-файл", errors)
    check_file_limits(files, {".js"}, int(config["max_js_bytes"]), "JS-файл", errors)
    check_file_limits(
        files,
        {".jpg", ".jpeg", ".png", ".webp", ".svg"},
        int(config["max_image_bytes"]),
        "Изображение",
        errors,
    )

    referenced: Counter[str] = Counter()
    page_weights: list[tuple[str, int]] = []

    for html_path in html_files:
        parser = ResourceParser()
        parser.feed(html_path.read_text(encoding="utf-8"))

        for raw_url in parser.references:
            resource = local_path(site_dir, raw_url)
            if resource is None:
                continue
            referenced[resource.relative_to(site_dir).as_posix()] += 1

        page_assets: dict[str, int] = {}
        for raw_url in parser.resources:
            resource = local_path(site_dir, raw_url)
            if resource is None:
                continue
            relative = resource.relative_to(site_dir).as_posix()
            page_assets[relative] = resource.stat().st_size

        page_weight = html_path.stat().st_size + sum(page_assets.values())
        relative_html = html_path.relative_to(site_dir).as_posix()
        page_weights.append((relative_html, page_weight))
        if page_weight > int(config["max_page_local_bytes"]):
            errors.append(
                f"Страница {relative_html}: локальная загрузка {page_weight} байт "
                f"при лимите {config['max_page_local_bytes']}"
            )

    add_manifest_references(site_dir, referenced, errors)
    add_dynamic_js_references(site_dir, files, referenced)

    p95 = percentile([weight for _, weight in page_weights], 0.95)
    check_budget(
        "95-й процентиль локального веса страницы",
        p95,
        int(config["p95_page_local_bytes"]),
        errors,
    )

    allowed_orphans = set(config["allowed_orphans"])
    asset_files = {
        path.relative_to(site_dir).as_posix()
        for path in files
        if path.relative_to(site_dir).as_posix().startswith(ASSET_PREFIXES)
        and path.suffix.lower() in TRACKED_SUFFIXES
    }
    orphans = sorted(asset_files - set(referenced) - allowed_orphans)
    if orphans:
        errors.append("Найдены неподключённые asset-файлы: " + ", ".join(orphans))

    missing_allowed = sorted(allowed_orphans - asset_files)
    if missing_allowed:
        errors.append(
            "Allowlist содержит отсутствующие asset-файлы: " + ", ".join(missing_allowed)
        )

    if errors:
        for message in errors:
            fail(message)
        print(f"Performance-аудит завершён с ошибками: {len(errors)}")
        return 1

    largest_pages = sorted(page_weights, key=lambda item: item[1], reverse=True)[:3]
    largest_summary = "; ".join(f"{path} — {weight}" for path, weight in largest_pages)
    print(
        "Performance-аудит успешно завершён: "
        f"файлов {len(files)}, HTML {len(html_files)}, общий вес {total_bytes}, "
        f"CSS {css_total}, JS {js_total}, изображения {image_total}, "
        f"p95 страницы {p95}. Самые тяжёлые: {largest_summary}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
