# Контракт контроля очереди уведомлений

## Назначение

Закрытая Edge Function `broker-notification-health` предоставляет техническое состояние очереди Telegram-уведомлений без раскрытия персональных данных заявителей.

Она не является частью публичного сайта, не вызывается браузером посетителя и не включает Supabase как канал приёма заявок.

Публичная конфигурация до отдельной приёмки сохраняется:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

## Источник данных

Функция вызывает только RPC:

`public.broker_lead_notification_queue_health()`

RPC возвращает агрегаты по статусам и доступна только `service_role`.

В ответ нельзя включать:

- `lead_id` и `request_id`;
- имя, телефон, город;
- источник и URL страницы;
- текст заявки или комментарий;
- `raw_payload`;
- Telegram chat ID и token;
- admin или monitor token.

## Авторизация

Функция требует отдельный secret:

`NOTIFICATION_MONITOR_TOKEN`

Запрос:

```text
GET /functions/v1/broker-notification-health
Authorization: Bearer <monitor token>
```

Monitor token:

- не совпадает с `NOTIFICATION_ADMIN_TOKEN`;
- не передаётся в query string;
- не публикуется в репозитории, issue или клиентском JavaScript;
- сравнивается внутри handler через SHA-256;
- хранится только в secrets Edge Function и доверенной системе мониторинга.

В `supabase/config.toml` для функции используется `verify_jwt = false`, чтобы собственный bearer token дошёл до handler. После этого handler самостоятельно обязан отклонить запрос без правильного monitor token.

## Сетевая модель

Функция:

- принимает только `GET`;
- не устанавливает `Access-Control-Allow-Origin`;
- возвращает `Cache-Control: no-store`;
- не допускает browser CORS-вызов;
- при неверном токене отвечает `401 unauthorized`;
- при отсутствии конфигурации отвечает `503 server_not_configured`;
- при ошибке RPC отвечает `503 queue_health_unavailable`.

## Формат ответа

Успешный ответ:

```json
{
  "ok": true,
  "status": "ok",
  "checked_at": "2026-07-13T20:00:00.000Z",
  "alerts": [],
  "queue": [
    {
      "notification_status": "sent",
      "lead_count": 12,
      "oldest_lead_at": "2026-07-13T10:00:00.000Z",
      "oldest_attempted_at": "2026-07-13T10:00:02.000Z",
      "stale_count": 0,
      "max_attempt_count": 1,
      "total_manual_retries": 0
    }
  ],
  "thresholds": {
    "failed_warning": 1,
    "failed_critical": 5,
    "pending_warning": 10,
    "attempts_warning": 3,
    "stale_sending_minutes": 15
  }
}
```

Допустимые итоговые состояния:

- `ok` — активных тревог нет;
- `warning` — требуется проверка оператора;
- `critical` — есть зависшее уведомление или критическое число ошибок.

HTTP-коды:

- `200` — `ok` или `warning`;
- `503` — `critical` либо health RPC недоступна;
- `401` — неверный monitor token;
- `405` — неподдерживаемый метод.

## Коды тревог

Разрешены только технические коды:

- `stale_sending` — есть `sending` старше 15 минут;
- `failed_present` — есть хотя бы одно `failed`;
- `failed_critical` — превышен критический порог `failed`;
- `pending_backlog` — превышен порог `pending`;
- `attempts_elevated` — повышено максимальное число попыток.

Коды не должны содержать идентификатор или сведения заявки.

## Пороги

Пороги задаются secrets/env функции:

- `NOTIFICATION_FAILED_WARNING_THRESHOLD`, по умолчанию `1`;
- `NOTIFICATION_FAILED_CRITICAL_THRESHOLD`, по умолчанию `5`;
- `NOTIFICATION_PENDING_WARNING_THRESHOLD`, по умолчанию `10`;
- `NOTIFICATION_ATTEMPT_WARNING_THRESHOLD`, по умолчанию `3`.

Изменение порогов выполняется после анализа фактического потока заявок и фиксируется в issue №7 без публикации секретов.

## Реакция оператора

При `warning`:

1. проверить агрегаты очереди;
2. сверить технические события в доверенной среде;
3. не выполнять retry без проверки request ID в Telegram и базе;
4. использовать закрытую `broker-notification-retry` только для подтверждённого `failed`.

При `critical`:

1. не включать или временно отключить публичный Supabase endpoint;
2. оставить Web3Forms рабочим;
3. проверить зависшие `sending` и ошибки Telegram;
4. устранить причину;
5. провести ручной retry только по утверждённому runbook;
6. повторить health-запрос и smoke-тест.

## Активационный барьер

Health-функция может быть развёрнута только после:

1. применения всех шести миграций;
2. проверки `broker_lead_notification_queue_health()`;
3. создания отдельного monitor token;
4. подтверждения отсутствия CORS;
5. проверки ответа без персональных данных;
6. настройки ответственного и канала тревог;
7. выполнения `docs/supabase-notification-health-smoke.md`.

Развёртывание health-функции само по себе не разрешает включать `hybrid`.