# Контракт ответа для заявки с ограниченной обработкой

## Назначение

После подтверждённого privacy-запроса заявка может получить `processing_restricted = true`, `retention_hold = true` либо быть обезличена. Повторный POST с тем же `request_id` не должен запускать Telegram, менять заявку или показывать браузеру ложный статус `pending`.

## Публичный ответ Edge Function

Публичная Edge Function уже использует ограниченный набор статусов доставки:

- `pending`;
- `sending`;
- `sent`;
- `failed`;
- `disabled`.

Для restricted, hold и anonymized заявки функция `claim_broker_lead_notification` возвращает:

```json
{
  "claimed": false,
  "current_status": "disabled",
  "attempt_count": 0
}
```

Фактический `attempt_count` возвращается из строки заявки; пример выше показывает новую заявку без предыдущих попыток.

Edge Function передаёт браузеру:

```json
{
  "ok": true,
  "success": true,
  "duplicate": true,
  "notification_status": "disabled"
}
```

HTTP-ответ остаётся `200`, поскольку исходная заявка существует и повторный request ID обработан идемпотентно. Статус `disabled` означает только отсутствие дальнейшей серверной доставки, а не новую заявку и не ошибку формы.

## Внутренний административный статус

Закрытый ручной retry сохраняет более точный внутренний ответ `restricted`. Это позволяет оператору отличить privacy-ограничение от обычного выключенного Telegram-канала.

Публичный браузер не получает blocker code, причины privacy-запроса, `retention_hold`, `processing_restricted`, `anonymized_at` или другие внутренние признаки.

## Запрещённое поведение

Нельзя:

- нормализовать `restricted` в `pending`;
- увеличивать `notification_attempt_count`;
- переводить заявку в `sending`;
- формировать Telegram-сводку;
- создавать notification event;
- возвращать клиенту внутренний blocker code;
- раскрывать причину ограничения обработки;
- изменять режим сайта с `web3forms` до общей Supabase-приёмки.

## Граница каналов

Этот контракт относится только к будущему Supabase Edge Function. Он не удаляет и не отзывает уже доставленный Web3Forms email, SMS, MAX, ВКонтакте, Telegram или данные сторонней CRM.
