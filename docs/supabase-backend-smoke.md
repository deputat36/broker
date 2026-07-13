# Smoke-тест Supabase backend v2

## Назначение

Чек-лист подтверждает, что подготовленные исходники действительно применены в нужном Supabase-проекте и могут безопасно работать вторым каналом рядом с Web3Forms.

До завершения всех проверок сайт должен сохранять:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

Тесты выполняются сначала в отдельной тестовой среде или с явно тестовыми данными.

## Переменные для теста

Заменить значения локально, не коммитить их в репозиторий:

```bash
export FUNCTION_URL="https://PROJECT.supabase.co/functions/v1/broker-public-lead"
export SITE_ORIGIN="https://sterlikova-ipoteka.ru"
export REQUEST_ID="00000000-0000-4000-8000-000000000001"
```

Не размещать в командах браузера или публичных файлах:

- `SUPABASE_SERVICE_ROLE_KEY`;
- Telegram bot token;
- закрытые CRM-ключи.

## 1. Проверка миграций

В подтверждённом Supabase-проекте должны быть применены:

1. `202607070001_create_broker_leads.sql`;
2. `202607130002_broker_leads_v2.sql`.

Проверить наличие основных объектов:

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
    'notification_status'
  )
order by column_name;
```

Проверить уникальный индекс:

```sql
select indexname, indexdef
from pg_indexes
where schemaname = 'public'
  and indexname = 'broker_leads_request_id_uidx';
```

Проверить RPC:

```sql
select routine_name
from information_schema.routines
where routine_schema = 'public'
  and routine_name in (
    'consume_broker_lead_rate_limit',
    'purge_broker_lead_rate_limits'
  );
```

Ожидается:

- обе таблицы созданы;
- новые столбцы присутствуют;
- индекс частичный и уникальный;
- обе функции существуют;
- RLS включён;
- публичная anon-вставка в таблицы не создана.

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

Ожидается:

- HTTP `204`;
- `Access-Control-Allow-Origin` равен `$SITE_ORIGIN`;
- разрешены `POST, OPTIONS`;
- присутствует `Vary: Origin`.

Запрещённый Origin:

```bash
curl -i -X OPTIONS "$FUNCTION_URL" \
  -H "Origin: https://attacker.example" \
  -H "Access-Control-Request-Method: POST"
