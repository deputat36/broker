# Контракт серверного приёма онлайн-заявок

## Текущее состояние

Рабочая форма отправляет email-копию через Web3Forms:

```yaml
lead_capture:
  mode: "web3forms"
  web3forms_access_key: "UUID"
  web3forms_endpoint: "https://api.web3forms.com/submit"
  endpoint: ""
  thank_you_path: "/spasibo/"
  timeout_ms: 8000
  min_fill_ms: 3000
```

Supabase backend v2 подготовлен в исходниках, но не подключён к публичной форме:

- `supabase/migrations/202607130002_broker_leads_v2.sql`;
- `supabase/functions/broker-public-lead/index.ts`;
- `scripts/audit-supabase-backend.py`.

До применения миграции, деплоя Edge Function и полного smoke-теста `endpoint` должен оставаться пустым, а режим — `web3forms`.

## Целевая схема

После приёмки используется режим `hybrid`:

```text
Браузер
  ├─ Web3Forms → независимая email-копия
  └─ Supabase Edge Function → проверка → rate limit → база → событие → Telegram
```

Успешный ответ хотя бы одного канала позволяет клиенту перейти на `/spasibo/`. Ошибка дополнительного канала не должна уничтожать подготовленный текст или резервные способы связи.

Целевая конфигурация после smoke-теста:

```yaml
lead_capture:
  mode: "hybrid"
  web3forms_access_key: "UUID"
  web3forms_endpoint: "https://api.web3forms.com/submit"
  endpoint: "https://PROJECT.supabase.co/functions/v1/broker-public-lead"
  thank_you_path: "/spasibo/"
  timeout_ms: 8000
  min_fill_ms: 3000
```

## Публичная конфигурация и секреты

Файл `_config.yml` находится в открытом репозитории. В нём разрешено хранить только:

- публичный HTTPS URL Edge Function;
- публичный идентификатор Web3Forms;
- режим транспорта;
- числовые таймауты;
- путь страницы благодарности.

Запрещено размещать в браузере и репозитории:

- Supabase `service_role` key;
- токен Telegram-бота;
- Telegram chat ID, если его публикация не согласована;
- пароль или API-ключ CRM;
- SMTP-пароль;
- любой секрет, позволяющий читать таблицы или отправлять сообщения от имени сервиса.

Секреты должны храниться только в защищённом окружении Edge Function.

## HTTP-запрос

Метод: `POST`.

Обязательные заголовки:

```text
Accept: application/json
Content-Type: application/json
```

Cookie и пользовательские credentials не передаются.

Edge Function принимает только JSON-объект размером не более серверного `MAX_BODY_BYTES`. Значение по умолчанию в исходниках — 65 536 байт.

## Payload schema_version 1

Текущая форма версии 2 отправляет контракт `schema_version: 1`:

```json
{
  "schema_version": 1,
  "request_id": "4ad69d4d-e387-4f38-a7ac-c13b87aa160b",
  "form_version": "2",
  "submitted_at": "2026-07-13T12:00:00.000Z",
  "form_fill_ms": 28450,
  "source_page": "/uslugi/semeynaya-ipoteka/",
  "page_url": "https://sterlikova-ipoteka.ru/online-zayavka/?source=...",
  "page_title": "Онлайн-заявка ипотечному брокеру",
  "referrer": "https://sterlikova-ipoteka.ru/uslugi/semeynaya-ipoteka/",
  "tracking": {
    "first_touch": {},
    "last_touch": {},
    "current": {
      "utm_source": "vk",
      "utm_medium": "post",
      "utm_campaign": "family_mortgage"
    }
  },
  "client": {
    "name": "Анна",
    "phone": "+7 (900) 000-00-00",
    "phone_normalized": "79000000000",
    "city": "Воронеж",
    "preferred_contact": "MAX"
  },
  "mortgage": {
    "scenario": "Семейная ипотека",
    "object_type": "Квартира в новостройке",
    "object_price": "6 000 000 ₽",
    "down_payment": "1 200 000 ₽",
    "income_type": "Официальная работа",
    "bank_history": "Ранее не обращались",
    "comment": "Нужен предварительный разбор"
  },
  "qualification": {
    "status": "warm",
    "score": 55,
    "priority": "обработать в рабочий день",
    "reasons": ["оставлен корректный телефон", "понятна задача"]
  },
  "personal_data_consent": "yes",
  "consent": true,
  "spam_check": {
    "honeypot_empty": true,
    "form_fill_ms": 28450,
    "likely_bot": false
  }
}
```

Нельзя расширять payload паспортом, СНИЛС, банковскими реквизитами, кодами подтверждения, фотографиями документов или полным кредитным отчётом.

## Обязательная серверная валидация

Edge Function не доверяет клиентской проверке и самостоятельно контролирует:

1. точный `Origin` из разрешённого списка;
2. `POST` и `OPTIONS`;
3. `Content-Type: application/json`;
4. максимальный размер тела;
5. объектную структуру JSON;
6. `schema_version = 1`;
7. UUID или допустимый fallback-формат `request_id`;
8. имя, город и ипотечный сценарий;
9. российский телефон из 11 цифр, начинающийся с `7`;
10. согласие `personal_data_consent = yes` и `consent = true`;
11. honeypot и минимальное время заполнения;
12. длину каждого текстового поля;
13. допустимые протоколы URL;
14. безопасные значения квалификации.

