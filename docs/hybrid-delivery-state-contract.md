# Контракт состояния hybrid-доставки

## Назначение

Контракт фиксирует, какой из независимых каналов подтвердил приём одной онлайн-заявки:

- `web3forms_only` — email-канал Web3Forms подтвердил приём, Supabase не подтвердил;
- `supabase_only` — Supabase подтвердил сохранение, Web3Forms не подтвердил;
- `both` — оба канала подтвердили приём.

Это техническое состояние доставки, а не статус обработки клиента, не вероятность одобрения и не подтверждение прочтения заявки Татьяной.

## Текущее состояние сайта

Публичный режим остаётся:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

Поэтому в рабочей конфигурации фактически подтверждается `web3forms_only`. Supabase, receipt-handler и Telegram не развёрнуты и не включены.

## Браузерная координация

`assets/js/application-inputs.js` наблюдает только технические результаты двух запросов с одинаковым `request_id`.

В режиме `hybrid`:

1. Web3Forms и Supabase остаются независимыми задачами основной формы.
2. Отправка Web3Forms может подождать результат Supabase не более 2500 мс.
3. Если Supabase уже завершился, в Web3Forms добавляется подтверждённое поле `delivery_state` со значением `web3forms_only` или `both`.
4. После завершения обеих задач вычисляется итоговое состояние.
5. При `both` браузер отправляет отдельную квитанцию без данных клиента.
6. Ошибка квитанции не меняет успешный результат заявки и не заменяет страницу благодарности.

Если Supabase не успел ответить за 2500 мс, email отправляется без предположения о финальном состоянии. После завершения обеих задач итог всё равно используется для аналитики и receipt-механизма.

## Устойчивость к переходу на страницу подтверждения

После успешной заявки переход на `/spasibo/` начинается через короткую задержку. Чтобы навигация не прервала уже сформированную обезличенную квитанцию, `assets/js/application-delivery-keepalive.js` добавляет `keepalive: true` только запросу с:

- `request_kind = delivery_receipt`;
- `delivery_state = both`.

Адаптер загружается раньше `application-inputs.js` и `application-preparation.js`. Он не меняет Web3Forms, основную Supabase-заявку, payload клиента или общий таймаут формы.

## Supabase-состояние

Миграция `202607140005_broker_lead_delivery_state.sql` добавляет:

- `client_delivery_state`;
- `delivery_state_updated_at`;
- `mark_broker_lead_delivery_both(text)`;
- `broker_lead_delivery_state(uuid, text)`.

Строка `broker_leads` появляется только после успешного Supabase-приёма, поэтому её начальное значение — `supabase_only`.

Разрешён только монотонный переход:

```text
supabase_only → both
```

Понижение `both → supabase_only` запрещено. Restricted, hold и anonymized заявки не изменяются.

## Web3Forms-only

При `web3forms_only` строки `broker_leads` может не быть. Оператор видит заявку в email-канале. Если Supabase завершился до отправки email, письмо получает поле:

```text
delivery_state: web3forms_only
```

Отсутствие Supabase-строки не считается потерей Web3Forms-заявки.

## Обезличенная квитанция

Edge Function `broker-delivery-receipt` принимает только:

```json
{
  "request_kind": "delivery_receipt",
  "request_id": "<UUID или IP-YYYYMMDD-XXXXXXXX>",
  "delivery_state": "both"
}
```

Она не принимает и не хранит:

- имя;
- телефон;
- город;
- ипотечные параметры;
- комментарий;
- tracking;
- qualification;
- `raw_payload`;
- документы.

Для существующей, отсутствующей и restricted-заявки публичный ответ одинаковый — HTTP `204` без тела. Это не раскрывает наличие заявки.

## Доступ оператора

Доверенный CRM-код получает состояние через:

```text
broker_lead_delivery_state(lead_id, request_id)
```

RPC проходит operational guard и недоступен ролям `anon` и `authenticated`.

## Аналитика

Допустимы только фиксированные цели:

- `online_application_delivery_web3forms_only`;
- `online_application_delivery_supabase_only`;
- `online_application_delivery_both`;
- `online_application_delivery_receipt_success`;
- `online_application_delivery_receipt_error`.

В аналитику не передаются `request_id`, телефон, город, текст заявки или сырой ответ сервера.

## Ограничения

- Квитанция `both` является best-effort: её сбой не отменяет уже принятые заявки.
- `keepalive` повышает вероятность завершения запроса при навигации, но не заменяет серверный smoke-тест.
- Если Web3Forms и Supabase подтвердили приём, но receipt-handler недоступен, email остаётся подтверждением обоих каналов, а Supabase может временно показывать `supabase_only`.
- Состояние каналов не показывается клиенту и не меняет `/spasibo/`.
- Миграция и функции сами по себе не включают `hybrid`.