```

Ожидается HTTP `403` и отсутствие разрешающего CORS-заголовка для постороннего домена.

## 4. Валидный тестовый payload

Создать файл `/tmp/broker-lead.json`:

```json
{
  "schema_version": 1,
  "request_id": "00000000-0000-4000-8000-000000000001",
  "form_version": "2",
  "submitted_at": "2026-07-13T15:00:00.000Z",
  "form_fill_ms": 10000,
  "source_page": "/uslugi/podbor-ipoteki/",
  "page_url": "https://sterlikova-ipoteka.ru/online-zayavka/?source=%2Fuslugi%2Fpodbor-ipoteki%2F",
  "page_title": "Онлайн-заявка ипотечному брокеру",
  "referrer": "https://sterlikova-ipoteka.ru/uslugi/podbor-ipoteki/",
  "tracking": {
    "first_touch": {},
    "last_touch": {},
    "current": {
      "utm_source": "supabase_smoke",
      "utm_medium": "test",
      "utm_campaign": "backend_v2"
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
    "scenario": "Первичная консультация и подбор ипотеки",
    "object_type": "Пока не выбрано",
    "object_price": "Тест",
    "down_payment": "Тест",
    "income_type": "Не указано",
    "bank_history": "SMOKE TEST — не обрабатывать как реального клиента",
    "comment": "Проверка Supabase backend v2"
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

Ожидается HTTP `201`:

```json
{
  "ok": true,
  "success": true,
  "duplicate": false,
  "lead_id": "UUID",
  "request_id": "00000000-0000-4000-8000-000000000001",
  "crm_status": "new"
}
```

Зафиксировать `lead_id`.

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
  technical_priority,
  notification_status,
  created_at
from public.broker_leads
where request_id = '00000000-0000-4000-8000-000000000001';
```

Проверить:

- одна строка;
- нормализованный телефон начинается с `7` и содержит 11 цифр;
- исходные текстовые значения не потеряны;
- tracking и qualification записаны;
- `raw_payload` соответствует тесту;
- User-Agent взят из HTTP-заголовка, а не из клиентского JSON.

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

Ожидается HTTP `200`:

```json
{
  "ok": true,
  "success": true,
  "duplicate": true,
  "lead_id": "ТОТ ЖЕ UUID"
}
```

Проверить в базе:

```sql
select count(*)
from public.broker_leads
where request_id = '00000000-0000-4000-8000-000000000001';
```

Результат должен быть `1`.

## 7. Ошибки валидации

Проверить по отдельности:

- отсутствует имя;
- телефон короче 11 цифр;
- отсутствует город;
- отсутствует сценарий;
- `consent: false`;
- неправильный `schema_version`;
- неправильный `request_id`;
- `form_fill_ms` меньше `MIN_FILL_MS`.

Ожидается HTTP `422`, `ok: false`, `success: false` и массив безопасных кодов ошибок.

## 8. Spam-блок

Изменить:

```json
"spam_check": {
  "honeypot_empty": false,
  "likely_bot": true
}
```

Использовать новый `request_id`.

Ожидается HTTP `202`:

```json
{
  "ok": false,
  "success": false,
  "blocked": true,
  "error": "request_rejected"
}
```

Запись в `broker_leads` создаваться не должна. Такой ответ не должен считаться успешным каналом в режиме `hybrid`.

## 9. Content-Type, JSON и размер

Без `Content-Type: application/json` ожидается HTTP `415`.

Некорректный JSON ожидает HTTP `400` и `invalid_json`.

Тело больше `MAX_BODY_BYTES` ожидает HTTP `413` и `payload_too_large`.

## 10. Rate limit

Проверять только в тестовой среде с временно уменьшенным лимитом, например:

```text
RATE_LIMIT_PER_HOUR=3
```

Отправить четыре заявки с новыми `request_id`, одним телефоном, IP и User-Agent.

Ожидается:

- первые три запроса проходят серверный лимит;
- четвёртый получает HTTP `429`;
- ответ содержит `rate_limit_exceeded`;
- в таблице ограничений нет исходного IP, телефона и полного payload;
- счётчик увеличивается атомарно.

Проверка:

```sql
select fingerprint, window_start, attempt_count, last_request_id
from public.broker_lead_rate_limits
order by last_attempt_at desc
limit 10;
```

## 11. Очистка rate limit

В тестовой среде:

```sql
select public.purge_broker_lead_rate_limits(now() + interval '1 minute');
```

Проверить, что функция возвращает количество удалённых строк.

В production нужно настроить регулярный запуск с безопасным сроком, например удаление технических окон старше семи дней.

## 12. Telegram

### Без Telegram secrets

Ожидается:

- заявка сохранена;
- `notification_status = disabled`;
- ошибка не возвращается клиенту.

### С тестовым Telegram-чатом

Ожидается:

- сообщение приходит в правильный чат;
- присутствуют request ID, телефон, город, задача, приоритет и источник;
- `notification_status = sent`;
- создано событие `notification_sent`.

### Искусственная ошибка Telegram

В тестовой среде временно использовать неверный chat ID или тестовый недоступный канал.

Ожидается:

- заявка остаётся в базе;
- `notification_status = failed`;
- создано событие `notification_failed`;
- клиент получает успешный ответ о сохранении заявки.

После проверки вернуть правильные secrets.

## 13. Fail-closed проверка

На отдельной тестовой функции без применённой v2-миграции ожидается HTTP `503`:

```json
{
  "ok": false,
  "success": false,
  "error": "backend_migration_required"
}
```

Функция не должна молча принимать заявку без уникального `request_id` и атомарного rate limit.

## 14. Проверка hybrid на сайте

Переходить к этому этапу только после прохождения серверных тестов.

1. Обновить политику обработки данных под фактическое хранение в Supabase.
2. Указать проверенный HTTPS endpoint в `_config.yml`.
3. Перевести `lead_capture.mode` в `hybrid`.
4. Дождаться успешной Pages-сборки.
5. Отправить заявку через опубликованный сайт с UTM-метками.
6. Подтвердить email Web3Forms.
7. Подтвердить строку Supabase.
8. Подтвердить Telegram или рабочую очередь.
9. Проверить один request ID во всех каналах.
10. Проверить `/spasibo/` и fallback при отказе одного канала.

## 15. Откат

Если Supabase работает нестабильно:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

Web3Forms и резервные способы должны продолжить работу независимо.

Не удалять таблицы и миграции при оперативном откате. Сначала отключается только клиентский endpoint, затем анализируются события и логи без публикации персональных данных.

## Результат приёмки

Зафиксировать в issue №7:

- Supabase project ref;
- дату применения миграций;
- версию функции;
- разрешённые Origin;
- тестовый request ID и lead ID;
- результаты duplicate, CORS, spam и rate limit;
- Telegram-чат или очередь;
- ответственного за обработку;
- срок хранения;
- результат hybrid-теста;
- план отката.
