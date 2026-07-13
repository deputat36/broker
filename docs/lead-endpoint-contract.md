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

Supabase backend подготовлен в исходниках, но не подключён к публичной форме:

- `supabase/migrations/202607070001_create_broker_leads.sql`;
- `supabase/migrations/202607130002_broker_leads_v2.sql`;
- `supabase/migrations/202607130003_broker_lead_preparation.sql`;
- `supabase/functions/broker-public-lead/index.ts`;
- `scripts/audit-supabase-backend.py`;
- `docs/preparation-context-contract.md`;
- `docs/supabase-backend-smoke.md`.

До применения миграций, деплоя Edge Function и полного smoke-теста `endpoint` должен оставаться пустым, а режим — `web3forms`.

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

В открытом `_config.yml` разрешено хранить только:

- публичный HTTPS URL Edge Function;
- публичный идентификатор Web3Forms;
- режим транспорта;
- числовые таймауты;
- путь страницы благодарности.

Запрещено публиковать:

- Supabase `service_role` key;
- токен Telegram-бота;
- закрытый Telegram chat ID без согласования;
- пароль или API-ключ CRM;
- SMTP-пароль;
- любой секрет, позволяющий читать таблицы или отправлять сообщения от имени сервиса.

Секреты хранятся только в защищённом окружении Edge Function.

## HTTP-запрос

Метод: `POST`.

Обязательные заголовки:

```text
Accept: application/json
Content-Type: application/json
```

Cookie и пользовательские credentials не передаются.

Edge Function принимает только JSON-объект размером не более `MAX_BODY_BYTES`. Значение по умолчанию — 65 536 байт.

## Payload schema_version 1

Публичный контракт остаётся `schema_version: 1`. Новые необязательные поля добавляются без нарушения старых заявок.

```json
{
  "schema_version": 1,
  "request_id": "4ad69d4d-e387-4f38-a7ac-c13b87aa160b",
  "form_version": "2",
  "submitted_at": "2026-07-13T12:00:00.000Z",
  "form_fill_ms": 28450,
  "source_page": "/geo/borisoglebsk/otkazali-v-ipoteke/",
  "page_url": "https://sterlikova-ipoteka.ru/online-zayavka/?source=...",
  "page_title": "Онлайн-заявка ипотечному брокеру",
  "referrer": "https://sterlikova-ipoteka.ru/geo/borisoglebsk/otkazali-v-ipoteke/",
  "tracking": {
    "first_touch": {},
    "last_touch": {},
    "current": {
      "utm_source": "vk",
      "utm_medium": "post",
      "utm_campaign": "mortgage"
    }
  },
  "client": {
    "name": "Анна",
    "phone": "+7 (900) 000-00-00",
    "phone_normalized": "79000000000",
    "city": "Борисоглебск",
    "preferred_contact": "MAX"
  },
  "mortgage": {
    "scenario": "Банк отказал в ипотеке",
    "object_type": "Квартира на вторичном рынке",
    "object_price": "4 500 000 ₽",
    "down_payment": "900 000 ₽",
    "income_type": "Официальная работа",
    "bank_history": "Была одна заявка",
    "comment": "Нужен предварительный разбор"
  },
  "preparation": {
    "context_version": 1,
    "active": true,
    "journey_type": "Сложный региональный маршрут",
    "journey_stage": "После изучения маршрута подготовки",
    "scenario_slug": "otkazali-v-ipoteke",
    "completed_checks": ["diagnosis", "finances"],
    "completed_labels": [
      "Зафиксировал(а) банк, дату и этап отказа",
      "Проверил(а) кредиты, карты и ежемесячные платежи"
    ],
    "remaining_questions": "Нужно проверить, связан ли отказ с объектом"
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

`preparation` необязателен. Его отдельный контракт описан в `docs/preparation-context-contract.md`.

Нельзя расширять payload паспортом, СНИЛС, банковскими реквизитами, кодами подтверждения, фотографиями документов или полным кредитным отчётом.

## Обязательная серверная валидация

Edge Function не доверяет клиентской проверке и самостоятельно контролирует:

1. точный `Origin` из разрешённого списка;
2. методы `POST` и `OPTIONS`;
3. `Content-Type: application/json`;
4. максимальный размер тела;
5. объектную структуру JSON;
6. `schema_version = 1`;
7. UUID или допустимый fallback-формат `request_id`;
8. имя, город и ипотечный сценарий;
9. российский телефон из 11 цифр, начинающийся с `7`;
10. согласие `personal_data_consent = yes` и `consent = true`;
11. honeypot и минимальное время заполнения;
12. длину текстовых полей;
13. допустимые URL-протоколы;
14. безопасные значения квалификации.

Объект `preparation` остаётся необязательным. Миграция `202607130003` извлекает его из защищённого `raw_payload` по белому списку:

- ограничивает количество отметок четырьмя;
- принимает только `diagnosis`, `finances`, `documents`, `next_step`;
- ограничивает длину подписей и вопросов;
- принимает только четыре известных scenario slug;
- не переносит произвольные вложенные поля в рабочий JSON `preparation`.

Внутренние stack trace, ключи и полный текст ошибок базы не возвращаются в браузер.

## CORS

CORS сравнивает нормализованный Origin по точному совпадению. Проверка через `startsWith` запрещена.

Базовые разрешённые Origin:

- `https://sterlikova-ipoteka.ru`;
- `https://www.sterlikova-ipoteka.ru`;
- `https://deputat36.github.io`.

