# Smoke-тест серверной сводки уведомления

## Назначение

Проверить функцию `public.broker_lead_notification_summary(uuid)` до подключения Telegram или другого серверного канала уведомлений.

Тест выполняется только после применения миграций:

1. `202607070001_create_broker_leads.sql`;
2. `202607130002_broker_leads_v2.sql`;
3. `202607130003_broker_lead_preparation.sql`;
4. `202607130004_broker_lead_notification_summary.sql`.

До завершения теста сайт сохраняет:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

## Проверка прав

В SQL Editor подтверждённого Supabase-проекта:

```sql
select routine_name, security_type
from information_schema.routines
where routine_schema = 'public'
  and routine_name = 'broker_lead_notification_summary';
```

Проверить права:

```sql
select grantee, privilege_type
from information_schema.routine_privileges
where specific_schema = 'public'
  and routine_name = 'broker_lead_notification_summary'
order by grantee;
```

Ожидается:

- функция существует;
- используется `SECURITY DEFINER`;
- вызов разрешён только `service_role`;
- `anon` и `authenticated` не имеют `EXECUTE`.

## Подготовка тестовой заявки

Создать заявку через Edge Function smoke-тест с объектом `preparation`:

```json
{
  "context_version": 1,
  "active": true,
  "journey_type": "Сложный региональный маршрут",
  "journey_stage": "После изучения маршрута подготовки",
  "scenario_slug": "otkazali-v-ipoteke",
  "completed_checks": ["diagnosis", "finances"],
  "completed_labels": [
    "Зафиксировал(а) банк, дату и этап отказа",
    "Проверил(а) кредиты, карты и ежемесячные платежи"
  ],
  "remaining_questions": "SMOKE TEST — нужно понять, связан ли отказ с объектом"
}
```

После вставки получить `lead_id`.

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
- неизвестные ключи и вложенные поля отсутствуют;
- вопрос ограничен допустимой длиной;
- исходный комментарий клиента не изменён.

## Формирование сводки

Вызов выполнять серверной ролью или в доверенном SQL Editor:

```sql
select public.broker_lead_notification_summary('LEAD_ID');
```

Ожидаемый текст содержит:

- `Новая заявка ипотечному брокеру`;
- request ID;
- имя и телефон;
- город и способ связи;
- сценарий и объект;
- приоритет и источник;
- раздел `ПОДГОТОВКА ДО ОБРАЩЕНИЯ` ровно один раз;
- две выбранные отметки;
- оставшийся вопрос.

Текст не должен содержать:

- полный `raw_payload`;
- UTM JSON целиком;
- honeypot и fingerprint rate limit;
- паспорт, СНИЛС, банковские реквизиты или коды;
- Telegram bot token или chat ID.

## Обычная заявка

Создать тестовую заявку без объекта `preparation` и вызвать функцию.

Ожидается:

- базовая сводка формируется;
- раздел `ПОДГОТОВКА ДО ОБРАЩЕНИЯ` отсутствует;
- пустые служебные строки не добавляются.

## Неизвестный UUID

```sql
select public.broker_lead_notification_summary('00000000-0000-4000-8000-ffffffffffff');
```

Ожидается ошибка `broker_lead_not_found`.

Эту ошибку нельзя возвращать посетителю сайта как внутренний stack trace.

## Проверка будущего Telegram

После отдельного подтверждения Telegram secrets серверный обработчик должен:

1. сохранить заявку;
2. вызвать `broker_lead_notification_summary(lead_id)`;
3. отправить возвращённый текст в тестовый чат;
4. обновить `notification_status`;
5. создать событие `notification_sent` или `notification_failed`.

Проверить:

- одно сообщение на одну новую заявку;
- повтор с тем же request ID не создаёт второе уведомление;
- ошибка Telegram не удаляет заявку;
- сообщение читается на мобильном устройстве;
- подготовка отделена от комментария клиента;
- URL и персональные данные не публикуются в логах.

## Результат

Зафиксировать в issue №7:

- дату применения четвёртой миграции;
- test lead ID и request ID;
- результат проверки прав;
- текст сводки без публикации телефона;
- отсутствие раздела подготовки у обычной заявки;
- результат неизвестного UUID;
- подтверждённый Telegram-чат;
- результат duplicate и notification status;
- ответственного и план отката.
