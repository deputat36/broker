# Контракт ответа для заявки с ограниченной обработкой

## Назначение

После подтверждённого privacy-запроса заявка может получить `processing_restricted = true`, `retention_hold = true` либо быть обезличена. Повторный POST с тем же `request_id` не должен запускать Telegram, менять заявку, показывать браузеру ложный статус `pending` или раскрывать внутренние CRM-поля.

## Публичный ответ Edge Function

Публичная Edge Function использует ограниченный набор статусов доставки:

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

Edge Function завершает restricted duplicate до повторного Telegram claim и передаёт браузеру минимальный ответ:

```json
{
  "ok": true,
  "success": true,
  "duplicate": true,
  "request_id": "исходный request ID",
  "notification_status": "disabled"
}
```

`request_id` уже создан браузером при первом заполнении и используется как номер обращения. Он не заменяется внутренним `lead_id`.

HTTP-ответ остаётся `200`, поскольку исходная заявка существует и повторный request ID обработан идемпотентно. Статус `disabled` означает только отсутствие дальнейшей серверной доставки, а не новую заявку и не ошибку формы.

## Минимизация данных

Restricted duplicate не возвращает:

- внутренний `lead_id`;
- `crm_status`;
- `technical_priority`;
- объект `qualification`;
- blocker code;
- причины privacy-запроса;
- `retention_hold`;
- `processing_restricted`;
- `anonymized_at`;
- контактные, ипотечные или рекламные сведения.

Новая, обычная duplicate и restricted duplicate заявки используют один и тот же минимальный публичный envelope. Отличаются только HTTP-код, значение `duplicate` и фактический `notification_status`. Полный контракт описан в `docs/public-lead-response-contract.md`.

## Внутренний административный статус

Закрытый ручной retry сохраняет более точный внутренний ответ `restricted`. Это позволяет оператору отличить privacy-ограничение от обычного выключенного Telegram-канала.

Публичный браузер не получает внутренний статус `restricted` или другие признаки причины блокировки.

## Запрещённое поведение

Нельзя:

- нормализовать `restricted` в `pending`;
- увеличивать `notification_attempt_count`;
- переводить заявку в `sending`;
- формировать Telegram-сводку;
- создавать notification event;
- возвращать restricted duplicate внутренний `lead_id`, CRM-статус, приоритет или qualification;
- возвращать клиенту внутренний blocker code;
- раскрывать причину ограничения обработки;
- изменять режим сайта с `web3forms` до общей Supabase-приёмки.

## Граница каналов

Этот контракт относится только к будущему Supabase Edge Function. Он не удаляет и не отзывает уже доставленный Web3Forms email, SMS, MAX, ВКонтакте, Telegram или данные сторонней CRM.