Дополнительные dev-origin задаются через `ALLOWED_ORIGINS`. Запросы без Origin по умолчанию запрещены; временное разрешение для серверного smoke-теста контролируется `ALLOW_ORIGINLESS`.

## Идемпотентность

`request_id` создаётся в браузере до подготовки заявки.

Миграция добавляет частичный уникальный индекс `broker_leads_request_id_uidx`.

Поведение:

- первый запрос сохраняет заявку;
- повтор с тем же `request_id` не создаёт новую запись;
- повторный ответ возвращает прежний `lead_id` и `duplicate: true`;
- конкурентная повторная вставка дополнительно перехватывается по ошибке уникальности.

## Rate limit

Серверный rate limit реализован атомарной RPC-функцией `public.consume_broker_lead_rate_limit(...)`.

Отпечаток строится как SHA-256 от серверно определённого IP, User-Agent и последних четырёх цифр нормализованного телефона.

Таблица хранит только:

- хешированный fingerprint;
- часовое окно;
- количество попыток;
- время первой и последней попытки;
- последний `request_id`.

IP, телефон и полный payload в таблице rate limit не сохраняются.

При превышении лимита возвращается HTTP `429` и `rate_limit_exceeded`. Истёкшие счётчики удаляются функцией `purge_broker_lead_rate_limits`.

## Хранение заявки

Базовая миграция расширяет `public.broker_leads` без удаления legacy-полей.

Хранятся:

- `request_id`, версии контракта и формы;
- нормализованный телефон;
- исходные текстовые значения объекта, стоимости и взноса;
- способ подтверждения дохода и банковская история;
- tracking, qualification, spam_check и `raw_payload` в JSONB;
- технический приоритет и статус уведомления;
- `journey_type`, `journey_stage`, `journey_scenario_slug`;
- очищенный `preparation`;
- `preparation_completed`;
- `remaining_questions`.

Исходный `mortgage.comment` хранится отдельно и не должен содержать автоматически склеенный контекст подготовки.

RLS включён. Публичная anon-вставка не требуется: запись выполняет Edge Function с серверным `service_role`.

Доступ к `raw_payload` ограничивается уполномоченными сотрудниками. Срок хранения и порядок удаления утверждаются до режима `hybrid` и отражаются в политике обработки данных.

## События

`broker_lead_events` хранит минимальную операционную историю:

- создание заявки;
- успешное Telegram-уведомление;
- ошибку уведомления;
- будущие изменения статуса и действия менеджера.

В событии не нужно дублировать полный телефон и весь `raw_payload`.

## Telegram

Telegram-уведомление включается только при наличии серверных секретов `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID`.

Ошибка Telegram не откатывает сохранённую заявку. Она переводит `notification_status` в `failed` и создаёт техническое событие.

## Политика обработки данных

До подключения Supabase политика обработки данных должна быть обновлена под фактическое серверное хранение, сроки, доступ, удаление и возможные уведомления.

Поля подготовки добровольны, не являются оценкой вероятности одобрения и не заменяют решение банка.

## Включение endpoint

Порядок:

1. подтвердить Supabase project ref;
2. применить все три миграции;
3. задать secrets Edge Function;
4. выполнить `docs/supabase-backend-smoke.md`;
5. обновить политику обработки данных;
6. указать HTTPS endpoint;
7. перевести режим в `hybrid`;
8. проверить Web3Forms, Supabase, Telegram и `/spasibo/` одним request ID.

До этого endpoint должен оставаться пустым.

## Откат

При нестабильной работе вернуть:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

Web3Forms и резервные способы продолжают работать. Таблицы и миграции не удаляются при оперативном откате; сначала отключается только клиентский endpoint.