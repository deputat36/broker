#!/usr/bin/env python3
"""Проверяет опубликованный домен или локальный Pages-артефакт.

Live-режим выполняет HTTPS-запросы стандартной библиотекой Python и проверяет
главную, robots.txt, sitemap.xml и страницу благодарности. Offline-режим
использует тот же набор валидаторов для каталога `_site`, чтобы контракт smoke
проходил в pull request до фактического deploy.
"""

from __future__ import annotations

import argparse
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


DEFAULT_BASE_URL = "https://sterlikova-ipoteka.ru"
USER_AGENT = "SterlikovaMortgageProductionSmoke/1.0"
PATHS = ("/", "/robots.txt", "/sitemap.xml", "/spasibo/")
LEGACY_DOMAIN = "https://deputat36.github.io/broker"


@dataclass(frozen=True)
class Response:
    requested_path: str
    final_url: str
    status: int
    content_type: str
    text: str


class SmokeError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise SmokeError(message)


def canonical_base(value: str) -> str:
    parsed = urllib.parse.urlsplit(value.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        fail("Базовый адрес должен быть абсолютным HTTPS URL")
    if parsed.query or parsed.fragment:
        fail("Базовый адрес не должен содержать query или fragment")
    path = parsed.path.rstrip("/")
    return urllib.parse.urlunsplit(("https", parsed.netloc, path, "", ""))


def local_file_for(site_dir: Path, path: str) -> Path:
    if path == "/":
        return site_dir / "index.html"
    if path.endswith("/"):
        return site_dir / path.strip("/") / "index.html"
    return site_dir / path.lstrip("/")


def offline_response(site_dir: Path, base_url: str, path: str) -> Response:
    file = local_file_for(site_dir, path)
    if not file.is_file():
        fail(f"В Pages-артефакте отсутствует {path}: {file}")
    content_type = "application/xml" if path.endswith(".xml") else "text/plain" if path.endswith(".txt") else "text/html"
    return Response(
        requested_path=path,
        final_url=f"{base_url}{path}",
        status=200,
        content_type=content_type,
        text=file.read_text(encoding="utf-8", errors="strict"),
    )


def live_response(base_url: str, path: str, timeout: float) -> Response:
    url = f"{base_url}{path}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xml,text/plain;q=0.9,*/*;q=0.1",
            "Cache-Control": "no-cache",
        },
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            raw = response.read(2_000_000)
            charset = response.headers.get_content_charset() or "utf-8"
            try:
                text = raw.decode(charset, errors="strict")
            except (LookupError, UnicodeDecodeError) as error:
                fail(f"{path}: ответ нельзя декодировать как {charset}: {error}")
            return Response(
                requested_path=path,
                final_url=response.geturl(),
                status=getattr(response, "status", 200),
                content_type=response.headers.get("Content-Type", ""),
                text=text,
            )
    except urllib.error.HTTPError as error:
        fail(f"{path}: HTTP {error.code} {error.reason}")
    except urllib.error.URLError as error:
        fail(f"{path}: сеть/DNS/TLS: {error.reason}")
    except TimeoutError:
        fail(f"{path}: превышен таймаут {timeout:g} сек.")


def ensure_https_same_host(response: Response, base_url: str) -> None:
    expected = urllib.parse.urlsplit(base_url)
    actual = urllib.parse.urlsplit(response.final_url)
    if actual.scheme != "https":
        fail(f"{response.requested_path}: финальный URL не использует HTTPS: {response.final_url}")
    if actual.hostname != expected.hostname:
        fail(f"{response.requested_path}: редирект на другой host: {response.final_url}")
    if response.status != 200:
        fail(f"{response.requested_path}: ожидался HTTP 200, получен {response.status}")


def validate_home(response: Response, base_url: str) -> None:
    text = response.text
    if "text/html" not in response.content_type and response.content_type:
        fail(f"Главная: неожиданный Content-Type {response.content_type}")
    required = (
        "Татьяна Стерликова",
        "ипотечный брокер",
        'href="/online-zayavka/"',
        "tatyana-hero.webp",
        "tatyana-avatar.webp",
    )
    for marker in required:
        if marker not in text:
            fail(f"Главная: отсутствует маркер {marker}")
    canonical = f'<link rel="canonical" href="{base_url}/">'
    if canonical not in text:
        fail(f"Главная: canonical не равен {base_url}/")
    if LEGACY_DOMAIN in text:
        fail("Главная содержит старый технический домен GitHub Pages")
    if re.search(r"100%\s+одобр|гарантированн\w*\s+одобр|банк\s+точно\s+одобрит", text, re.I):
        fail("Главная содержит запрещённое обещание одобрения")


def validate_robots(response: Response, base_url: str) -> None:
    text = response.text.replace("\r\n", "\n")
    required = (
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {base_url}/sitemap.xml",
    )
    for marker in required:
        if marker not in text:
            fail(f"robots.txt: отсутствует строка {marker}")
    if LEGACY_DOMAIN in text:
        fail("robots.txt содержит старый технический домен")


