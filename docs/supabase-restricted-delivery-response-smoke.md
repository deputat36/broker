# Smoke: restricted delivery response

## Preconditions

- применены 11 миграций в лексикографическом порядке;
- публичный endpoint ещё не включён на рабочем сайте;
- тест выполняется только на отдельной тестовой заявке;
- известны точные `lead_id` и `request_id`;
- Telegram secrets могут быть настроены, чтобы проверить отсутствие отправки.

## 1. Обычная заявка

1. Создать тестовую заявку со статусом уведомления `pending`.
2. Вызвать `claim_broker_lead_notification`.
3. Подтвердить:
   - `claimed = true`;
   - `current_status = sending`;
   - счётчик попыток увеличился на один.
4. Вернуть тестовую заявку в исходное состояние либо удалить тестовые данные по принятой процедуре.

## 2. Ограничение обработки

1. Провести полный privacy workflow с действием `restrict_processing`.
2. Подтвердить:
   - `processing_restricted = true`;
   - `retention_hold = true`;
   - заявка не обезличена.
3. Зафиксировать исходный `notification_attempt_count`.

## 3. SQL claim restricted-заявки

Вызвать:

```sql
select *
from public.claim_broker_lead_notification(
  '<lead_id>'::uuid,
  '<request_id>'
);
```

Ожидание:

- `claimed = false`;
- `current_status = disabled`;
- `notification_attempt_count` не изменился;
- `notification_status` в строке не изменился;
- новые notification events отсутствуют.

## 4. Повторный POST Edge Function

Отправить тот же валидный payload с исходным `request_id`.

Ожидание HTTP `200`:

```json
{
  "ok": true,
  "success": true,
  "duplicate": true,
  "request_id": "<request_id>",
  "notification_status": "disabled"
}
```

Подтвердить точный набор ключей ответа. Restricted duplicate не должен содержать:

- `lead_id`;
- `crm_status`;
- `technical_priority`;
- `qualification`;
- `processing_restricted`;
- `retention_hold`;
- `anonymized_at`;
- blocker code;
- контактные или ипотечные поля.

Дополнительно подтвердить:

- Telegram-сообщение не отправлено;
- статус не заменён на `pending`;
- строка заявки не изменена;
- `notification_attempt_count` не увеличился;
- браузер продолжил считать ответ успешной идемпотентной обработкой.

## 5. Обезличенная заявка

1. На отдельной тестовой строке выполнить подтверждённый privacy anonymize.
2. Повторить SQL claim и duplicate POST.
3. Ожидать тот же минимальный ответ с `request_id` и `disabled`, отсутствие новой попытки и отсутствие Telegram.

## 6. Retention hold без privacy restriction

1. На отдельной тестовой строке установить допустимый `retention_hold = true` до включения operational guard либо через утверждённую тестовую процедуру.
2. Вызвать claim и повторный POST.
3. Ожидать `claimed = false`, `current_status = disabled`, минимальный публичный ответ и неизменный счётчик.

## 7. Обычная duplicate-заявка

1. Создать отдельную заявку без restriction, hold и anonymize.
2. Повторить POST с тем же `request_id`.
3. Подтвердить тот же пятиключевой envelope с `duplicate: true`.
4. Убедиться, что внутренние `lead_id`, CRM-статус, приоритет и qualification отсутствуют так же, как в restricted-ответе.
5. Подтвердить, что обычная duplicate может завершить ранее ожидавшее уведомление, а restricted duplicate не запускает доставку.

## 8. Административный retry

Вызвать закрытый retry-handler для restricted-заявки.

Ожидание:

- HTTP `409`;
- `error = retry_not_allowed`;
- внутренний `notification_status = restricted`;
- browser-safe преобразование в `disabled` не изменяет административную диагностику.

## 9. Проверка прав

Под ролями `anon` и `authenticated` вызов `claim_broker_lead_notification` должен завершиться отказом в доступе.

## 10. Проверка конфигурации сайта

Подтвердить:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

## Критерий приёмки

Smoke считается пройденным, когда restricted, hold и anonymized заявки возвращают браузеру только `ok`, `success`, `duplicate`, `request_id` и `notification_status: disabled`; обычная duplicate использует тот же минимальный envelope; внутренние CRM-поля отсутствуют, административный путь сохраняет `restricted`, счётчики и события restricted-заявки не меняются, Telegram не отправляется, а публичный Supabase endpoint остаётся выключенным.
