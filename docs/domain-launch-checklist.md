# Чек-лист запуска домена

Основной домен сайта:

`sterlikova-ipoteka.ru`

## Что уже сделано в репозитории

- В `_config.yml` указан `url: "https://sterlikova-ipoteka.ru"`.
- В `_config.yml` указан `baseurl: ""`.
- Добавлен файл `CNAME` со строкой `sterlikova-ipoteka.ru`.
- Обновлен `site.webmanifest` под корень сайта.
- `robots.txt` и `sitemap.xml` используют `absolute_url` и должны подтянуть новый домен после сборки.

## Что проверить в DNS

У регистратора домена нужно проверить:

- A-записи для основного домена указывают на GitHub Pages.
- `www` настроен как CNAME на `deputat36.github.io`.
- Нет парковочных A-записей регистратора.
- Нет лишних редиректов у регистратора.
- Нет wildcard-записи `*`, если она не нужна.

## Что проверить в GitHub Pages

В репозитории открыть:

`Settings → Pages`

Проверить:

- source: GitHub Actions;
- custom domain: `sterlikova-ipoteka.ru`;
- DNS check успешный;
- включен `Enforce HTTPS`.

Если HTTPS пока недоступен, нужно подождать обновления DNS и проверки сертификата.

## Что открыть после запуска

- `https://sterlikova-ipoteka.ru/`
- `https://sterlikova-ipoteka.ru/robots.txt`
- `https://sterlikova-ipoteka.ru/sitemap.xml`
- `https://sterlikova-ipoteka.ru/site.webmanifest`
- `https://sterlikova-ipoteka.ru/404.html`

## Что проверить на сайте

- Главная открывается без `/broker/` в адресе.
- Внутренние ссылки ведут на корень домена.
- Картинки и CSS загружаются без ошибок.
- Мобильное меню открывается и закрывается.
- Кнопка телефона работает.
- MAX копирует номер.
- ВК открывается.
- Калькулятор считает платеж.
- В sitemap нет старого адреса GitHub Pages.

## После технического запуска

- Добавить домен в Яндекс Вебмастер.
- Добавить домен в Google Search Console.
- Отправить `sitemap.xml` на переобход.
- Проверить сниппет ссылки во ВКонтакте и мессенджерах.
- Подключить Яндекс Метрику, когда будет ID счетчика.
