# Smoke-тест контроля очереди уведомлений

## Назначение

Проверить закрытую Edge Function `broker-notification-health`, агрегированный RPC и пороги тревог до подключения внешнего мониторинга.

Публичный сайт во время теста сохраняет:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

## Подготовка

Применить шесть миграций backend по порядку и выполнить smoke основного backend, Telegram-доставки и ручного retry.

Задать secrets функции:

- `SUPABASE_URL`;
- `SUPABASE_SERVICE_ROLE_KEY`;
- отдельный `NOTIFICATION_MONITOR_TOKEN`;
- при необходимости пороги `NOTIFICATION_*_THRESHOLD`.

Monitor token не должен совпадать с `NOTIFICATION_ADMIN_TOKEN`.

Локально задать:

```bash
export HEALTH_FUNCTION_URL="https://PROJECT.supabase.co/functions/v1/broker-notification-health"
export NOTIFICATION_MONITOR_TOKEN="LOCAL_MONITOR_SECRET"
```

## Проверка конфигурации

В `supabase/config.toml` должна быть секция:

```toml
[functions.broker-notification-health]
verify_jwt = false
```

Это разрешает собственному bearer token дойти до handler. Авторизацию затем выполняет сама функция.

## Проверка агрегированного RPC

В доверенном SQL Editor вызвать:

```sql
select *
from public.broker_lead_notification_queue_health();
```

Допустимые колонки:

- `notification_status`;
- `lead_count`;
- `oldest_lead_at`;
- `oldest_attempted_at`;
- `stale_count`;
- `max_attempt_count`;
- `total_manual_retries`.

Не должны возвращаться идентификаторы, имена, телефоны, города, URL, комментарии или `raw_payload`.

## Авторизация

Без токена:

```bash
curl -i "$HEALTH_FUNCTION_URL"
```

Ожидается HTTP `401`, `unauthorized`.

С неверным токеном ожидается тот же результат.

С правильным токеном:

```bash
curl -i "$HEALTH_FUNCTION_URL" \
  -H "Authorization: Bearer $NOTIFICATION_MONITOR_TOKEN"
```

Ожидается HTTP `200` для состояния `ok` или `warning`, либо HTTP `503` для `critical`.

## HTTP-защита

Проверить:

- `POST` возвращает HTTP `405`;
- ответ содержит `Cache-Control: no-store`;
- ответ не содержит `Access-Control-Allow-Origin`;
- URL запроса не содержит token;
- тело ошибки не содержит stack trace, ключи или сведения заявки.

## Нормальное состояние

При отсутствии `failed`, зависших `sending`, большого `pending` и повышенных попыток ожидается:

```json
{
  "ok": true,
  "status": "ok",
  "alerts": []
}
```

Проверить, что `queue` содержит только агрегаты, а `thresholds` соответствует окружению функции.

## Warning: failed_present

На тестовой заявке установить `notification_status = 'failed'`, не достигая критического порога.

Ожидается:

- HTTP `200`;
- `status = warning`;
- `alerts` содержит `failed_present`;
- персональные данные отсутствуют.

После теста вернуть запись в согласованное состояние.

## Critical: stale_sending

На тестовой заявке установить:

```sql
update public.broker_leads
set
  notification_status = 'sending',
  notification_attempted_at = now() - interval '20 minutes'
where id = 'TEST_LEAD_ID';
```

Ожидается:

- HTTP `503`;
- `status = critical`;
- `alerts` содержит `stale_sending`;
- `stale_count` больше нуля.

После теста восстановить тестовую запись штатным способом.

## Critical: failed_critical

В тестовой среде создать количество `failed`, равное критическому порогу.

Ожидается:

- HTTP `503`;
- `status = critical`;
- `alerts` содержит `failed_critical`.

Не использовать реальные заявки для искусственного увеличения счётчика.

## Warning: pending_backlog

В тестовой среде временно установить небольшой `NOTIFICATION_PENDING_WARNING_THRESHOLD` и создать соответствующее число тестовых `pending`.

Ожидается HTTP `200`, `status = warning`, код `pending_backlog`.

## Warning: attempts_elevated

Для тестовой заявки увеличить `notification_attempt_count` до порога.

Ожидается HTTP `200`, `status = warning`, код `attempts_elevated`.

## Ошибка RPC

В отдельной тестовой среде проверить поведение без шестой миграции либо с временно недоступным RPC.

Ожидается HTTP `503`, `queue_health_unavailable`, без технических деталей базы.

## Проверка отсутствия персональных данных

В JSON-ответе не должно быть ключей и значений:

- `lead_id`, `request_id`;
- `client_name`, `phone`, `city`;
- `source_page`, `page_url`;
- `comment`, `raw_payload`;
- `telegram_chat_id`, `telegram_bot_token`;
- `notification_admin_token`, `notification_monitor_token`.

## Runbook реакции

Для каждого кода проверить операционное действие:

- `failed_present` — анализ причины, решение о ручном retry;
- `failed_critical` — остановка включения hybrid и разбор очереди;
- `stale_sending` — проверка зависшей попытки и аварийного окна;
- `pending_backlog` — проверка Telegram-конфигурации и работоспособности handler;
- `attempts_elevated` — проверка повторов, таймаутов и дубликатов.

## Откат

При проблеме:

1. удалить или отключить `NOTIFICATION_MONITOR_TOKEN`;
2. не публиковать URL функции;
3. оставить сайт в `web3forms` с пустым `endpoint`;
4. не изменять заявки массово;
5. анализировать очередь через доверенный SQL Editor;
6. исправить причину и повторить smoke.

## Результат

Зафиксировать в issue №7:

- дату deploy функции;
- подтверждение отдельного monitor token;
- отсутствие CORS;
- результаты `ok`, `warning`, `critical`;
- отсутствие персональных данных;
- фактические пороги;
- ответственного и канал доставки тревог;
- процедуру отката.