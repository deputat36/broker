# Smoke-тест атомарной доставки уведомления

## Назначение

Проверить серверную цепочку:

`сохранённая заявка → атомарный claim → защищённая сводка → Telegram → sent/failed`.

Тест выполняется только после применения миграций:

1. `202607070001_create_broker_leads.sql`;
2. `202607130002_broker_leads_v2.sql`;
3. `202607130003_broker_lead_preparation.sql`;
4. `202607130004_broker_lead_notification_summary.sql`;
5. `202607130005_broker_lead_notification_delivery.sql`.

До завершения теста сайт сохраняет:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

## Проверка функций и прав

```sql
select routine_name, security_type
from information_schema.routines
where routine_schema = 'public'
  and routine_name in (
    'broker_lead_notification_summary',
    'claim_broker_lead_notification',
    'complete_broker_lead_notification'
  )
order by routine_name;
```

Проверить права:

```sql
select routine_name, grantee, privilege_type
from information_schema.routine_privileges
where specific_schema = 'public'
  and routine_name in (
    'broker_lead_notification_summary',
    'claim_broker_lead_notification',
    'complete_broker_lead_notification'
  )
order by routine_name, grantee;
```

Ожидается:

- все функции используют `SECURITY DEFINER`;
- вызов разрешён только `service_role`;
- `anon` и `authenticated` не имеют `EXECUTE`;
- публичный доступ отсутствует.

## Проверка колонок и constraint

```sql
select column_name, data_type
from information_schema.columns
where table_schema = 'public'
  and table_name = 'broker_leads'
  and column_name in (
    'notification_status',
    'notification_attempt_count',
    'notification_attempted_at',
    'notification_sent_at',
    'notification_last_error'
  )
order by column_name;
```

Constraint должен разрешать только `pending`, `sending`, `sent`, `failed` и `disabled`.

## Подготовка тестовой заявки

Создать заявку через Edge Function smoke-тест с объектом `preparation` и подтверждённым тестовым request ID.

До включения Telegram можно вручную перевести тестовую запись в очередь:

```sql
update public.broker_leads
set
  notification_status = 'pending',
  notification_attempt_count = 0,
  notification_attempted_at = null,
  notification_sent_at = null,
  notification_last_error = null
where id = 'LEAD_ID';
```

Использовать только явно тестовую запись.

## Проверка очищенных CRM-полей

```sql
select
  journey_type,
  journey_stage,
  journey_scenario_slug,
  preparation_completed,
  remaining_questions,
  preparation
from public.broker_leads
where id = 'LEAD_ID';
```

Ожидается:

- scenario slug входит в whitelist;
- массив содержит не более четырёх подписей;
- неизвестные ключи отсутствуют;
- исходный комментарий клиента не изменён.

## Формирование сводки

```sql
select public.broker_lead_notification_summary('LEAD_ID');
```

Текст содержит request ID, контакты, сценарий, приоритет, источник и раздел `ПОДГОТОВКА ДО ОБРАЩЕНИЯ` ровно один раз.

Текст не содержит полный `raw_payload`, UTM JSON целиком, honeypot, rate-limit fingerprint, Telegram secrets и stack trace.

## Первый атомарный claim

```sql
select *
from public.claim_broker_lead_notification('LEAD_ID', 'REQUEST_ID');
```

Ожидается:

- `claimed = true`;
- `current_status = sending`;
- `attempt_count = 1`;
- заполнено `notification_attempted_at`.

## Параллельный и повторный claim

Сразу повторить тот же вызов.

Ожидается:

- `claimed = false`;
- статус остаётся `sending`;
- счётчик не увеличивается.

При параллельном запуске двух транзакций только один вызов получает `claimed = true`.

## Успешное завершение

```sql
select public.complete_broker_lead_notification(
  'LEAD_ID',
  'REQUEST_ID',
  true,
  null
);
```

Ожидается `sent`, заполненный `notification_sent_at`, очищенный `notification_last_error` и отказ нового claim.

## Ошибка доставки

На новой тестовой записи выполнить claim и завершить ошибкой:

```sql
select public.complete_broker_lead_notification(
  'LEAD_ID',
  'REQUEST_ID',
  false,
  'telegram_http_500'
);
```

Ожидается:

- статус `failed`;
- безопасный код в `notification_last_error`;
- новый claim возвращает `claimed = false`;
- failed-уведомление автоматически не повторяется.

Ручной повтор после анализа причины выполняется отдельной административной операцией.

## Восстановление зависшего sending

На отдельной тестовой записи:

```sql
update public.broker_leads
set
  notification_status = 'sending',
  notification_attempted_at = now() - interval '16 minutes',
  notification_attempt_count = 1
where id = 'LEAD_ID';
```

Повторный claim должен вернуть `claimed = true`, `attempt_count = 2` и новое время попытки. Для `sending` моложе 15 минут claim отклоняется.

## Duplicate request ID через Edge Function

После деплоя тестовой Edge Function:

1. отправить новую заявку;
2. убедиться, что сообщение пришло один раз;
3. повторить POST с тем же `request_id`;
4. проверить `duplicate: true`;
5. убедиться, что второе сообщение не пришло;
6. проверить, что строка заявки одна;
7. проверить, что событие `notification_sent` одно.

Если первая попытка сохранила заявку, но не успела получить claim, duplicate-запрос может завершить `pending` уведомление.

## Аварийное окно после Telegram

Telegram не принимает идемпотентный ключ. Смоделировать:

1. сообщение принято Telegram;
2. фиксация `sent` не выполнена;
3. запись осталась `sending`;
4. до 15 минут duplicate не отправляет сообщение;
5. после 15 минут восстановление может создать повтор с тем же request ID.

Request ID в тексте используется для распознавания возможного дубля. Этот остаточный риск фиксируется при приёмке.

## Неизвестный UUID

```sql
select public.broker_lead_notification_summary('00000000-0000-4000-8000-ffffffffffff');
```

Ожидается `broker_lead_not_found`. Ошибка не возвращается посетителю сайта как stack trace.

## Проверка будущего Telegram

После подтверждения secrets серверный обработчик должен сохранить заявку, получить claim, сформировать сводку, отправить сообщение, завершить попытку и создать `notification_sent` или `notification_failed`.

Проверить:

- одно сообщение при обычном повторе request ID;
- ошибка Telegram не удаляет заявку;
- сообщение читается на мобильном устройстве;
- подготовка отделена от комментария;
- персональные данные не публикуются в технических логах.

## Результат

Зафиксировать в issue №7:

- дату применения пятой миграции;
- test lead ID и request ID;
- результат проверки прав;
- первый и повторный claim;
- результат `sent` и `failed`;
- восстановление зависшего `sending`;
- duplicate POST;
- подтверждённый тестовый чат;
- остаточный аварийный риск;
- ответственного и план отката.