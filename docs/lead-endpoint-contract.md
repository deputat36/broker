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

Supabase backend подготовлен в репозитории, но не подключён к публичной форме. До завершения всех smoke-тестов endpoint должен оставаться пустым, режим — `web3forms`.

Единственный актуальный порядок 11 миграций находится в `docs/supabase-migration-order.md`. Частичные списки в старых заметках не являются планом deploy.

Основные компоненты:

- `supabase/functions/broker-public-lead/index.ts`;
- `supabase/functions/broker-public-lead/handler.ts`;
- `supabase/functions/broker-delivery-receipt/index.ts`;
- `supabase/functions/broker-notification-retry/index.ts`;
- `supabase/functions/broker-notification-health/index.ts`;
- `scripts/audit-supabase-readiness.py`;
- специализированные контракты и smoke-файлы в `docs/`.

## Целевая схема

После отдельной приёмки публичного backend может использоваться режим `hybrid`:

```text
Браузер
  ├─ Web3Forms → независимая email-копия
  ├─ broker-public-lead
  │    → точный CORS
  │    → валидация schema_version=1
  │    → идемпотентность request_id
  │    → атомарный rate limit
  │    → broker_leads и broker_lead_events
  │    → operational guard
  │    → атомарный claim уведомления
  │    → защищённая Telegram-сводка
  │    → минимальный публичный response
  └─ broker-delivery-receipt
       → только request_id и delivery_state=both
       → монотонное подтверждение supabase_only → both
```

Закрытые административные функции работают отдельно от сайта:

```text
Администратор
  ├─ broker-notification-retry → failed-only retry
  └─ broker-notification-health → обезличенный контроль очереди
```

Их URL и секреты не публикуются в `_config.yml`, HTML или JavaScript.

## Публичная конфигурация и секреты

В открытом репозитории разрешены только:

- публичный HTTPS URL основной Edge Function после приёмки;
- производный URL receipt-handler без secrets;
- публичный идентификатор Web3Forms;
- режим транспорта;
- числовые таймауты;
- путь страницы подтверждения.

Запрещено публиковать:

- `SUPABASE_SERVICE_ROLE_KEY`;
- Telegram bot token и chat ID;
- `NOTIFICATION_ADMIN_TOKEN`;
- `NOTIFICATION_MONITOR_TOKEN`;
- CRM, SMTP и другие серверные secrets.

Service_role используется только внутри доверенного серверного кода. Для публичных и закрытых Edge Functions `verify_jwt = false` допустим только вместе с их собственной обязательной проверкой Origin или отдельного bearer token.

## HTTP-запрос формы

Метод: `POST`.

```text
Accept: application/json
Content-Type: application/json
```

Cookie и пользовательские credentials не передаются. Максимальный размер тела контролируется `MAX_BODY_BYTES`.

## Payload schema_version 1

Обязательные верхнеуровневые поля:

- `schema_version = 1`;
- `request_id`;
- `form_version`;
- `submitted_at`;
- `form_fill_ms`;
- `source_page`;
- `client`;
- `mortgage`;
- `personal_data_consent`;
- `consent`;
- `spam_check`.

Поддерживаются:

- `tracking`;
- `qualification`;
- необязательный `preparation` по `docs/preparation-context-contract.md`.

Payload нельзя расширять паспортом, СНИЛС, реквизитами карт, кодами подтверждения, фотографиями документов или полным кредитным отчётом.

## Обязательная серверная валидация

Edge Function самостоятельно контролирует:

1. точный Origin и CORS;
2. методы `POST` и `OPTIONS`;
3. JSON Content-Type;
4. размер и объектную структуру тела;
5. `schema_version`;
6. UUID или разрешённый fallback request ID;
7. имя, город, сценарий и российский телефон;
8. согласие;
9. honeypot и минимальное время заполнения;
10. длины текстов и безопасные URL;
11. qualification и preparation whitelist.

Stack trace, SQL-текст, ключи и персональные сведения в ошибочных ответах запрещены.

## Идемпотентность

`request_id` создаётся браузером до отправки. Частичный уникальный индекс не позволяет создать вторую строку.

Поведение:

- первый запрос сохраняет одну заявку;
- повтор возвращает `duplicate: true` и тот же request ID;
- конкурентная вставка перехватывается по уникальному индексу;
- обычный duplicate может завершить только ожидающее или зависшее уведомление;
- restricted, hold и anonymized duplicate не запускает доставку;
- `sent`, `failed` и `disabled` автоматически повторно не отправляются.

Внутренний `lead_id` не возвращается браузеру.

## Минимальный публичный success response

Новая заявка получает HTTP `201`, duplicate — HTTP `200`.

Оба ответа содержат ровно один envelope:

```json
{
  "ok": true,
  "success": true,
  "duplicate": false,
  "request_id": "<номер обращения>",
  "notification_status": "sent"
}
```

Поле `duplicate` меняется для повтора. Restricted-заявка получает `notification_status: "disabled"`.

