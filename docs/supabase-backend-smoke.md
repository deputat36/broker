# Smoke-тест Supabase backend v2

## Назначение

Чек-лист подтверждает, что Supabase может безопасно работать вторым каналом рядом с Web3Forms.

До завершения всех проверок сайт сохраняет:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

Тесты выполняются только в подтверждённом проекте и с явно тестовыми данными.

## Переменные

```bash
export FUNCTION_URL="https://PROJECT.supabase.co/functions/v1/broker-public-lead"
export SITE_ORIGIN="https://sterlikova-ipoteka.ru"
export REQUEST_ID="00000000-0000-4000-8000-000000000001"
```

Не публиковать `SUPABASE_SERVICE_ROLE_KEY`, Telegram bot token, chat ID и CRM-ключи.

## 1. Проверка миграций

Применить строго по порядку:

1. `202607070001_create_broker_leads.sql`;
2. `202607130002_broker_leads_v2.sql`;
3. `202607130003_broker_lead_preparation.sql`;
4. `202607130004_broker_lead_notification_summary.sql`;
5. `202607130005_broker_lead_notification_delivery.sql`.

Проверить таблицы:

```sql
select to_regclass('public.broker_leads');
select to_regclass('public.broker_lead_events');
select to_regclass('public.broker_lead_rate_limits');
```

Проверить колонки:

```sql
select column_name, data_type
from information_schema.columns
where table_schema = 'public'
  and table_name = 'broker_leads'
  and column_name in (
    'request_id',
    'schema_version',
    'raw_payload',
    'tracking',
    'qualification',
    'spam_check',
    'journey_type',
    'journey_stage',
    'journey_scenario_slug',
    'preparation',
    'preparation_completed',
    'remaining_questions',
    'notification_status',
    'notification_attempt_count',
    'notification_attempted_at',
    'notification_sent_at',
    'notification_last_error'
  )
order by column_name;
```

Проверить функции:

```sql
select routine_name
from information_schema.routines
where routine_schema = 'public'
  and routine_name in (
    'consume_broker_lead_rate_limit',
    'purge_broker_lead_rate_limits',
    'sync_broker_lead_preparation',
    'broker_lead_notification_summary',
    'claim_broker_lead_notification',
    'complete_broker_lead_notification'
  )
order by routine_name;
```

Ожидается:

- частичный уникальный индекс request ID;
- RLS включён;
- публичная anon-вставка отсутствует;
- preparation trigger активен;
- notification constraint допускает только `pending`, `sending`, `sent`, `failed`, `disabled`;
- публичный доступ к серверным RPC отсутствует.

## 2. Проверка конфигурации Edge Function

Обязательные secrets:

- `SUPABASE_URL`;
- `SUPABASE_SERVICE_ROLE_KEY`.

Настройки:

```text
ALLOWED_ORIGINS=https://sterlikova-ipoteka.ru,https://www.sterlikova-ipoteka.ru
ALLOW_ORIGINLESS=false
RATE_LIMIT_PER_HOUR=8
MIN_FILL_MS=1500
MAX_BODY_BYTES=65536
TELEGRAM_TIMEOUT_MS=5000
```

Telegram secrets подключаются только для подтверждённого тестового чата.

## 3. CORS preflight

Разрешённый Origin:

```bash
curl -i -X OPTIONS "$FUNCTION_URL" \
  -H "Origin: $SITE_ORIGIN" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"
```

Ожидается HTTP `204`, точный `Access-Control-Allow-Origin` и `Vary: Origin`.

Запрещённый Origin должен получить HTTP `403` без разрешающего заголовка.

## 4. Валидный payload

Использовать заявку со `schema_version: 1`, уникальным request ID, тестовым телефоном, согласием и временем заполнения больше `MIN_FILL_MS`.

Для сложного маршрута добавить:

```json
{
  "preparation": {
    "context_version": 1,
    "active": true,
    "journey_type": "Сложный региональный маршрут",
    "journey_stage": "После изучения маршрута подготовки",
    "scenario_slug": "otkazali-v-ipoteke",
    "completed_checks": ["diagnosis", "finances"],
    "completed_labels": [
      "Зафиксирован банк и этап отказа",
      "Проверены кредиты и карты"
    ],
    "remaining_questions": "Нужно понять, связан ли отказ с объектом"
  }
}
```

Отправить:

