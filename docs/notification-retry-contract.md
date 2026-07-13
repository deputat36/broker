# Контракт ручного повтора уведомлений

## Назначение

Ручной retry используется только для заявок, которые уже сохранены в `public.broker_leads`, но Telegram-уведомление завершилось статусом `failed`.

Он не является частью публичной формы, не вызывается из браузера посетителя и не заменяет Web3Forms.

До полного smoke-теста сайт сохраняет:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

## Состав

Шестая миграция:

`supabase/migrations/202607130006_broker_lead_notification_manual_retry.sql`

Закрытая Edge Function:

`supabase/functions/broker-notification-retry/index.ts`

Миграция применяется после пяти предыдущих миграций backend:

1. `202607070001_create_broker_leads.sql`;
2. `202607130002_broker_leads_v2.sql`;
3. `202607130003_broker_lead_preparation.sql`;
4. `202607130004_broker_lead_notification_summary.sql`;
5. `202607130005_broker_lead_notification_delivery.sql`;
6. `202607130006_broker_lead_notification_manual_retry.sql`.

## Разрешённый переход статуса

Новый ручной запрос может выполнить только переход:

```text
failed → pending → sending → sent | failed
```

Новый административный retry запрещён из:

- `sent`;
- `disabled`;
- `pending`;
- активного или зависшего `sending`.

SQL RPC переводит только `failed` в `pending`. Он не расширяет допустимые исходные статусы.

## Восстановление прерванного retry

Если административная функция уже получила подтверждение SQL RPC, но аварийно завершилась позже, запись может остаться в `pending` или `sending`.

Повторный запуск может продолжить такую ранее подтверждённую попытку только при одновременном выполнении условий:

- `notification_manual_retry_count > 0`;
- статус равен `pending` или `sending`;
- в базе сохранён допустимый reason code;
- запрос передаёт тот же reason code;
- атомарный `claim_broker_lead_notification` разрешает захват.

Активный `sending` не захватывается повторно. Зависший `sending` может быть восстановлен штатным claim только после 15 минут.

Другой reason code возвращает `retry_reason_mismatch`. Состояния без ранее подтверждённого ручного retry возвращают `retry_not_allowed`.

Такое восстановление не увеличивает `notification_manual_retry_count` и не создаёт второе событие `notification_retry_requested`.

## Причины retry

Свободный комментарий администратора не принимается. Разрешены только коды:

- `telegram_config_fixed`;
- `telegram_temporary_error`;
- `notification_summary_fixed`;
- `manual_recovery`.

Это предотвращает попадание имени, телефона, текста заявки и других персональных данных в технический журнал.

## SQL RPC

`public.request_broker_lead_notification_retry(uuid, text, text)`:

- доступна только `service_role`;
- проверяет UUID, request ID и текущий статус;
- переводит только `failed` в `pending`;
- увеличивает `notification_manual_retry_count`;
- сохраняет время и код причины;
- возвращает сохранённый `reason_code`;
- создаёт событие `notification_retry_requested`;
- не отправляет Telegram самостоятельно.

## Административная Edge Function

`broker-notification-retry` требует переменные окружения:

- `SUPABASE_URL`;
- `SUPABASE_SERVICE_ROLE_KEY`;
- `NOTIFICATION_ADMIN_TOKEN`;
- `TELEGRAM_BOT_TOKEN`;
- `TELEGRAM_CHAT_ID`;
- необязательный `TELEGRAM_TIMEOUT_MS`.

Секреты не размещаются в репозитории, `_config.yml`, браузерном JavaScript, URL или issue.

Функция:

- принимает только `POST application/json`;
- не устанавливает CORS-заголовки;
- требует `Authorization: Bearer ...`;
- сравнивает admin token по SHA-256 без прямого строкового сравнения;
- ограничивает тело 8192 байтами;
- принимает только `lead_id`, `request_id`, `reason_code`;
- возвращает только технический статус и счётчики;
- сообщает `resumed: true`, если продолжена ранее подтверждённая попытка;
- не возвращает имя, телефон, город, текст заявки, URL или `raw_payload`.

## Формат запроса

```json
{
  "lead_id": "00000000-0000-4000-8000-000000000001",
  "request_id": "00000000-0000-4000-8000-000000000002",
  "reason_code": "telegram_temporary_error"
}
```

## Журналирование

Создаются обезличенные события:

- `notification_retry_requested`;
- `notification_retry_sent`;
- `notification_retry_failed`.

Payload события может содержать только:

- `reason_code`;
- `retry_count`;
- `attempt_count`;
- безопасный `error_code`;
- логический признак `resumed`.

Полный payload заявки, Telegram token, chat ID и текст уведомления в событие не записываются.

## Контроль очереди

`public.broker_lead_notification_queue_health()` возвращает только агрегаты по статусу:

- количество заявок;
- время самой старой заявки;
- время самой старой попытки;
- количество зависших `sending` старше 15 минут;
- максимальное количество попыток;
- общее количество ручных retry.

Функция доступна только `service_role` и не возвращает идентификаторы, имена, телефоны, города, источники или тексты заявок.

## Ограничения

Telegram API не поддерживает идемпотентный ключ. Если Telegram принял сообщение, но функция аварийно завершилась до фиксации `sent`, повтор после ручной проверки теоретически может создать дубль. Оператор обязан сверить request ID в Telegram и базе до вызова retry.

`failed` не повторяется автоматически. Каждая новая попытка требует отдельного подтверждённого административного запроса.

## Активационный барьер

Deploy административной функции разрешён только после:

1. применения всех шести миграций;
2. проверки прав RPC;
3. теста в отдельном Telegram-чате;
4. проверки отсутствия CORS;
5. проверки неправильного admin token;
6. проверки восстановления `pending` и зависшего `sending` с тем же reason code;
7. проверки очереди без персональных данных;
8. фиксации ответственного и процедуры отката в issue №7.

Публичный Supabase endpoint и режим `hybrid` остаются выключенными до отдельной приёмки основного backend.