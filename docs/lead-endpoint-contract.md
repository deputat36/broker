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

Supabase backend подготовлен в репозитории, но не подключён к публичной форме.

Основные файлы:

- `supabase/migrations/202607070001_create_broker_leads.sql`;
- `supabase/migrations/202607130002_broker_leads_v2.sql`;
- `supabase/migrations/202607130003_broker_lead_preparation.sql`;
- `supabase/migrations/202607130004_broker_lead_notification_summary.sql`;
- `supabase/migrations/202607130005_broker_lead_notification_delivery.sql`;
- `supabase/migrations/202607130006_broker_lead_notification_manual_retry.sql`;
- `supabase/functions/broker-public-lead/index.ts`;
- `supabase/functions/broker-public-lead/handler.ts`;
- `supabase/functions/broker-notification-retry/index.ts`;
- `scripts/audit-supabase-backend.py`;
- `scripts/audit-notification-retry.py`;
- `docs/preparation-context-contract.md`;
- `docs/notification-summary-contract.md`;
- `docs/notification-retry-contract.md`;
- `docs/supabase-backend-smoke.md`;
- `docs/supabase-notification-smoke.md`;
- `docs/supabase-notification-retry-smoke.md`.

До применения шести миграций, деплоя Edge Function и полного smoke-теста `endpoint` должен оставаться пустым, режим — `web3forms`.

## Целевая схема

После приёмки публичного backend используется режим `hybrid`:

```text
Браузер
  ├─ Web3Forms → независимая email-копия
  └─ Supabase Edge Function
       → CORS и валидация
       → идемпотентность request_id
       → атомарный rate limit
       → broker_leads
       → broker_lead_events
       → атомарный claim уведомления
       → защищённая сводка
       → Telegram
```

Закрытый ручной retry работает отдельно:

```text
Администратор
  → broker-notification-retry без CORS
  → admin token
  → failed-only RPC
  → атомарный claim
  → защищённая сводка
  → Telegram
```

Успешный ответ хотя бы одного публичного канала позволяет перейти на `/spasibo/`. Ошибка Supabase или Telegram не должна уничтожать подготовленный текст и резервные способы связи.

Целевая публичная конфигурация после smoke-теста:

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

URL административной retry-функции не публикуется в `_config.yml`, HTML или JavaScript сайта.

## Публичная конфигурация и секреты

В открытом `_config.yml` разрешено хранить только:

- публичный HTTPS URL основной Edge Function;
- публичный идентификатор Web3Forms;
- режим транспорта;
- числовые таймауты;
- путь страницы благодарности.

Запрещено публиковать:

- Supabase `service_role` key;
- Telegram bot token;
- закрытый Telegram chat ID;
- `NOTIFICATION_ADMIN_TOKEN`;
- пароль или API-ключ CRM;
- SMTP-пароль;
- секрет, позволяющий читать таблицы или отправлять сообщения от имени сервиса.

Секреты хранятся только в окружении соответствующей Edge Function.

## HTTP-запрос публичной формы

Метод: `POST`.

Заголовки:

```text
Accept: application/json
Content-Type: application/json
```

Cookie и пользовательские credentials не передаются.

Максимальный размер JSON контролируется `MAX_BODY_BYTES`. Значение по умолчанию — 65 536 байт.

## Payload schema_version 1