```bash
curl -i -X POST "$FUNCTION_URL" \
  -H "Origin: $SITE_ORIGIN" \
  -H "Content-Type: application/json" \
  --data-binary @/tmp/broker-lead.json
```

Ожидается HTTP `201`, `success: true`, новый `lead_id` и тот же request ID.

## 5. Проверка записи

```sql
select
  id,
  request_id,
  status,
  phone_normalized,
  scenario,
  source_page,
  journey_type,
  journey_stage,
  journey_scenario_slug,
  preparation,
  preparation_completed,
  remaining_questions,
  comment,
  notification_status,
  notification_attempt_count,
  notification_attempted_at,
  notification_sent_at,
  notification_last_error
from public.broker_leads
where request_id = '00000000-0000-4000-8000-000000000001';
```

Проверить:

- одна строка;
- телефон нормализован;
- комментарий клиента не содержит служебной склейки;
- preparation очищен whitelist-механизмом;
- неизвестный slug не сохраняется;
- не более четырёх labels;
- raw payload доступен только уполномоченным;
- User-Agent получен из HTTP-заголовка.

## 6. Идемпотентность

Повторить POST с тем же `request_id`.

Ожидается HTTP `200`, `duplicate: true`, тот же `lead_id` и одна строка в базе.

При включённом тестовом Telegram второе сообщение при обычном повторе не приходит. Подробная атомарная проверка выполняется по `docs/supabase-notification-smoke.md`.

## 7. Ошибки валидации

Проверить отдельно:

- отсутствует имя;
- неправильный телефон;
- отсутствует город;
- отсутствует сценарий;
- `consent: false`;
- неправильный `schema_version`;
- неправильный `request_id`;
- слишком короткое `form_fill_ms`.

Ожидается HTTP `422` с безопасными кодами. Объект preparation необязателен.

## 8. Spam-блок

Honeypot или `likely_bot: true` должны вернуть HTTP `202`, `success: false`, `request_rejected` без записи заявки.

Такой ответ не считается успешным каналом в hybrid.

## 9. Content-Type, JSON и размер

- нет JSON Content-Type — HTTP `415`;
- некорректный JSON — HTTP `400`;
- тело больше `MAX_BODY_BYTES` — HTTP `413` и `payload_too_large`.

## 10. Rate limit

В тестовой среде временно установить небольшой лимит. Последний запрос должен получить HTTP `429` и `rate_limit_exceeded`.

Таблица лимитов не хранит исходный IP, полный телефон или payload.

Проверить очистку через `purge_broker_lead_rate_limits`.

## 11. Проверка прав

Убедиться, что `anon` и `authenticated` не имеют прямых прав записи и EXECUTE на служебные RPC.

`service_role` используется только внутри Edge Function.

## 12. Telegram и сводка

Выполнить отдельный чеклист `docs/supabase-notification-smoke.md`.

Проверяются:

- `broker_lead_notification_summary`;
- первый и повторный claim;
- статусы `sending`, `sent`, `failed`;
- зависшее sending;
- duplicate request ID;
- остаточное аварийное окно Telegram.

Неизвестный UUID должен вернуть `broker_lead_not_found` только доверенному серверному вызову, без stack trace клиенту.

## 13. Fail-closed

Без применённых миграций тестовая функция должна вернуть безопасный `backend_migration_required`, а не принять неполную заявку.

## 14. Проверка hybrid

Переходить к этому этапу только после серверных тестов.

1. Обновить политику под фактическое хранение в Supabase.
2. Указать проверенный HTTPS endpoint.
3. Перевести режим в `hybrid`.
4. Дождаться успешной Pages-сборки.
5. Отправить заявку с UTM.
6. Подтвердить Web3Forms email.
7. Подтвердить строку Supabase.
8. Подтвердить Telegram или рабочую очередь.
9. Сверить один request ID во всех каналах.
10. Проверить `/spasibo/` и отказ одного канала.

## 15. Откат

При нестабильности:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

Миграции и данные не удаляются оперативно. Сначала отключается endpoint, затем анализируются события и логи.

## Результат приёмки

Зафиксировать в issue №7:

- Supabase project ref;
- даты пяти миграций;
- версию Edge Function;
- разрешённые Origin;
- тестовые request ID и lead ID;
- CORS, duplicate, spam и rate limit;
- preparation whitelist;
- атомарный claim и notification status;
- подтверждённый Telegram-чат;
- срок хранения;
- результат hybrid;
- ответственного и план отката.