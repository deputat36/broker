# Smoke: минимальный публичный ответ Edge Function

## Preconditions

- применены 11 миграций по `docs/supabase-migration-order.md`;
- функция развёрнута только в тестовом проекте;
- рабочий сайт сохраняет `mode: "web3forms"` и `endpoint: ""`;
- используются только тестовые данные.

## 1. Новая заявка

Отправить валидный payload с новым `request_id`.

Ожидание: HTTP `201` и ровно пять ключей:

```json
{
  "ok": true,
  "success": true,
  "duplicate": false,
  "request_id": "<исходный request_id>",
  "notification_status": "disabled"
}
```

Значение `notification_status` зависит от тестовой конфигурации Telegram, но должно входить в разрешённый список.

Ответ не содержит:

- `lead_id`;
- `crm_status`;
- `technical_priority`;
- `qualification`;
- контактные сведения;
- ипотечные вводные;
- tracking или `raw_payload`.

Проверить в базе, что внутренний UUID, qualification и technical priority при этом сохранены.

## 2. Обычный duplicate

Повторить тот же POST.

Ожидание: HTTP `200`, тот же набор из пяти ключей, `duplicate: true` и тот же `request_id`.

Если Telegram уже завершён, второе уведомление не отправляется. В ответе по-прежнему отсутствуют внутренние поля.

## 3. Restricted duplicate

Выполнить `docs/supabase-restricted-delivery-response-smoke.md`.

Ожидание: тот же минимальный envelope, `duplicate: true`, `notification_status: "disabled"`, отсутствие Telegram и внутренних полей.

## 4. Клиентская совместимость

В тестовой копии временно настроить custom endpoint и отправить заявку через браузер.

Подтвердить:

- `sendCustomLead` принимает минимальный success response;
- появляется сообщение об успешной отправке;
- выполняется переход на `/spasibo/`;
- страница подтверждения получает номер из исходного payload;
- локальная сводка содержит сценарий и город из формы;
- код не обращается к `response.lead_id`, `response.crm_status`, `response.technical_priority` или `response.qualification`.

После теста вернуть `endpoint: ""`.

## 5. Безопасные ошибки

Проверить invalid JSON, неправильный Origin, oversized payload, rate limit и отсутствие миграций.

Ответы не должны содержать:

- stack trace;
- SQL-текст;
- service role key;
- Telegram token;
- имя, телефон или комментарий заявки.

## 6. Проверка серверного хранения

Для созданной тестовой строки подтвердить наличие:

- `id`;
- `status`;
- `technical_priority`;
- `qualification`;
- `raw_payload`;
- notification status и событий;
- `client_delivery_state` после применения одиннадцатой миграции.

Минимизация относится только к HTTP-ответу и не удаляет серверные сведения.

## Критерий приёмки

Smoke пройден, когда новая, обычная duplicate и restricted duplicate заявки возвращают единый пятиключевой envelope, клиентский сценарий работает без внутренних полей, серверные сведения сохраняются, а рабочий Supabase endpoint остаётся выключенным.