Текущая форма версии 2 использует обратносуместимый контракт:

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
      "utm_campaign": "complex_mortgage"
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
    "scenario": "Банк отказал в ипотеке",
    "object_type": "Квартира на вторичном рынке",
    "object_price": "6 000 000 ₽",
    "down_payment": "1 200 000 ₽",
    "income_type": "Официальная работа",
    "bank_history": "Был один отказ",
    "comment": "Нужен первичный разбор"
  },
  "preparation": {
    "context_version": 1,
    "active": true,
    "journey_type": "Сложный региональный маршрут",
    "journey_stage": "После изучения маршрута подготовки",
    "scenario_slug": "otkazali-v-ipoteke",
    "completed_checks": ["diagnosis", "finances"],
    "completed_labels": ["Зафиксирован этап отказа", "Проверены кредиты и карты"],
    "remaining_questions": "Нужно понять, связан ли отказ с объектом"
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

Нельзя расширять payload паспортом, СНИЛС, реквизитами, кодами подтверждения, фотографиями документов или полным кредитным отчётом.

## Обязательная серверная валидация

Основная Edge Function самостоятельно контролирует:

1. точный Origin;
2. `POST` и `OPTIONS`;
3. JSON Content-Type;
4. максимальный размер тела;
5. объектную структуру JSON;
6. `schema_version = 1`;
7. UUID или допустимый fallback `request_id`;
8. имя, город и сценарий;
9. российский телефон;
10. согласие;
11. honeypot и минимальное время заполнения;
12. длины текстов;
13. безопасные URL;
14. допустимую квалификацию.

Stack trace, ключи и полный текст ошибок базы не возвращаются в браузер.

## CORS

Origin публичной функции сравнивается по точному нормализованному совпадению. `startsWith` запрещён.

Базовые Origin:

- `https://sterlikova-ipoteka.ru`;
- `https://www.sterlikova-ipoteka.ru`;
- `https://deputat36.github.io`.

Запросы без Origin по умолчанию запрещены. Временное разрешение для серверного smoke контролируется `ALLOW_ORIGINLESS`.

Административная функция `broker-notification-retry` не устанавливает `Access-Control-Allow-Origin` и не предназначена для браузерного вызова.

## Идемпотентность

`request_id` создаётся до подготовки заявки. Частичный уникальный индекс не позволяет создать вторую строку.

Поведение:

- первый запрос сохраняет заявку;
- повтор возвращает прежний `lead_id` и `duplicate: true`;
- конкурентная вставка перехватывается по уникальному индексу;
- duplicate может восстановить только незавершённое `pending` или зависшее `sending` уведомление;
- `sent`, `failed` и `disabled` автоматически повторно не отправляются.

## Rate limit

RPC `public.consume_broker_lead_rate_limit(...)` атомарно считает запросы. Fingerprint строится на сервере и не сохраняет исходный IP или полный телефон.

При превышении возвращается HTTP `429` и `rate_limit_exceeded`.

## Хранение заявки

`public.broker_leads` хранит:

- request ID и версии;
- нормализованный телефон;
- ипотечные вводные;
- tracking, qualification и spam_check;
- защищённый `raw_payload`;
- очищенный preparation;
- технический приоритет;
- статус и метаданные уведомления;
- счётчики и код причины ручного retry.

RLS включён. Публичная anon-вставка не используется: запись выполняется серверной ролью.

## Уведомления

Состояния:

- `disabled`;
- `pending`;
- `sending`;
- `sent`;
- `failed`.

Основная Edge Function получает атомарный claim через `claim_broker_lead_notification`, формирует текст через `broker_lead_notification_summary`, отправляет Telegram и завершает попытку через `complete_broker_lead_notification`.

Обычные параллельные и повторные запросы не должны отправлять два сообщения. Зависшее `sending` можно восстановить после 15 минут.

Telegram API не предоставляет идемпотентный ключ. Если сообщение принято, а фиксация `sent` не выполнена, после аварийного окна возможен повтор с тем же request ID. Этот риск проверяется и принимается отдельно.

## Ручной retry

RPC `request_broker_lead_notification_retry` разрешает только переход `failed → pending` и принимает код причины из белого списка.

Закрытая Edge Function:

- требует отдельный admin token;
- не разрешает CORS;
- не подключается к публичной форме;
- повторно использует атомарный claim и защищённую сводку;
- возвращает только технический статус и счётчики;
- не возвращает персональные данные.

`failed` не повторяется автоматически. Каждая новая попытка требует отдельного административного решения.

## Контроль очереди

RPC `broker_lead_notification_queue_health` возвращает агрегаты по статусам:

- количество записей;
- самые старые технические времена;
- количество зависших `sending`;
- максимальное число попыток;
- общее количество ручных retry.

Функция доступна только `service_role` и не возвращает идентификаторы заявок, имена, телефоны, города, URL или тексты.

## События

`broker_lead_events` хранит минимальную историю:

- `created`;
- `notification_sent`;
- `notification_failed`;
- `notification_retry_requested`;
- `notification_retry_sent`;
- `notification_retry_failed`.

В событии не дублируются полный телефон, raw payload, текст уведомления или секреты.

## Fail-closed и откат

Если миграции не применены, публичный endpoint должен возвращать безопасный `backend_migration_required`, а не молча принимать неполную заявку.

При нестабильности выполняется откат конфигурации:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

Для отключения ручного retry удаляется или заменяется `NOTIFICATION_ADMIN_TOKEN`, административная функция не публикуется. Миграции и данные оперативно не удаляются.

## Условие включения hybrid

Hybrid включается только после:

1. применения шести миграций;
2. проверки CORS публичной функции;
3. проверки отсутствия CORS у административной функции;
4. проверки идемпотентности и rate limit;
5. проверки preparation;
6. проверки атомарного claim;
7. проверки ручного retry и агрегированной очереди;
8. подтверждения Web3Forms email;
9. подтверждения Telegram-чата;
10. проверки duplicate и аварийного окна;
11. утверждения срока хранения и ответственного;
12. обновления политики обработки данных.

Deploy закрытой retry-функции и включение публичного `hybrid` являются двумя отдельными решениями и принимаются только после соответствующих smoke-тестов.