# Контракт ошибок публичной Edge Function

## Назначение

`broker-public-lead` использует единый безопасный формат ошибок. Браузер не должен получать внутренние коды PostgreSQL, тексты исключений, счётчики rate limit, причины антиспама или подробный список серверных проверок.

## Единый error envelope

Все ответы с ошибкой содержат:

```json
{
  "ok": false,
  "success": false,
  "error_code": "validation_failed",
  "request_id": "4ad69d4d-e387-4f38-a7ac-c13b87aa160b"
}
```

Для `rate_limit_exceeded` дополнительно разрешено только:

```json
{
  "retry_after_seconds": 3600
}
```

Другие дополнительные поля в публичном error response запрещены.

## Correlation request ID

- После успешного разбора payload используется валидный клиентский `request_id`.
- До разбора JSON, при неправильном или отсутствующем `request_id` создаётся новый UUID через `crypto.randomUUID()`.
- Correlation ID предназначен для сопоставления обращения с серверным журналом и не является внутренним UUID строки `broker_leads`.
- В ответ не возвращается `lead_id`.

## Публичные коды

| HTTP | `error_code` | Смысл |
|---|---|---|
| 202 | `request_rejected` | антиспам отклонил запрос без раскрытия причины |
| 400 | `invalid_json` | тело нельзя безопасно разобрать как JSON-объект |
| 403 | `origin_not_allowed` | Origin не входит в белый список |
| 405 | `method_not_allowed` | разрешены только POST и корректный OPTIONS preflight |
| 413 | `payload_too_large` | превышен допустимый размер тела |
| 415 | `content_type_not_supported` | требуется JSON Content-Type |
| 422 | `validation_failed` | серверная проверка payload не пройдена |
| 429 | `rate_limit_exceeded` | превышен почасовой лимит |
| 500 | `lead_storage_failed` | заявка не была надёжно сохранена |
| 503 | `backend_unavailable` | серверная конфигурация недоступна |
| 503 | `backend_migration_required` | обязательная миграция или RPC не готовы |

Коды являются публичным белым списком. Нельзя формировать `error_code` из текста исключения, `error.code`, SQLSTATE или ответа Telegram.

## Запрещённые поля

Error response не содержит:

- `error` и `message` с техническим текстом;
- массив `errors`;
- `blocked`;
- `attempt_count` и `rate_limit`;
- `lead_id`, CRM status, priority или qualification;
- имя, телефон, город, ипотечные вводные или tracking;
- SQLSTATE, название таблицы, constraint или stack trace;
- Telegram error и серверные secrets.

Внутренние причины могут фиксироваться только в закрытом серверном журнале.

## Кэширование и CORS

Все JSON-ответы Edge Function получают `Cache-Control: no-store`.

CORS применяется только для разрешённого Origin. Запрещённый Origin получает безопасный envelope, но браузер не предоставляет его вызывающей странице без разрешающего CORS-заголовка.

## Совместимость клиента

Клиентская форма считает ответ ошибочным по HTTP status, `ok === false` или `success === false`. Она не зависит от подробных массивов валидации, внутренних счётчиков или PostgreSQL-кодов.

При любой ошибке подготовленный текст остаётся доступен для SMS, MAX, ВКонтакте, Web Share и ручного копирования.

## Текущее состояние

До полного Supabase smoke рабочая конфигурация остаётся:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

Контракт не включает публичный Supabase endpoint и не меняет действующую доставку Web3Forms.