Публичный response не содержит:

- `lead_id`;
- CRM status;
- `technical_priority`;
- `qualification`;
- контактные и ипотечные сведения;
- tracking и `raw_payload`;
- признаки privacy или retention.

Полный контракт: `docs/public-lead-response-contract.md`.

## Безопасный error response

Все ошибки используют единый envelope с `error_code` из белого списка и correlation request ID. Только HTTP `429` дополнительно содержит `retry_after_seconds`.

Полный контракт: `docs/public-lead-error-contract.md`.

## Rate limit

RPC `consume_broker_lead_rate_limit` атомарно считает запросы. Fingerprint создаётся сервером и не хранит исходный IP или полный телефон.

При превышении возвращается HTTP `429` и `rate_limit_exceeded`. Очистка выполняется через `purge_broker_lead_rate_limits`.

## Хранение заявки

`broker_leads` хранит:

- request ID и версии;
- контактные и ипотечные вводные;
- tracking, qualification и spam_check;
- защищённый `raw_payload`;
- очищенный preparation;
- технический приоритет;
- notification status, попытки и retry metadata;
- privacy, retention и operational flags;
- `client_delivery_state` и время его обновления.

RLS включён. Публичная anon-вставка не используется.

## Состояние каналов

После завершения независимых попыток браузер определяет:

- `web3forms_only`;
- `supabase_only`;
- `both`.

В Supabase хранится только `supabase_only` или `both`, поскольку строка появляется только после успешного серверного приёма. `web3forms_only` существует в email-канале без обязательной Supabase-строки.

Receipt-handler принимает только техническую квитанцию:

```json
{
  "request_kind": "delivery_receipt",
  "request_id": "<номер обращения>",
  "delivery_state": "both"
}
```

Он возвращает одинаковый HTTP `204` для существующей, отсутствующей и restricted-заявки. Состояние не показывается клиенту и не меняет `/spasibo/`.

Полный контракт: `docs/hybrid-delivery-state-contract.md`.

## Уведомления

Состояния:

- `disabled`;
- `pending`;
- `sending`;
- `sent`;
- `failed`.

Основная функция использует:

- `claim_broker_lead_notification`;
- `broker_lead_notification_summary`;
- `complete_broker_lead_notification`.

Telegram не имеет идемпотентного ключа, поэтому аварийное окно после фактической отправки, но до фиксации `sent`, проверяется отдельным smoke-тестом.

## Ручной retry и очередь

`request_broker_lead_notification_retry` разрешает только подтверждённый переход `failed → pending` и принимает reason code из белого списка.

`broker_lead_notification_queue_health` возвращает только агрегаты без идентификаторов и персональных данных.

Restricted, hold и anonymized заявки исключены из retry, Telegram summary и health-очереди.

## Retention

Retention выключен по умолчанию.

Перед любым apply выполняется:

- `broker_lead_retention_preview`;
- проверка terminal status;
- проверка `retention_hold`;
- проверка завершённого notification status;
- точное подтверждение `apply_broker_lead_retention`.

Лиды обезличиваются, а не удаляются физически. Cron не создаётся до отдельной приёмки.

## Индивидуальные privacy-запросы

Процесс использует точную пару `lead_id + request_id` и отдельные RPC preview/start/verify/apply/cancel.

Он не ищет заявки по телефону, не хранит документы проверки личности и не выполняет обезличивание без статуса `verified`.

При ограничении обработки устанавливаются `processing_restricted` и `retention_hold`.

## Operational guard

`broker_lead_operational_guard` и `broker_lead_operational_snapshot` защищают ограниченную заявку от:

- уведомлений;
- ручного retry;
- CRM update;
- follow-up;
- экспорта;
- обычных событий.

Прямой service_role доступ технически привилегирован, но не является разрешённым операционным способом обхода guard.

## Fail-closed и откат

Если миграции не применены, endpoint возвращает `backend_migration_required`, а не принимает неполную заявку.

Откат публичного канала:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

Секреты закрытых функций ротируются или удаляются отдельно. Миграции и реальные данные оперативно не удаляются.

## Условие включения hybrid

Hybrid включается только после:

1. применения всех 11 миграций по каноническому порядку;
2. успешного `audit-supabase-readiness.py`;
3. проверки CORS и per-function security config для четырёх функций;
4. проверки идемпотентности и rate limit;
5. проверки preparation;
6. проверки минимального public response и безопасных ошибок;
7. проверки интерфейса ошибок;
8. проверки `web3forms_only`, `supabase_only`, `both` и receipt-handler;
9. проверки атомарного Telegram claim;
10. проверки ручного retry и health;
11. проверки retention preview/apply;
12. проверки privacy workflow и operational guard;
13. подтверждения Web3Forms email;
14. утверждения ответственных, сроков хранения и процедур отката;
15. обновления политики обработки данных под фактически развёрнутый канал.

Deploy закрытых функций и включение публичного `hybrid` — разные решения.
