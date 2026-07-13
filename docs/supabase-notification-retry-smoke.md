# Smoke-тест ручного повтора уведомлений

## Назначение

Проверить шестую миграцию, агрегированный контроль очереди и закрытую Edge Function `broker-notification-retry` до рабочего использования.

Тест проводится только в подтверждённом Supabase-проекте и тестовом Telegram-чате.

Публичный сайт во время теста сохраняет:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

## Подготовка

Применить миграции строго по порядку:

1. `202607070001_create_broker_leads.sql`;
2. `202607130002_broker_leads_v2.sql`;
3. `202607130003_broker_lead_preparation.sql`;
4. `202607130004_broker_lead_notification_summary.sql`;
5. `202607130005_broker_lead_notification_delivery.sql`;
6. `202607130006_broker_lead_notification_manual_retry.sql`.

Проверить `supabase/config.toml`:

```toml
[functions.broker-notification-retry]
verify_jwt = false
```

`verify_jwt = false` нужен, чтобы собственный `Authorization: Bearer NOTIFICATION_ADMIN_TOKEN` дошёл до handler. После отключения platform JWT обязательны внутренняя проверка token и отсутствие CORS.

Для закрытой функции задать secrets:

- `SUPABASE_URL`;
- `SUPABASE_SERVICE_ROLE_KEY`;
- `NOTIFICATION_ADMIN_TOKEN`;
- `TELEGRAM_BOT_TOKEN`;
- `TELEGRAM_CHAT_ID`;
- при необходимости `TELEGRAM_TIMEOUT_MS`.

Не публиковать значения в терминале общего доступа, issue, логах, документах или URL.

Локально задать:

```bash
export RETRY_FUNCTION_URL="https://PROJECT.supabase.co/functions/v1/broker-notification-retry"
export NOTIFICATION_ADMIN_TOKEN="LOCAL_SECRET"
export LEAD_ID="00000000-0000-4000-8000-000000000001"
export REQUEST_ID="00000000-0000-4000-8000-000000000002"
```

## Проверка прав RPC

Проверить функции:

```sql
select routine_name, security_type
from information_schema.routines
where routine_schema = 'public'
  and routine_name in (
    'request_broker_lead_notification_retry',
    'broker_lead_notification_queue_health'
  )
order by routine_name;
```

Проверить privileges:

```sql
select routine_name, grantee, privilege_type
from information_schema.routine_privileges
where specific_schema = 'public'
  and routine_name in (
    'request_broker_lead_notification_retry',
    'broker_lead_notification_queue_health'
  )
order by routine_name, grantee;
```

Ожидается:

- `SECURITY DEFINER`;
- `EXECUTE` только для `service_role`;
- отсутствие прав у `public`, `anon`, `authenticated`.

## Контроль очереди без персональных данных

Вызвать доверенной серверной ролью:

```sql
select *
from public.broker_lead_notification_queue_health();
```

Результат может содержать только:

- `notification_status`;
- `lead_count`;
- `oldest_lead_at`;
- `oldest_attempted_at`;
- `stale_count`;
- `max_attempt_count`;
- `total_manual_retries`.

Не должны возвращаться:

- `lead_id` и `request_id`;
- имя, телефон и город;
- страница-источник;
- текст заявки;
- `raw_payload`;
- Telegram chat ID или token.

## Подготовка failed-заявки

Создать тестовую заявку через основной backend smoke и искусственно получить ошибку Telegram либо в тестовой среде установить:

```sql
update public.broker_leads
set
  notification_status = 'failed',
  notification_last_error = 'telegram_temporary_error'
where id = 'LEAD_ID'
  and request_id = 'REQUEST_ID';
```

Использовать только тестовую заявку с явной пометкой `SMOKE TEST`.

## Проверка SQL retry

Вызвать:

```sql
select *
from public.request_broker_lead_notification_retry(
  'LEAD_ID',
  'REQUEST_ID',
  'telegram_temporary_error'
);
```

Ожидается:

- `retry_requested = true`;
- `current_status = pending`;
- `retry_count = 1`;
- `reason_code = telegram_temporary_error`;
- увеличен `notification_manual_retry_count`;
- установлены время и reason code;
- создано событие `notification_retry_requested`.

Проверить событие:

```sql
select event_type, event_title, event_comment, payload
from public.broker_lead_events
where lead_id = 'LEAD_ID'
  and event_type = 'notification_retry_requested'
order by created_at desc
limit 1;
```

Payload не должен содержать персональные данные.

Вернуть тестовую заявку в `failed` перед проверкой Edge Function.

## Запрещённые новые переходы

Проверить SQL retry для статусов:

- `sent`;
- `disabled`;
- `pending`;
- `sending`.

Ожидается `retry_requested = false`, исходный статус не меняется, новое событие не создаётся.

Это проверяет именно запрет нового перехода. Закрытая Edge Function может продолжить ранее подтверждённый `pending` или зависший `sending` по отдельным правилам ниже.

Проверить неизвестный reason code. Ожидается ошибка `invalid_notification_retry_reason` без изменения записи.

## HTTP-защита

