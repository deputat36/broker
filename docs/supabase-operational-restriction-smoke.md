# Smoke: operational guard для restricted заявок

## Предварительные условия

- подтверждён отдельный тестовый Supabase-проект;
- применены девять миграций по порядку;
- публичный сайт остаётся в режиме `web3forms`;
- `lead_capture.endpoint` остаётся пустым;
- используются только явно тестовые заявки и тестовый Telegram-чат.

## Проверка прав

Под ролями `anon` и `authenticated` должны быть недоступны:

- `broker_lead_operational_guard`;
- `broker_lead_operational_snapshot`;
- `broker_lead_notification_summary`;
- `claim_broker_lead_notification`;
- `complete_broker_lead_notification`;
- `request_broker_lead_notification_retry`.

Trigger-функции не должны быть доступны для прямого вызова даже через `service_role`.

## Тестовые заявки

Создать минимум четыре тестовые строки:

1. обычная unrestricted заявка со статусом уведомления `failed`;
2. заявка для privacy action `restrict_processing`;
3. заявка для privacy action `anonymize`;
4. заявка для проверки cancel.

Для каждой сохранить точную пару `lead_id + request_id`. Не использовать реальные данные клиентов.

## Unrestricted guard

Для первой заявки выполнить guard с кодами:

- `notification_retry`;
- `crm_read`;
- `crm_update`;
- `export`;
- `follow_up`.

Ожидается:

- `allowed = true`;
- `blocker_code is null`;
- snapshot возвращает ограниченную структуру;
- snapshot не содержит `raw_payload`, fingerprint, service-role key или notification error.

Неизвестный `action_code` должен завершиться ошибкой `broker_operational_action_invalid`.

Неправильная пара ID должна вернуть `lead_not_found` без имени, телефона и содержимого.

## Restrict processing

Для второй заявки пройти:

1. preview privacy-запроса;
2. start `restrict_processing`;
3. verify;
4. apply.

Проверить:

- `processing_restricted = true`;
- `retention_hold = true`;
- guard возвращает `allowed = false` и `processing_restricted`;
- snapshot для `crm_read`, `export` и `follow_up` блокируется;
- прямой `UPDATE status`, `technical_priority` или `comment` завершается ошибкой `broker_lead_processing_restricted`;
- вставка обычного события завершается ошибкой `broker_lead_processing_restricted`;
- privacy events остаются разрешены.

## Уведомления restricted заявки

Для restricted заявки проверить:

- claim не переводит запись в `sending`;
- notification summary не возвращает текст заявки;
- manual retry не переводит `failed` в `pending`;
- notification attempt count не увеличивается;
- Telegram-сообщение не отправляется;
- notification health не считает эту строку в `failed`, `pending` или `sending` очереди.

Повторный вызов публичной Edge Function с тем же request ID не должен восстанавливать уведомление restricted заявки.

## Privacy anonymize после установки триггера

Для третьей заявки выполнить verified `anonymize` через privacy RPC.

Проверить:

- privacy apply не блокируется operational trigger;
- строка `broker_leads` физически сохранена;
- контактные, ипотечные, tracking, preparation и raw payload поля очищены;
- `processing_restricted = true`;
- `anonymized_at is not null`;
- guard возвращает `already_anonymized`;
- обычный update и обычное событие блокируются;
- событие `privacy_request_completed` записывается.

Попытка изменить технический статус обезличенной строки должна завершиться `broker_lead_already_anonymized`.

## Privacy cancel после установки триггера

Для четвёртой заявки:

1. запомнить прежние `retention_hold` и `processing_restricted`;
2. выполнить start privacy-запроса;
3. выполнить cancel с разрешённым reason code.

Проверить:

- cancel не блокируется operational trigger;
- восстановлены только прежние два флага;
- остальные поля не изменились;
- событие `privacy_request_cancelled` записано;
- после восстановления unrestricted состояния guard снова разрешает действия, если прежние флаги были false.

## Проверка обходов

Должны блокироваться:

- прямой update restricted строки через service role;
- изменение notification status вручную;
- добавление `notification_retry_requested` вручную;
- экспорт через operational snapshot;
- получение Telegram summary;
- попытка cancel с изменением дополнительных полей;
- попытка anonymize без verified privacy request;
- попытка anonymize с неполной очисткой обязательных полей.

## Атомарность

Спровоцировать ошибку в privacy apply в тестовой транзакции. Проверить, что:

- часть полей не была очищена отдельно от остальных;
- privacy request не стал `completed`;
- обычные события не записались;
- restriction и hold сохранились.

## Внешние каналы

Зафиксировать отдельно: SQL guard не удаляет уже полученные Web3Forms email, Telegram, SMS, MAX, ВКонтакте или записи внешней CRM. Smoke каждого реально подключённого канала проводится отдельной процедурой.

## Завершение

После теста:

- удалить только тестовые строки по утверждённой тестовой процедуре;
- не включать Cron;
- не публиковать service role;
- не переключать сайт в `hybrid`;
- сохранить агрегированный результат без персональных данных в issue приёмки;
- подтвердить `mode: web3forms` и пустой `endpoint`.