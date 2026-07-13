# Smoke-тест Supabase backend v2

## Назначение

Чек-лист подтверждает, что подготовленные исходники применены в правильном Supabase-проекте и могут безопасно работать вторым каналом рядом с Web3Forms.

До завершения всех проверок сайт должен сохранять:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

Тесты выполняются сначала в отдельной тестовой среде или с явно тестовыми данными.

## Переменные для теста

Заменить значения локально и не коммитить секреты:

```bash
export FUNCTION_URL="https://PROJECT.supabase.co/functions/v1/broker-public-lead"
export SITE_ORIGIN="https://sterlikova-ipoteka.ru"
export REQUEST_ID="00000000-0000-4000-8000-000000000001"
```

Не публиковать:

- `SUPABASE_SERVICE_ROLE_KEY`;
- Telegram bot token;
- Telegram chat ID без согласования;
- CRM-ключи.

## 1. Проверка миграций

В подтверждённом Supabase-проекте должны быть применены по порядку:

1. `202607070001_create_broker_leads.sql`;
2. `202607130002_broker_leads_v2.sql`;
3. `202607130003_broker_lead_preparation.sql`.

Проверить основные объекты:

```sql
select to_regclass('public.broker_leads');
select to_regclass('public.broker_lead_events');
select to_regclass('public.broker_lead_rate_limits');

select column_name, data_type
from information_schema.columns
where table_schema = 'public'
  and table_name = 'broker_leads'
  and column_name in (
    'request_id',
    'schema_version',
    'form_version',
    'phone_normalized',
    'tracking',
    'qualification',
    'spam_check',
    'raw_payload',
    'notification_status',
    'journey_type',
    'journey_stage',
    'journey_scenario_slug',
    'preparation',
    'preparation_completed',
    'remaining_questions'
  )
order by column_name;
```

Проверить индексы:

```sql
select indexname, indexdef
from pg_indexes
where schemaname = 'public'
  and indexname in (
    'broker_leads_request_id_uidx',
    'broker_leads_preparation_gin_idx',
    'broker_leads_journey_scenario_idx'
  )
order by indexname;
```

Проверить функции и trigger:

```sql
select routine_name
from information_schema.routines
where routine_schema = 'public'
  and routine_name in (
    'consume_broker_lead_rate_limit',
    'purge_broker_lead_rate_limits',
    'sync_broker_lead_preparation'
  );

select trigger_name, event_manipulation
from information_schema.triggers
where event_object_schema = 'public'
  and event_object_table = 'broker_leads'
  and trigger_name = 'broker_leads_sync_preparation';
```

Ожидается:

- таблицы и новые столбцы присутствуют;
- request ID имеет частичный уникальный индекс;
- preparation имеет GIN-индекс;
- trigger включён на `insert` и `update` поля `raw_payload`;
- RLS включён;
- публичная anon-вставка в таблицы отсутствует.

## 2. Проверка конфигурации Edge Function

Обязательные secrets:

- `SUPABASE_URL`;
- `SUPABASE_SERVICE_ROLE_KEY`.

Рекомендуемые настройки:

```text
ALLOWED_ORIGINS=https://sterlikova-ipoteka.ru,https://www.sterlikova-ipoteka.ru
ALLOW_ORIGINLESS=false
RATE_LIMIT_PER_HOUR=8
MIN_FILL_MS=1500
MAX_BODY_BYTES=65536
TELEGRAM_TIMEOUT_MS=5000
```

Telegram подключается только для тестового или подтверждённого рабочего чата:

- `TELEGRAM_BOT_TOKEN`;
- `TELEGRAM_CHAT_ID`.

## 3. CORS preflight

Разрешённый Origin:

```bash
curl -i -X OPTIONS "$FUNCTION_URL" \
  -H "Origin: $SITE_ORIGIN" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type"
```

Ожидается HTTP `204`, точный `Access-Control-Allow-Origin`, `POST, OPTIONS` и `Vary: Origin`.

Запрещённый Origin:

```bash
curl -i -X OPTIONS "$FUNCTION_URL" \
  -H "Origin: https://attacker.example" \
  -H "Access-Control-Request-Method: POST"
```

Ожидается HTTP `403` без разрешающего CORS-заголовка.

## 4. Валидный payload с preparation

Создать `/tmp/broker-lead.json`:

```json
{
  "schema_version": 1,
  "request_id": "00000000-0000-4000-8000-000000000001",
  "form_version": "2",
  "submitted_at": "2026-07-13T15:00:00.000Z",
  "form_fill_ms": 10000,
  "source_page": "/geo/borisoglebsk/otkazali-v-ipoteke/",
  "page_url": "https://sterlikova-ipoteka.ru/online-zayavka/?source=...&journey=complex&stage=route",
  "page_title": "Онлайн-заявка ипотечному брокеру",
  "referrer": "https://sterlikova-ipoteka.ru/geo/borisoglebsk/otkazali-v-ipoteke/",
  "tracking": {
    "first_touch": {},
    "last_touch": {},
    "current": {
      "utm_source": "supabase_smoke",
      "utm_medium": "test",
      "utm_campaign": "backend_v2_preparation"
    }
  },
  "client": {
    "name": "Тест Supabase",
    "phone": "+7 (900) 000-00-01",
    "phone_normalized": "79000000001",
    "city": "Борисоглебск",
    "preferred_contact": "Позвонить"
  },
  "mortgage": {
    "scenario": "Банк отказал в ипотеке",
    "object_type": "Пока не выбрано",
    "object_price": "Тест",
    "down_payment": "Тест",
    "income_type": "Не указано",
    "bank_history": "SMOKE TEST — не обрабатывать как реального клиента",
    "comment": "Исходный комментарий клиента без служебной склейки"
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
    "remaining_questions": "Нужно понять, связан ли отказ с объектом"
  },
  "qualification": {
    "status": "cold",
    "score": 25,
    "priority": "уточнить вводные",
    "reasons": ["тестовая заявка"]
  },
  "personal_data_consent": "yes",
  "consent": true,
  "spam_check": {
    "honeypot_empty": true,
    "form_fill_ms": 10000,
    "likely_bot": false
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

Ожидается HTTP `201`, `success: true`, новый `lead_id` и тот же `request_id`.

## 5. Проверка записи в базе

```sql
select
  id,
  request_id,
  status,
  client_name,
  phone_normalized,
  city,
  scenario,
  source_page,
  journey_type,
  journey_stage,
  journey_scenario_slug,
  preparation,
  preparation_completed,
  remaining_questions,
  comment,
  technical_priority,
  notification_status,
  created_at