Без токена:

```bash
curl -i -X POST "$RETRY_FUNCTION_URL" \
  -H "Content-Type: application/json" \
  --data '{"lead_id":"'$LEAD_ID'","request_id":"'$REQUEST_ID'","reason_code":"manual_recovery"}'
```

Ожидается HTTP `401` и `unauthorized`.

С неверным токеном ожидается тот же результат.

`GET` ожидает HTTP `405`.

Без `Content-Type: application/json` ожидается HTTP `415`.

Некорректный JSON ожидает HTTP `400`.

Тело больше 8192 байт ожидает HTTP `413`.

Ответы не должны содержать CORS-заголовок `Access-Control-Allow-Origin`.

## Успешный ручной retry

Убедиться, что заявка имеет `failed`, а Telegram secrets указывают на тестовый чат.

```bash
curl -i -X POST "$RETRY_FUNCTION_URL" \
  -H "Authorization: Bearer $NOTIFICATION_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"lead_id":"'$LEAD_ID'","request_id":"'$REQUEST_ID'","reason_code":"telegram_temporary_error"}'
```

Ожидается:

- HTTP `200`;
- `success: true`;
- `notification_status: sent`;
- `resumed: false`;
- увеличены retry count и attempt count;
- одно новое Telegram-сообщение;
- созданы события `notification_retry_requested` и `notification_retry_sent`;
- ответ не содержит персональные данные.

Проверить таблицу:

```sql
select
  notification_status,
  notification_attempt_count,
  notification_manual_retry_count,
  notification_manual_retry_requested_at,
  notification_manual_retry_reason_code,
  notification_sent_at,
  notification_last_error
from public.broker_leads
where id = 'LEAD_ID';
```

## Восстановление pending

Проверить аварийный сценарий, когда SQL retry уже выполнен, запись имеет `pending`, но Edge Function ещё не получила claim.

1. Подготовить `failed`-заявку.
2. Вызвать `request_broker_lead_notification_retry` с reason code.
3. Не вызывать claim вручную.
4. Вызвать закрытую Edge Function с тем же request ID и тем же reason code.

Ожидается:

- новый SQL-переход не выполняется;
- `notification_manual_retry_count` не увеличивается второй раз;
- второе событие `notification_retry_requested` не создаётся;
- функция получает claim и завершает отправку;
- ответ содержит `resumed: true`.

## Восстановление зависшего sending

Проверить запись с:

- `notification_status = sending`;
- `notification_manual_retry_count > 0`;
- допустимым сохранённым reason code;
- `notification_attempted_at` старше 15 минут.

Вызвать закрытую функцию с тем же reason code.

Ожидается:

- атомарный claim разрешает восстановление зависшего `sending`;
- ручной retry count не увеличивается;
- отправка завершается;
- ответ содержит `resumed: true`.

Для активного `sending` моложе 15 минут ожидается HTTP `409` и `notification_not_claimed`.

## Несовпадение причины

Для ранее подтверждённого `pending` или `sending` передать другой reason code.

Ожидается HTTP `409`, `retry_reason_mismatch`, состояние и счётчики не меняются, Telegram-сообщение не отправляется.

## Ошибка повторной доставки

В тестовой среде временно использовать неверный Telegram chat ID и повторить процедуру с другой failed-заявкой.

Ожидается:

- HTTP `502`;
- заявка остаётся сохранённой;
- `notification_status = failed`;
- безопасный `notification_last_error`;
- событие `notification_retry_failed`;
- автоматического нового retry не происходит.

После теста вернуть корректные secrets.

## Повтор после sent

Повторить HTTP-запрос для уже отправленной заявки.

Ожидается HTTP `409`, `retry_not_allowed`, статус `sent`, второе Telegram-сообщение не создаётся.

## Проверка журналирования

Для тестовой заявки допустимы события:

- `notification_retry_requested`;
- `notification_retry_sent`;
- `notification_retry_failed`.

В event payload разрешены только:

- `reason_code`;
- `retry_count`;
- `attempt_count`;
- `error_code`;
- логический признак `resumed`.

Проверить отсутствие полного payload, имени, телефона, города, URL и текста уведомления.

## Откат

При проблеме:

1. удалить или отключить secret `NOTIFICATION_ADMIN_TOKEN`;
2. не публиковать URL административной функции;
3. оставить публичный сайт в режиме `web3forms` с пустым `endpoint`;
4. не удалять заявки и историю событий;
5. анализировать только безопасные коды ошибок и агрегированное состояние очереди.

## Результат

Зафиксировать в issue №7:

- дату применения шестой миграции;
- дату deploy закрытой функции;
- подтверждение `verify_jwt = false` и собственной проверки admin token;
- подтверждение отсутствия CORS;
- использованный reason code;
- итоговые статусы и счётчики без идентификаторов клиента;
- наличие одного Telegram-сообщения;
- результат восстановления `pending`;
- результат восстановления зависшего `sending`;
- результат `retry_reason_mismatch`;
- результат повторного вызова после `sent`;
- результат ошибки доставки;
- ответственного за ручной retry и процедуру отката.