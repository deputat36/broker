# Smoke: безопасные ошибки публичной Edge Function

## Preconditions

- применены 11 миграций в каноническом порядке;
- `broker-public-lead` развёрнута только в тестовом окружении;
- рабочий сайт остаётся в режиме `web3forms`;
- production endpoint в `_config.yml` пуст;
- для тестов известен разрешённый Origin.

## Общий критерий envelope

Каждая проверяемая ошибка должна возвращать:

```json
{
  "ok": false,
  "success": false,
  "error_code": "<публичный код>",
  "request_id": "<UUID или исходный request_id>"
}
```

Допустимое дополнительное поле только одно: `retry_after_seconds` для HTTP `429`.

Во всех ответах проверить `Cache-Control: no-store`.

## 1. Invalid JSON

Отправить обрезанный JSON с корректным Origin и Content-Type.

Ожидание:

- HTTP `400`;
- `error_code = invalid_json`;
- `request_id` соответствует UUID;
- отсутствуют parser message и stack trace.

## 2. Неподдерживаемый Content-Type

Отправить POST с `text/plain`.

Ожидание:

- HTTP `415`;
- `error_code = content_type_not_supported`;
- новый correlation UUID.

## 3. Слишком большой payload

Проверить ограничение по `Content-Length` и по фактическому размеру прочитанного тела.

Ожидание для обоих случаев:

- HTTP `413`;
- `error_code = payload_too_large`;
- отсутствуют размер тела и серверный лимит.

## 4. Запрещённый Origin

Отправить POST и OPTIONS с Origin вне белого списка.

Ожидание:

- HTTP `403`;
- `error_code = origin_not_allowed`;
- отсутствует `Access-Control-Allow-Origin` для неизвестного домена.

## 5. Неправильный метод

Отправить GET с разрешённым Origin.

Ожидание:

- HTTP `405`;
- `error_code = method_not_allowed`;
- correlation UUID.

## 6. Серверная валидация

Отправить JSON-объект с валидным `request_id`, но без обязательных полей.

Ожидание:

- HTTP `422`;
- `error_code = validation_failed`;
- ответ содержит исходный валидный `request_id`;
- отсутствует массив `errors` и названия отдельных полей.

## 7. Антиспам

Отправить payload с заполненным honeypot либо `likely_bot = true`.

Ожидание:

- HTTP `202`;
- `ok = false` и `success = false`;
- `error_code = request_rejected`;
- ответ не содержит причину блокировки или поле `blocked`;
- заявка не сохранена.

## 8. Rate limit

На тестовом fingerprint исчерпать установленный лимит.

Ожидание:

```json
{
  "ok": false,
  "success": false,
  "error_code": "rate_limit_exceeded",
  "request_id": "<исходный request_id>",
  "retry_after_seconds": 3600
}
```

Не должны возвращаться:

- `attempt_count`;
- `rate_limit`;
- fingerprint;
- IP или часть телефона.

## 9. Backend unavailable

В тестовом окружении убрать обязательную серверную конфигурацию.

Ожидание:

- HTTP `503`;
- `error_code = backend_unavailable`;
- отсутствует название отсутствующего secret.

## 10. Migration/RPC unavailable

На отдельном тестовом проекте проверить отсутствие обязательной RPC или несовместимую схему.

Ожидание:

- HTTP `503`;
- `error_code = backend_migration_required`;
- отсутствуют SQLSTATE, название функции, таблицы или constraint.

## 11. Ошибка сохранения

Смоделировать безопасную ошибку вставки, не используя реальные данные клиента.

Ожидание:

- HTTP `500`;
- `error_code = lead_storage_failed`;
- исходный валидный `request_id` сохранён;
- PostgreSQL `error.code` отсутствует в response.

## 12. Клиентская совместимость

Подтвердить, что `assets/js/online-application.js`:

- считает ответ ошибочным по HTTP status, `ok === false` или `success === false`;
- не зависит от `errors`, `attempt_count`, `rate_limit` или `blocked`;
- после ошибки сохраняет подготовленный текст и резервные каналы.

## Запрещённые поля

Проверить все ответы `202–503` на отсутствие:

- `error`;
- `message`;
- `errors`;
- `blocked`;
- `attempt_count`;
- `rate_limit`;
- `lead_id`;
- `technical_priority`;
- `qualification`;
- SQLSTATE и stack trace;
- контактных и ипотечных сведений.

## Конфигурация сайта

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

## Критерий приёмки

Smoke пройден, когда все ошибки используют единый envelope, correlation ID присутствует во всех ветках, только `429` получает `retry_after_seconds`, внутренние причины остаются в закрытом журнале, а публичный Supabase endpoint не включён.
