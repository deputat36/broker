# Smoke-тест хранения и очистки заявок

## Назначение

Проверить миграцию `202607140001_broker_lead_retention.sql` в подтверждённом тестовом Supabase-проекте до включения серверного канала и до работы с реальными заявками.

Во время теста публичный сайт сохраняет:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

Retention policy должна оставаться выключенной до этапа явного тестового включения.

## Предварительные условия

1. Используется отдельный тестовый проект или полностью тестовые строки с пометкой `RETENTION SMOKE`.
2. Применены миграции по порядку, включая `202607140001_broker_lead_retention.sql`.
3. Secrets, телефоны реальных клиентов и реальные тексты заявок не используются.
4. Автоматический Cron job отсутствует.
5. Назначен оператор теста и подготовлен план отката.

## Проверка объектов

Проверить таблицы и поля:

```sql
select to_regclass('public.broker_lead_retention_settings');
select to_regclass('public.broker_lead_retention_runs');

select column_name, data_type
from information_schema.columns
where table_schema = 'public'
  and table_name = 'broker_leads'
  and column_name in (
    'retention_hold',
    'anonymized_at',
    'retention_reason_code'
  )
order by column_name;
```

Проверить функции:

```sql
select routine_name, security_type
from information_schema.routines
where routine_schema = 'public'
  and routine_name in (
    'broker_lead_retention_preview',
    'apply_broker_lead_retention'
  )
order by routine_name;
```

Ожидается:

- обе функции существуют;
- используются `SECURITY DEFINER` и фиксированный `search_path`;
- RLS включён на двух retention-таблицах;
- `public`, `anon` и `authenticated` не имеют доступа;
- `service_role` имеет только предусмотренные права.

## Политика выключена по умолчанию

```sql
select *
from public.broker_lead_retention_settings;
```

Ожидается:

- одна singleton-строка;
- `enabled = false`;
- terminal-статусы входят только в `closed`, `lost`, `archived`, `cancelled`;
- числовые сроки проходят constraints.

Попытка добавить `new` в `terminal_statuses` должна завершиться ошибкой constraint.

## Подготовка тестовых сценариев

Создать минимум шесть тестовых лидов:

1. старый `closed` + `sent` — кандидат;
2. старый `new` + `sent` — активный и защищённый;
3. старый `closed` + `failed` — unresolved и защищённый;
4. старый `closed` + `sent` + `retention_hold = true` — защищённый hold;
5. свежий `closed` + `sent` — ещё не достиг срока;
6. старый неизвестный статус + `sent` — защищён fail-closed.

Для кандидата заполнить тестовые значения во всех группах полей:

- имя, телефон, город;
- ипотечные вводные;
- комментарий и банковскую историю;
- UTM, URL, referrer и User-Agent;
- tracking, qualification, spam_check и raw_payload;
- preparation и remaining_questions.

Добавить:

- старое событие кандидата;
- старое событие активного лида;
- новую event-запись кандидата;
- старую и новую rate-limit запись.

Использовать только явно тестовые значения.

## Preview

```sql
select *
from public.broker_lead_retention_preview();
```

Проверить:

- `policy_enabled = false`;
- кандидат учитывается в `eligible_terminal_leads`;
- активный и неизвестный лиды учитываются как защищённые;
- `failed` учитывается в `protected_notification_leads`;
- hold учитывается в `protected_hold_leads`;
- старое событие активного необезличенного лида не считается eligible;
- ответ не содержит UUID, request ID, имени, телефона, города или текста заявки.

Сохранить агрегаты без идентификаторов клиента в issue приёмки.

## Блокировка выключенной политики

```sql
select *
from public.apply_broker_lead_retention('APPLY_BROKER_RETENTION');
```

При `enabled = false` ожидается ошибка:

```text
broker_retention_disabled
```

Ни одна строка и событие не должны измениться.

## Блокировка неправильного подтверждения

В тестовой среде временно включить policy:

```sql
update public.broker_lead_retention_settings
set enabled = true,
    updated_at = now()
where singleton = true;
```

Вызвать с неправильной строкой:

```sql
select *
from public.apply_broker_lead_retention('WRONG_CONFIRMATION');
```