def sitemap_locations(text: str) -> list[str]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        fail(f"sitemap.xml: некорректный XML: {error}")
    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    if root.tag != f"{namespace}urlset":
        fail(f"sitemap.xml: ожидался urlset, получен {root.tag}")
    locations = [node.text.strip() for node in root.findall(f"{namespace}url/{namespace}loc") if node.text and node.text.strip()]
    return locations


def validate_sitemap(response: Response, base_url: str) -> None:
    locations = sitemap_locations(response.text)
    if len(locations) < 100:
        fail(f"sitemap.xml содержит только {len(locations)} URL; ожидалось не менее 100")
    if len(locations) != len(set(locations)):
        fail("sitemap.xml содержит повторяющиеся URL")

    forbidden_parts = ("/404.html", "/spasibo/", "/assets/", LEGACY_DOMAIN)
    expected_host = urllib.parse.urlsplit(base_url).hostname
    for location in locations:
        parsed = urllib.parse.urlsplit(location)
        if parsed.scheme != "https" or parsed.hostname != expected_host:
            fail(f"sitemap.xml содержит URL вне основного HTTPS-домена: {location}")
        if any(part in location for part in forbidden_parts):
            fail(f"sitemap.xml содержит запрещённый URL: {location}")
    if f"{base_url}/" not in locations:
        fail("sitemap.xml не содержит главную страницу")
    if f"{base_url}/online-zayavka/" not in locations:
        fail("sitemap.xml не содержит онлайн-заявку")


def validate_thank_you(response: Response, base_url: str) -> None:
    text = response.text
    required = (
        '<meta name="robots" content="noindex, follow">',
        'id="lead-id"',
        "window.location.hash.replace(/^#/, '')",
        "legacyParams.get('id')",
        "window.history.replaceState(null, document.title, window.location.pathname)",
        "lead_thankyou_view",
    )
    for marker in required:
        if marker not in text:
            fail(f"Страница благодарности: отсутствует маркер {marker}")
    forbidden = (
        "get('scenario')",
        "get('status')",
        'id="lead-scenario"',
        'id="lead-city"',
        'id="lead-status"',
        LEGACY_DOMAIN,
    )
    for marker in forbidden:
        if marker in text:
            fail(f"Страница благодарности содержит запрещённый маркер {marker}")
    canonical = f'<link rel="canonical" href="{base_url}/spasibo/">'
    if canonical not in text:
        fail("Страница благодарности содержит неверный canonical")


def validate_suite(responses: dict[str, Response], base_url: str) -> None:
    for path in PATHS:
        ensure_https_same_host(responses[path], base_url)
    validate_home(responses["/"], base_url)
    validate_robots(responses["/robots.txt"], base_url)
    validate_sitemap(responses["/sitemap.xml"], base_url)
    validate_thank_you(responses["/spasibo/"], base_url)


def run_offline(site_dir: Path, base_url: str) -> None:
    if not site_dir.is_dir():
        fail(f"Каталог Pages-артефакта не найден: {site_dir}")
    responses = {path: offline_response(site_dir, base_url, path) for path in PATHS}
    validate_suite(responses, base_url)
    print(f"Offline live-domain contract успешно проверен: {len(PATHS)} маршрута, sitemap >= 100 URL")


def run_live(base_url: str, attempts: int, delay: float, timeout: float) -> None:
    last_error: SmokeError | None = None
    for attempt in range(1, attempts + 1):
        try:
            responses = {path: live_response(base_url, path, timeout) for path in PATHS}
            validate_suite(responses, base_url)
            count = len(sitemap_locations(responses["/sitemap.xml"].text))
            print(f"Production smoke успешно завершён: HTTPS, {len(PATHS)} маршрута, {count} URL в sitemap")
            return
        except SmokeError as error:
            last_error = error
            print(f"Попытка {attempt}/{attempts}: {error}", file=sys.stderr)
            if attempt < attempts:
                time.sleep(delay)
    raise last_error or SmokeError("Production smoke завершился без результата")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--site-dir", type=Path, help="Проверить локальный Pages-артефакт вместо сети")
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--delay", type=float, default=15.0)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    try:
        base_url = canonical_base(args.base_url)
        if args.attempts < 1 or args.attempts > 30:
            fail("Количество попыток должно быть от 1 до 30")
        if args.delay < 0 or args.delay > 120:
            fail("Задержка должна быть от 0 до 120 секунд")
        if args.timeout < 1 or args.timeout > 60:
            fail("Таймаут должен быть от 1 до 60 секунд")

        if args.site_dir:
            run_offline(args.site_dir.resolve(), base_url)
        else:
            run_live(base_url, args.attempts, args.delay, args.timeout)
        return 0
    except SmokeError as error:
        print(f"::error::{error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
