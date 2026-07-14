# Контракт индивидуальных запросов на данные

## Назначение

Контур предназначен для точечной обработки просьбы клиента ограничить дальнейшую обработку либо обезличить одну ранее сохранённую заявку.

Он не является публичной формой удаления, не вызывается из браузера посетителя и не выполняет поиск по телефону, имени или городу.

До отдельной приёмки Supabase остаётся выключенным:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

## Состав

Восьмая миграция:

`supabase/migrations/202607140002_broker_lead_privacy_requests.sql`

Она применяется после семи предыдущих миграций backend и retention.

Добавляются:

- поле `processing_restricted` в `broker_leads`;
- таблица `broker_lead_privacy_requests`;
- preview RPC;
- start RPC;
- verification RPC;
- apply RPC;
- cancel RPC.

Все таблицы и функции закрыты от `public`, `anon` и `authenticated`. Доступ предоставляется только `service_role`.

## Идентификация заявки

Процесс использует только точную пару:

- `lead_id`;
- `request_id`.

Поиск по телефону, имени, городу, email, тексту комментария или рекламному источнику намеренно отсутствует.

Перед запуском оператор обязан проверить личность клиента вне публичной формы. В базе не сохраняются паспорт, фотографии документов, контрольные вопросы или свободный комментарий оператора.

## Действия

Поддерживаются только два действия:

- `restrict_processing` — сохранить запись, но оставить `processing_restricted = true` и `retention_hold = true`;
- `anonymize` — необратимо удалить контактные и содержательные поля одной заявки.

Физическое удаление строки `broker_leads` не выполняется.

## Состояния запроса

```text
pending_verification → verified → completed
pending_verification | verified → cancelled
```

Одновременно для одной заявки допускается только один открытый запрос.

## Preview

`broker_lead_privacy_request_preview(uuid, text)` возвращает только:

- найден ли лид;
- можно ли начать процесс;
- статус лида и уведомления;
- наличие retention hold;
- наличие ограничения обработки;
- факт предыдущего обезличивания;
- число открытых запросов;
- технический blocker code.

Preview не возвращает имя, телефон, город, текст заявки, URL, UTM или `raw_payload`.

## Start

`start_broker_lead_privacy_request(...)` требует точную строку:

`START_BROKER_PRIVACY_REQUEST`

Start блокируется, если:

- лид не найден по точной паре ID;
- заявка уже обезличена;
- существует другой retention hold;
- уведомление находится в `pending` или `sending`;
- для лида уже есть открытый privacy-запрос;
- action code неизвестен.

После успешного start:

- `retention_hold = true`;
- `processing_restricted = true`;
- создаётся `privacy_request_started`;
- исходные значения hold/restriction сохраняются для безопасной отмены.

## Проверка личности

`verify_broker_lead_privacy_request(...)` требует точную строку:

`VERIFY_BROKER_PRIVACY_REQUEST`

Разрешены только методы:

- `same_contact_channel`;
- `callback_verified`;
- `documented_internal_check`.

Код означает, что уполномоченный оператор выполнил проверку вне публичной формы. Код не является автоматическим доказательством личности и не заменяет утверждённую внутреннюю процедуру.

## Применение

`apply_broker_lead_privacy_request(...)` требует точную строку:

`APPLY_BROKER_PRIVACY_REQUEST`

Применение разрешено только для `verified` и повторно сверяет:

- точную пару lead/request ID;
- `retention_hold = true`;
- `processing_restricted = true`;
- отсутствие `pending` и `sending` уведомления.

### Restrict processing

Запись сохраняется. Hold и processing restriction остаются активными до отдельного осознанного решения.

### Anonymize

Очищаются:

- имя, телефон и город;
- комментарий и ипотечные вводные;
- UTM, URL, referrer и User-Agent;
- tracking, qualification, spam check и raw payload;
- preparation и оставшиеся вопросы;
- другие содержательные поля.

Сохраняются только технические идентификаторы, статусы, даты, счётчики и отметка `manual_privacy_request`.

`processing_restricted` остаётся включённым, а retention hold снимается, чтобы старые технические события позднее могли быть очищены утверждённой retention-политикой.

## Отмена

`cancel_broker_lead_privacy_request(...)` требует точную строку:

`CANCEL_BROKER_PRIVACY_REQUEST`

Разрешены только причины:

- `identity_not_verified`;
- `duplicate_request`;
- `request_withdrawn`.

При отмене восстанавливаются предыдущие значения `retention_hold` и `processing_restricted`. Выполненный или уже отменённый запрос повторно отменить нельзя.

## Журналирование

Создаются технические события:

- `privacy_request_started`;
- `privacy_request_verified`;
- `privacy_request_completed`;
- `privacy_request_cancelled`.

Payload может содержать только action code, verification method code или cancellation reason code. Телефон, имя, текст заявки, свободный комментарий и документы в события не записываются.

## Граница сторонних каналов

Обезличивание в Supabase не удаляет:

- Web3Forms email;
- SMS;
- сообщения MAX;
- переписку ВКонтакте;
- Telegram-сообщение, уже доставленное оператору;
- сведения, переданные в CRM или другому участнику после отдельного согласования.

Для каждого фактически используемого внешнего канала нужна отдельная процедура удаления или ограничения доступа.

## Активационный барьер

Рабочее использование разрешается только после:

1. применения восьми миграций по порядку;
2. проверки RLS и прав функций;
3. утверждения процедуры проверки личности;
4. теста точной идентификации lead/request ID;
5. проверки блокировок pending/sending и existing hold;
6. проверки start/verify/apply/cancel;
7. подтверждения полного списка очищаемых полей;
8. проверки отсутствия персональных данных в preview и событиях;
9. назначения ответственного;
10. обновления публичной политики перед фактическим серверным хранением.

Контур не включает публичный endpoint, автоматическую обработку запросов, поиск по телефону или переключение сайта в `hybrid`.