Ожидается `broker_retention_confirmation_required` без изменений данных.

## Успешное применение

Перед применением повторить preview и сверить ожидаемые количества.

```sql
select *
from public.apply_broker_lead_retention('APPLY_BROKER_RETENTION');
```

Ожидается:

- возвращён новый run ID;
- обезличен только старый terminal-лид с `sent`;
- активный `new` не изменён;
- неизвестный статус не изменён;
- `failed` не изменён;
- hold-лид не изменён;
- свежий terminal-лид не изменён;
- строка лида физически не удалена.

## Проверка обезличивания

Для тестового кандидата проверить:

```sql
select
  status,
  notification_status,
  retention_hold,
  anonymized_at,
  retention_reason_code,
  client_name,
  phone,
  city,
  comment,
  phone_normalized,
  raw_payload,
  tracking,
  qualification,
  spam_check,
  preparation,
  preparation_completed,
  remaining_questions
from public.broker_leads
where id = 'TEST_LEAD_ID';
```

Ожидается:

- `anonymized_at` заполнен;
- `retention_reason_code = scheduled_anonymization`;
- `phone = [anonymized]`;
- контактные и содержательные текстовые поля равны `null`;
- JSON-поля очищены до `{}` или `[]`;
- terminal-статус, notification status, внутренний ID, request ID и технические даты сохранены.

Повторный запуск не должен повторно учитывать уже обезличенный лид.

## Проверка событий

Проверить, что:

- старое событие обезличенного лида удалено;
- новое событие обезличенного лида сохранено до достижения срока;
- старое событие активного или hold-лида не удалено;
- события необезличенных лидов не затронуты.

## Проверка rate limit

Проверить, что:

- старая техническая rate-limit запись удалена;
- новая запись сохранена;
- таблица по-прежнему не содержит исходный IP, полный телефон или payload.

## Журнал успешного запуска

```sql
select
  id,
  started_at,
  finished_at,
  status,
  policy_snapshot,
  anonymized_leads,
  deleted_events,
  deleted_rate_limits
from public.broker_lead_retention_runs
order by started_at desc
limit 1;
```

Ожидается:

- `status = completed`;
- количества совпадают с результатом функции;
- snapshot содержит только сроки и terminal-статусы;
- нет lead ID, request ID, имени, телефона, URL или текста заявки.

## Проверка атомарного отката

Только в изолированной тестовой среде временно создать контролируемую ошибку после начала операции, например запретить вставку в тестовый журнал retention.

Запустить apply и убедиться:

- вызов завершился ошибкой;
- обезличивание откатилось;
- события и rate-limit записи не были частично удалены;
- ложная строка `completed` не появилась.

После проверки вернуть схему в состояние миграции.

## Проверка hold

Установить `retention_hold = true` на старом terminal-лиде и повторить preview/apply.

Ожидается:

- лид учитывается как protected hold;
- его поля не очищаются;
- связанные события не удаляются.

Снять hold только после завершения теста и отдельной проверки основания.

## Повторный preview

После успешного запуска повторить:

```sql
select *
from public.broker_lead_retention_preview();
```

Количество кандидатов должно уменьшиться на число обезличенных лидов. Активные, unresolved и hold-защиты должны остаться неизменными.

## Отключение после теста

Обязательно вернуть:

```sql
update public.broker_lead_retention_settings
set enabled = false,
    updated_at = now()
where singleton = true;
```

Не создавать Cron job и не включать автоматический запуск в рамках первого smoke.

## Проверка сторонних каналов

Подтвердить отдельно:

- Supabase retention не удаляет Web3Forms email;
- сообщения в SMS, MAX и ВКонтакте не удаляются;
- почтовый ящик и сторонняя CRM имеют собственную процедуру хранения;
- пользователю не сообщается о полном удалении из всех каналов после одного Supabase purge.

## Результат

Зафиксировать в отдельном issue:

- проект и дату применения миграции;
- утверждённые сроки;
- утверждённые terminal-статусы;
- агрегаты preview до и после;
- результат active/unresolved/hold-защит;
- результат атомарного отката;
- run ID без публикации lead ID и request ID;
- отсутствие Cron;
- ответственного за включение и откат;
- состояние policy `enabled = false` после теста.