Внутренние stack trace, ключи и полный текст ошибок базы не возвращаются в браузер.

## CORS

CORS сравнивает нормализованный Origin по точному совпадению. Проверка через `startsWith` запрещена.

Базовые разрешённые Origin в исходниках:

- `https://sterlikova-ipoteka.ru`;
- `https://www.sterlikova-ipoteka.ru`;
- `https://deputat36.github.io`.

Дополнительные dev-origin задаются через `ALLOWED_ORIGINS`. Запросы без Origin по умолчанию запрещены; временное разрешение для серверного smoke-теста контролируется `ALLOW_ORIGINLESS`.

## Идемпотентность

`request_id` создаётся в браузере до подготовки заявки.

Миграция добавляет частичный уникальный индекс:

```text
broker_leads_request_id_uidx
```

Поведение:

- первый запрос сохраняет заявку;
- повтор с тем же `request_id` не создаёт новую запись;
- повторный ответ возвращает прежний `lead_id` и `duplicate: true`;
- конкурентная повторная вставка дополнительно перехватывается по ошибке уникальности.

## Rate limit

Серверный rate limit реализован атомарной RPC-функцией:

```text
public.consume_broker_lead_rate_limit(...)
```

Отпечаток строится как SHA-256 от серверно определённого IP, User-Agent и последних четырёх цифр нормализованного телефона.

Таблица `broker_lead_rate_limits` хранит только:

- хешированный fingerprint;
- часовое окно;
- количество попыток;
- время первой и последней попытки;
- последний `request_id`.

IP, телефон и полный payload в таблице rate limit не сохраняются.

При превышении лимита возвращается HTTP `429` и `rate_limit_exceeded`.

Истёкшие счётчики удаляются функцией `purge_broker_lead_rate_limits`. Её нужно запускать по расписанию после подключения backend.

## Хранение заявки

Миграция расширяет существующую `public.broker_leads` без удаления legacy-полей.

Новые данные включают:

- `request_id`;
- версии контракта и формы;
- нормализованный телефон;
- исходные текстовые значения объекта, стоимости и взноса;
- способ подтверждения дохода и историю обращений в банки;
- tracking, qualification и spam_check в JSONB;
- исходный `raw_payload`;
- технический приоритет;
- статус уведомления.

RLS включён. Публичная anon-вставка в таблицы не требуется: запись выполняет Edge Function с серверным `service_role`.

Доступ к `raw_payload` должен быть ограничен уполномоченными сотрудниками. Срок хранения заявок и порядок удаления необходимо утвердить до включения режима `hybrid` и отразить в политике обработки данных.

## События

Таблица `broker_lead_events` хранит минимальную операционную историю:

- создание заявки;
- успешное Telegram-уведомление;
- ошибку уведомления;
- будущие изменения статуса и действия менеджера.

В техническом событии не нужно дублировать полный телефон и весь `raw_payload`.

## Telegram

Telegram-уведомление включается только при наличии серверных секретов:

- `TELEGRAM_BOT_TOKEN`;
- `TELEGRAM_CHAT_ID`.

Ошибка Telegram:

- не откатывает сохранённую заявку;
- переводит `notification_status` в `failed`;
- создаёт отдельное событие;
- не раскрывает токен клиенту.

## Ответы endpoint

Успешное создание — HTTP `201`:

```json
{
  "ok": true,
  "success": true,
  "duplicate": false,
  "lead_id": "UUID",
  "request_id": "UUID",
  "crm_status": "new",
  "technical_priority": "обработать в рабочий день",
  "qualification": {},
  "notification_status": "sent"
}
```

Повторный запрос — HTTP `200`:

```json
{
  "ok": true,
  "success": true,
  "duplicate": true,
  "lead_id": "UUID",
  "request_id": "UUID"
}
```

Ошибка валидации — HTTP `422`:

```json
{
  "ok": false,
  "success": false,
  "errors": ["invalid_phone"]
}
```

Не применена миграция или недоступен атомарный rate limit — HTTP `503`:

```json
{
  "ok": false,
  "success": false,
  "error": "backend_migration_required"
}
```

Клиентский код сохраняет Web3Forms, SMS, MAX, ВКонтакте, Web Share и копирование текста как независимые каналы.

## Порядок активации

1. Подтвердить фактический Supabase-проект.
2. Применить обе миграции в штатном migration workflow.
3. Проверить таблицы, индексы, RLS и RPC rate limit.
4. Развернуть `broker-public-lead` с серверными секретами.
5. Настроить точные `ALLOWED_ORIGINS`.
6. Настроить публичный браузерный вызов Edge Function согласно политике проекта.
7. Подключить тестовый Telegram-чат либо оставить уведомление `disabled`.
8. Выполнить success, duplicate, validation, spam, rate limit, CORS и timeout smoke-тесты.
9. Проверить сохранение заявки и событий непосредственно в Supabase.
10. Утвердить срок хранения и порядок удаления персональных данных.
11. Обновить политику сайта под фактическое серверное хранение.
12. Указать публичный HTTPS endpoint в `_config.yml`.
13. Перевести `lead_capture.mode` с `web3forms` на `hybrid`.
14. Повторить сквозной тест Web3Forms + Supabase + `/spasibo/`.

До выполнения всех пунктов endpoint должен оставаться пустым.
