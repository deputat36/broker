# Контракт ограничения операционной обработки заявки

## Текущее состояние

Supabase backend не подключён к публичной форме. Рабочий канал остаётся Web3Forms, `lead_capture.endpoint` пуст.

Файл `supabase/migrations/202607140003_broker_lead_operational_guard.sql` подготавливает единый guard для будущей CRM, Telegram, экспорта и follow-up. Миграция не выполняет действий над существующими заявками при применении.

## Когда заявка блокируется

Операционные действия запрещаются, если выполняется хотя бы одно условие:

- `processing_restricted = true`;
- `retention_hold = true`;
- `anonymized_at is not null`.

Ограничение применяется не только к интерфейсу. Оно закреплено на уровне RPC и триггеров базы данных.

## Единый guard

RPC:

```text
broker_lead_operational_guard(lead_id, request_id, action_code)
```

Принимаются только коды:

- `notification_claim`;
- `notification_complete`;
- `notification_summary`;
- `notification_retry`;
- `crm_read`;
- `crm_update`;
- `export`;
- `follow_up`.

Guard требует точную пару `lead_id + request_id` и возвращает только техническое решение:

- `allowed`;
- `blocker_code`;
- статусы заявки и уведомления;
- счётчик попыток;
- признаки restriction, hold и anonymization.

Имя, телефон, город и содержание заявки guard не возвращает.

Коды блокировки:

- `lead_not_found`;
- `processing_restricted`;
- `retention_hold`;
- `already_anonymized`.

## Уведомления

Следующие RPC повторно проверяют guard:

- `claim_broker_lead_notification`;
- `complete_broker_lead_notification`;
- `broker_lead_notification_summary`;
- `request_broker_lead_notification_retry`.

Ограниченная заявка:

- не переводится в `sending`;
- не формирует текст Telegram;
- не возвращается из `failed` в `pending`;
- не создаёт событие ручного retry;
- исключается из агрегированной рабочей очереди health-monitoring.

Если privacy-запрос начался одновременно с уведомлением, блокировки строк обеспечивают fail-closed поведение: privacy start не начинается при `sending`, а claim не проходит после установки restriction.

## CRM и экспорт

RPC:

```text
broker_lead_operational_snapshot(lead_id, request_id, action_code)
```

Разрешён только для:

- `crm_read`;
- `export`;
- `follow_up`.

Snapshot не возвращает `raw_payload`, spam fingerprint, секреты и внутренние notification error. Ограниченная, удерживаемая или обезличенная заявка snapshot не получает.

Будущие CRM-интеграции и экспорт должны использовать guard/snapshot. Прямое чтение таблицы с `service_role` технически обладает повышенными правами и поэтому запрещается операционной процедурой. Service role нельзя передавать в браузер, пользовательский интерфейс или сторонний клиент.

## Прямые изменения строки

Trigger `broker_leads_guard_restricted_updates` блокирует обычный `UPDATE` restricted, hold и anonymized строк.

Допускаются только два подтверждённых privacy-сценария:

1. verified `anonymize` с очисткой полного белого списка содержательных полей;
2. cancel открытого privacy-запроса с восстановлением прежних `retention_hold` и `processing_restricted` без изменения остальных полей.

Обычная смена статуса, приоритета, комментария, телефона, источника, notification status или qualification запрещена.

## События

Trigger `broker_lead_events_guard_restricted_insert` запрещает обычные события restricted, hold и anonymized заявок.

Разрешены только технические события privacy workflow:

- `privacy_request_started`;
- `privacy_request_verified`;
- `privacy_request_completed`;
- `privacy_request_cancelled`.

Это предотвращает повторную обработку через будущую CRM-ленту или автоматические действия.

## Права

Все guard, snapshot и notification RPC:

- недоступны `PUBLIC`, `anon` и `authenticated`;
- доступны только `service_role`;
- используют фиксированный `search_path`;
- не публикуются в HTML или JavaScript сайта.

Trigger-функции не выдаются даже `service_role` для прямого вызова.

## Граница сторонних каналов

Ограничение в Supabase не удаляет и не отзывает уже доставленный Web3Forms email, Telegram-сообщение, SMS, MAX, ВКонтакте или запись внешней CRM. Для каждого фактически подключённого канала нужна отдельная проверяемая процедура.

## Условие включения

Контур считается готовым только после:

1. применения девяти миграций по порядку;
2. проверки прав функций и триггеров;
3. smoke-теста unrestricted и restricted заявок;
4. проверки privacy apply/cancel после включения триггеров;
5. проверки отсутствия restricted лидов в notification health;
6. утверждения CRM/export-процедуры;
7. подтверждения внешних каналов;
8. сохранения `lead_capture.mode: web3forms` и `endpoint: ""` до общей приёмки hybrid.