# Privacy явного payload онлайн-заявки

## Проблема

Пользователь может открыть форму по ссылке, содержащей query-параметры или fragment. В них случайно могут оказаться телефон, имя, номер обращения, внутренний token или другое значение, которое не относится к анкете.

Ранее явный payload после нажатия «Отправить заявку онлайн» использовал:

- полный `window.location.href`;
- полный `document.referrer`.

Из-за этого случайные значения могли попасть в Web3Forms email, существовавшую тогда дублирующую полную JSON-копию заявки или будущий серверный канал вместе с заявкой.

## Явный payload онлайн-заявки

`assets/js/online-application.js` получает контекст через `window.getSiteSafePageContext`, который предоставляет `assets/js/main.js`.

В payload входят:

- текущая страница как `origin + path` без query и fragment;
- внутренний referrer как `origin + path` без query и fragment;
- внешний referrer только как origin;
- UTM-метки и рекламные click ID отдельно по фиксированному allowlist.

## Fail-closed fallback

Если общий helper недоступен из-за сбоя `main.js`, модуль формы не возвращается к сырому `window.location.href` или полному `document.referrer`.

Fallback передаёт:

- безопасный `origin + path` текущей страницы;
- пустой referrer.

Потеря части атрибуции безопаснее передачи неизвестных параметров URL.

## Что не меняется

- содержательные поля, которые пользователь сам ввёл и проверил;
- request ID;
- квалификация обращения;
- Web3Forms и будущий Supabase как каналы доставки;
- отдельные разрешённые UTM и click ID;
- 90-дневная локальная атрибуция и её срок.

## Автоматическая проверка

```bash
python3 scripts/audit-application-payload-privacy.py ./_site
```

Аудит проверяет исходный и собранный JavaScript из Pages-артефакта, публичную политику, общий safe context и подключение к post-build.

Запрещённые маркеры:

```text
page_url: window.location.href
referrer: document.referrer || ''
fields_json
```