from public.broker_leads
where request_id = '00000000-0000-4000-8000-000000000001';
```

Проверить:

- одна строка;
- телефон нормализован до 11 цифр и начинается с `7`;
- `raw_payload.preparation` соответствует тесту;
- `journey_type`, `journey_stage` и slug заполнены trigger-функцией;
- `preparation_completed` содержит только две подписи;
- `remaining_questions` хранится отдельно;
- `comment` не содержит строк подготовки;
- tracking и qualification записаны;
- User-Agent взят из HTTP-заголовка.

Проверить whitelist. Повторить запрос с неизвестным slug, лишним ключом проверки, пятью labels и огромным `context_version`.

Ожидается:

- неизвестный slug превращается в `null`;
- `active` становится `false`;
- неизвестный check не сохраняется;
- сохраняется максимум четыре labels;
- version не вызывает ошибку integer и ограничивается безопасным диапазоном;
- произвольные вложенные поля отсутствуют в очищенном `preparation`, но могут оставаться только в защищённом `raw_payload`.

События:

```sql
select event_type, event_title, event_comment, created_at
from public.broker_lead_events
where request_id = '00000000-0000-4000-8000-000000000001'
order by created_at;
```

Ожидается минимум событие `created`.

## 6. Идемпотентность

Повторить тот же POST с тем же `request_id`.

Ожидается HTTP `200`, `duplicate: true` и тот же `lead_id`.

```sql
select count(*)
from public.broker_leads
where request_id = '00000000-0000-4000-8000-000000000001';
```

Результат должен быть `1`.

## 7. Ошибки валидации

Проверить отдельно:

- отсутствует имя;
- неправильный телефон;
- отсутствует город;
- отсутствует сценарий;
- `consent: false`;
- неправильный `schema_version`;
- неправильный `request_id`;
- `form_fill_ms` меньше `MIN_FILL_MS`.

Ожидается HTTP `422` и безопасный массив кодов ошибок.

Объект `preparation` необязателен: обычная заявка без него должна успешно приниматься.

## 8. Spam-блок

Передать:

```json
"spam_check": {
  "honeypot_empty": false,
  "likely_bot": true
}
```

Ожидается HTTP `202`, `success: false`, `request_rejected`. Запись не создаётся, а ответ не считается успешным каналом в режиме hybrid.

## 9. Content-Type, JSON и размер

- без `Content-Type: application/json` — HTTP `415`;
- некорректный JSON — HTTP `400` и `invalid_json`;
- тело больше `MAX_BODY_BYTES` — HTTP `413` и `payload_too_large`.

## 10. Rate limit

В тестовой среде временно установить:

```text
RATE_LIMIT_PER_HOUR=3
```

Отправить четыре заявки с новыми `request_id`, одним телефоном, IP и User-Agent.

Ожидается:

- первые три проходят;
- четвёртая получает HTTP `429` и `rate_limit_exceeded`;
- счётчик увеличивается атомарно;
- таблица rate limit не хранит исходный IP, телефон и payload.

## 11. Очистка rate limit

```sql
select public.purge_broker_lead_rate_limits(now() + interval '1 minute');
```

Функция должна вернуть количество удалённых строк. В production требуется регулярный безопасный график очистки.

## 12. Telegram

Без Telegram secrets заявка сохраняется с `notification_status = disabled`.

С тестовым чатом сообщение должно содержать request ID, телефон, город, задачу, приоритет и источник. После будущего расширения уведомления желательно добавить journey stage, но отсутствие этого поля сейчас не блокирует сохранение структурированного контекста в CRM.

Искусственная ошибка Telegram не должна откатывать заявку. Ожидаются `notification_status = failed` и событие `notification_failed`.

## 13. Fail-closed проверка

На тестовой функции без применённой базовой или preparation-миграции ожидается HTTP `503` и `backend_migration_required` либо ошибка сохранения без ложного успешного ответа.

Функция не должна молча принимать заявку без уникального `request_id`, атомарного rate limit и требуемых колонок.

## 14. Проверка hybrid на сайте

Переходить к этому этапу только после серверных тестов.

1. Обновить политику обработки данных под фактическое хранение в Supabase.
2. Указать проверенный HTTPS endpoint в `_config.yml`.
3. Перевести `lead_capture.mode` в `hybrid`.
4. Дождаться успешной Pages-сборки.
5. Отправить обычную и сложную заявки с UTM-метками.
6. Подтвердить email Web3Forms.
7. Подтвердить строку Supabase и отдельные preparation-поля.
8. Подтвердить Telegram или рабочую очередь.
9. Проверить один request ID во всех каналах.
10. Проверить `/spasibo/` и fallback при отказе одного канала.

## 15. Откат

При нестабильной работе вернуть:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

Web3Forms и резервные способы должны продолжить работу независимо.

Не удалять таблицы и миграции при оперативном откате. Сначала отключается клиентский endpoint, затем анализируются события и логи без публикации персональных данных.

## Результат приёмки

Зафиксировать в issue №7:

- Supabase project ref;
- дату применения всех трёх миграций;
- версию функции;
- разрешённые Origin;
- тестовый request ID и lead ID;
- результаты duplicate, CORS, spam и rate limit;
- результат очистки и whitelist preparation;
- Telegram-чат или очередь;
- ответственного за обработку;
- срок хранения;
- результат проверки hybrid;
- план отката.