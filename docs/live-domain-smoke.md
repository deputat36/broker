# Автоматическая проверка опубликованного домена

## Назначение

`scripts/smoke-live-domain.py` проверяет один и тот же контракт в двух режимах:

1. offline — собранный Pages-артефакт внутри pull request;
2. live — фактически опубликованный `https://sterlikova-ipoteka.ru` после deploy в `main`.

Проверка не отправляет заявки и не использует персональные данные, Web3Forms, Supabase или аналитические secrets.

## Offline-режим

Команда:

```bash
python3 scripts/smoke-live-domain.py --site-dir ./_site
```

Она запускается в обязательном post-build suite каждого pull request и проверяет:

- главную страницу;
- `robots.txt`;
- `sitemap.xml`;
- `/spasibo/`;
- canonical основного домена;
- отсутствие старого технического домена;
- наличие онлайн-заявки и фотографий;
- отсутствие обещаний гарантированного одобрения;
- не менее 100 уникальных URL в sitemap;
- только HTTPS URL основного домена в sitemap;
- отсутствие `/404.html`, `/spasibo/` и `/assets/` в sitemap;
- `noindex` и минимальный privacy-контракт страницы благодарности.

Offline-режим подтверждает, что артефакт готов к публикации, но не доказывает работоспособность DNS и GitHub Pages.

## Live-режим

После успешного job `deploy` workflow запускает job `production-smoke`:

```bash
python3 scripts/smoke-live-domain.py \
  --attempts 12 \
  --delay 15 \
  --timeout 20
```

Проверка использует стандартную TLS-валидацию Python. Ошибка сертификата, DNS, HTTPS, HTTP-статуса, редирект на другой host или расхождение опубликованного контента завершают job ошибкой.

Повторные попытки нужны из-за возможной задержки обновления CDN после GitHub Pages deploy. Максимальная дополнительная задержка — около трёх минут.

## Проверяемые маршруты

- `https://sterlikova-ipoteka.ru/`;
- `https://sterlikova-ipoteka.ru/robots.txt`;
- `https://sterlikova-ipoteka.ru/sitemap.xml`;
- `https://sterlikova-ipoteka.ru/spasibo/`.

## Диагностика

При live-ошибке workflow загружает артефакт `production-smoke-diagnostics` с файлом `production-smoke.log`.

Типовые причины:

- `сеть/DNS/TLS` — домен не разрешается, сертификат ещё не выпущен или TLS-цепочка недействительна;
- `HTTP 404` — Pages опубликовал другой артефакт или путь отсутствует;
- `редирект на другой host` — custom domain либо redirect настроены неверно;
- неверный canonical/robots/sitemap — опубликован старый или неполный артефакт;
- отсутствующий privacy-маркер — `/spasibo/` не соответствует текущему контракту.

## Что проверяется вручную

Production smoke не заменяет:

- проверку `Settings → Pages`, DNS check и `Enforce HTTPS`;
- визуальную проверку на реальном телефоне и компьютере;
- клики по телефону, MAX и ВКонтакте;
- фактическую отправку Web3Forms;
- превью ссылки в социальных сетях;
- подключение Яндекс Вебмастера и Google Search Console.

Эти действия остаются в `docs/live-domain-acceptance.md` и issue №2/№5/№8.

## Критерий результата

Зелёный `production-smoke` подтверждает только следующее:

- custom domain отвечает по валидному HTTPS;
- ключевые публичные файлы доступны с HTTP 200;
- опубликованный контент соответствует проверенному Pages-контракту;
- robots, sitemap, canonical и минимальная страница благодарности не расходятся с репозиторием.
