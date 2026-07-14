# Smoke-тест индивидуальных privacy-запросов

## Назначение

Проверить восьмую миграцию и точечный процесс ограничения обработки или обезличивания одной заявки до рабочего использования.

Тест проводится только на явно тестовых данных. Публичный сайт сохраняет:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

## Подготовка

Применить восемь миграций строго по порядку, последней:

`202607140002_broker_lead_privacy_requests.sql`

Проверить:

```sql
select to_regclass('public.broker_lead_privacy_requests');

select column_name, data_type
from information_schema.columns
where table_schema = 'public'
  and table_name = 'broker_leads'
  and column_name = 'processing_restricted';
```

Проверить функции:

```sql
select routine_name, security_type
from information_schema.routines
where routine_schema = 'public'
  and routine_name in (
    'broker_lead_privacy_request_preview',
    'start_broker_lead_privacy_request',
    'verify_broker_lead_privacy_request',
    'apply_broker_lead_privacy_request',
    'cancel_broker_lead_privacy_request'
  )
order by routine_name;
```

Ожидается `SECURITY DEFINER`, но EXECUTE только для `service_role`. У `public`, `anon`, `authenticated` прав быть не должно.

## Тестовые заявки

Создать отдельные заявки:

1. `sent`, без hold — для успешного anonymize;
2. `failed`, без hold — для успешного restrict processing;
3. `pending` — должна быть заблокирована;
4. `sending` — должна быть заблокирована;
5. `sent` + `retention_hold = true` — должна быть заблокирована;
6. уже обезличенная — должна быть заблокирована;
7. `sent`, без hold — для cancel.

Заполнить тестовыми значениями все группы полей, включая `raw_payload`, UTM, комментарий, preparation и notification metadata.

## Preview

```sql
select *
from public.broker_lead_privacy_request_preview('LEAD_ID', 'REQUEST_ID');
```

Проверить:

- точная пара ID возвращает `lead_found = true`;
- неправильный request ID возвращает `lead_found = false` и `lead_not_found`;
- pending/sending возвращают `notification_unresolved`;
- существующий hold возвращает `existing_retention_hold`;
- обезличенная заявка возвращает `already_anonymized`;
- ответ не содержит имя, телефон, город, комментарий, URL, UTM или raw payload.

## Блокировка неправильного start

Проверить неправильную строку подтверждения. Ожидается:

`broker_privacy_start_confirmation_required`

Проверить неизвестный action. Ожидается:

`broker_privacy_action_invalid`

Проверить start для pending/sending. Ожидается:

`broker_privacy_notification_unresolved`

Проверить start при existing hold. Ожидается:

`broker_privacy_existing_hold`

## Успешный start

```sql
select *
from public.start_broker_lead_privacy_request(
  'LEAD_ID',
  'REQUEST_ID',
  'anonymize',
  'START_BROKER_PRIVACY_REQUEST'
);
```

Ожидается:

- статус `pending_verification`;
- `retention_hold = true`;
- `processing_restricted = true`;
- одна строка в `broker_lead_privacy_requests`;
- событие `privacy_request_started`;
- повторный start блокируется `broker_privacy_open_request_exists`.

## Verify

Неверная строка подтверждения должна вернуть:

`broker_privacy_verify_confirmation_required`

Неизвестный method code должен вернуть:

`broker_privacy_verification_method_invalid`

Успешный вызов:

```sql
select *
from public.verify_broker_lead_privacy_request(
  'PRIVACY_REQUEST_ID',
  'same_contact_channel',
  'VERIFY_BROKER_PRIVACY_REQUEST'
);
```

Ожидается:

- статус `verified`;
- заполнены `verified_at` и method code;
- событие `privacy_request_verified`;
- повторный verify блокируется `broker_privacy_request_not_pending`.

## Apply до verification

Для отдельного pending-запроса вызвать apply. Ожидается:

`broker_privacy_request_not_verified`

Ни одно содержательное поле лида не должно измениться.

## Успешный anonymize

```sql
select *
from public.apply_broker_lead_privacy_request(
  'PRIVACY_REQUEST_ID',
  'APPLY_BROKER_PRIVACY_REQUEST'
);
```

Проверить:

- статус privacy request = `completed`;
- `anonymized = true`;
- строка `broker_leads` физически не удалена;
- `anonymized_at` заполнено;
- `retention_reason_code = manual_privacy_request`;
- `processing_restricted = true`;
- `retention_hold = false`;
- имя, телефон, город, комментарий, UTM, URL и referrer очищены;
- `tracking`, `qualification`, `spam_check`, `raw_payload`, `preparation` очищены;
- событие `privacy_request_completed` не содержит персональных данных.

## Restrict processing

Для заявки `failed` создать, проверить и применить action `restrict_processing`.

Ожидается:

- строка не обезличена;
- `processing_restricted = true`;
- `retention_hold = true`;
- privacy request = `completed`;
- дальнейшая автоматическая retention-очистка такую строку не затрагивает.

## Изменение состояния между verify и apply

После verify временно установить `notification_status = sending` либо снять hold.

Apply должен вернуть:

`broker_privacy_lead_state_changed`

Транзакция не должна частично очищать заявку.

## Cancel

Для отдельной заявки выполнить start, затем:

```sql
select *
from public.cancel_broker_lead_privacy_request(
  'PRIVACY_REQUEST_ID',
  'request_withdrawn',
  'CANCEL_BROKER_PRIVACY_REQUEST'
);
```

Проверить:

- статус `cancelled`;
- восстановлены предыдущие значения hold и processing restriction;
- событие `privacy_request_cancelled`;
- персональные поля не изменены;
- повторный cancel блокируется `broker_privacy_request_not_open`.

Неверная причина должна вернуть:

`broker_privacy_cancellation_reason_invalid`

## Проверка отсутствия поиска по персональным данным

В миграции и функциях не должно быть RPC с параметрами phone, client_name, city или email.

Таблица privacy requests не должна содержать свободный комментарий, документы, телефон или имя.

## Проверка событий

Допустимые payload-ключи:

- `action_code`;
- `verification_method_code`;
- `cancellation_reason_code`.

Проверить отсутствие телефона, имени, города, текста заявки, URL, raw payload и документов.

## Граница внешних каналов

Зафиксировать, что тест Supabase не удаляет:

- Web3Forms email;
- SMS/MAX/ВКонтакте;
- уже доставленное Telegram-сообщение;
- сведения сторонней CRM.

Для них нужна отдельная операционная процедура.

## Откат

При проблеме:

1. не использовать RPC privacy workflow;
2. оставить Supabase endpoint пустым;
3. не удалять таблицы и заявки оперативно;
4. сохранить `retention_hold` для запросов, которые требуют ручной проверки;
5. анализировать только технические коды и тестовые данные.

## Результат

Зафиксировать в issue приёмки:

- дату применения восьмой миграции;
- проверку прав;
- тестовые статусы без идентификаторов клиента;
- успешные preview/start/verify/apply/cancel;
- блокировки pending/sending/hold;
- отсутствие hard delete;
- отсутствие PII в preview и событиях;
- ответственного и процедуру проверки личности.