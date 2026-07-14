# Smoke-тест состояния hybrid-доставки

## Предусловия

1. Применены все 11 миграций по `docs/supabase-migration-order.md`.
2. Развёрнуты `broker-public-lead` и `broker-delivery-receipt`.
3. Для обеих функций проверен точный `ALLOWED_ORIGINS`.
4. В тестовой среде включён `hybrid`; рабочая конфигурация сайта до приёмки остаётся `web3forms` с пустым endpoint.
5. Используются только тестовые имя, телефон и email-канал.

## 1. Проверка миграции

Подтвердить наличие:

- `broker_leads.client_delivery_state`;
- `broker_leads.delivery_state_updated_at`;
- constraint только для `supabase_only` и `both`;
- RPC `mark_broker_lead_delivery_both`;
- RPC `broker_lead_delivery_state`;
- отсутствия EXECUTE у `anon` и `authenticated`.

Новая Supabase-строка должна получать `supabase_only` по умолчанию.

## 2. Web3Forms-only

Отключить или намеренно сломать тестовый Supabase endpoint, оставив Web3Forms рабочим.

Ожидание:

- клиент получает обычное успешное подтверждение;
- открывается неизменённая `/spasibo/`;
- email приходит один раз;
- Supabase-строка не создаётся;
- итоговая аналитическая категория — `web3forms_only`;
- если Supabase успел вернуть отказ до отправки email, поле `delivery_state` в письме равно `web3forms_only`;
- receipt-handler не вызывается.

## 3. Supabase-only

Отключить тестовый Web3Forms-канал, оставив Supabase рабочим.

Ожидание:

- создаётся ровно одна строка `broker_leads`;
- `client_delivery_state = 'supabase_only'`;
- legacy-поле `delivery_channel` может оставаться `supabase`; точное состояние каналов хранится в `client_delivery_state`;
- email не приходит;
- клиент всё равно получает успешное подтверждение, потому что один канал принят;
- итоговая аналитическая категория — `supabase_only`;
- квитанция `both` не отправляется.

## 4. Оба канала

Включить оба тестовых канала.

Ожидание:

- Web3Forms email приходит один раз;
- Supabase создаёт одну строку;
- после квитанции `client_delivery_state = 'both'`;
- `delivery_channel = 'both'`;
- создаётся не более одного события `delivery_state_updated`;
- повторная квитанция остаётся идемпотентной;
- аналитическая категория — `both`;
- фиксируется `online_application_delivery_receipt_success`;
- клиент видит обычную страницу благодарности без названий каналов.

## 5. Медленный Supabase

Задержать ответ основной Edge Function более чем на 2500 мс, но меньше общего таймаута формы.

Ожидание:

- Web3Forms не блокируется дольше 2500 мс;
- email может уйти без поля `delivery_state`;
- после завершения обеих задач браузер всё равно вычисляет итог;
- при двух успешных каналах отправляется квитанция `both`;
- клиенту не показывается промежуточный технический статус.

## 6. Ошибка receipt-handler

Оба основных канала должны успешно принять заявку, а receipt-handler вернуть ошибку или быть недоступным.

Ожидание:

- заявка считается успешно отправленной;
- `/spasibo/` открывается;
- Web3Forms email и Supabase-строка сохраняются;
- клиенту не показывается ошибка квитанции;
- фиксируется только `online_application_delivery_receipt_error`;
- Supabase может временно остаться в `supabase_only` до ручной сверки.

## 7. Restricted, hold и anonymized

Для тестовой Supabase-строки по очереди установить:

- `processing_restricted = true`;
- `retention_hold = true`;
- `anonymized_at`.

Отправить квитанцию `both`.

Ожидание:

- HTTP `204` без тела;
- состояние строки не меняется;
- новое событие не создаётся;
- наличие и причина блокировки не раскрываются браузеру.

## 8. Отсутствующая заявка

Отправить валидную квитанцию с неизвестным request ID.

Ожидание:

- HTTP `204` без тела;
- строка и событие не создаются;
- ответ не отличается от существующей заявки.

## 9. Невалидная квитанция

Проверить:

- неизвестный `request_kind`;
- состояние `web3forms_only` или `supabase_only` вместо `both`;
- неправильный request ID;
- неподдерживаемый Content-Type;
- тело больше 4096 байт;
- запрещённый Origin.

Ожидание: безопасный error envelope без внутренних SQL-кодов и персональных данных.

## 10. Права

Под `anon` и `authenticated` прямой вызов RPC должен завершаться отказом.

Receipt Edge Function использует service role только внутри серверного кода. Service-role key отсутствует в HTML, JavaScript, `_config.yml` и публичных ответах.

## 11. Аналитика

Проверить пять фиксированных целей. В параметрах Метрики не должно быть:

- request ID;
- телефона;
- города;
- сценария;
- текста заявки;
- server response body.

## 12. Откат

До завершения проверки вернуть:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

Отключить или удалить test receipt function URL из внешней тестовой конфигурации. Миграции и тестовые строки не удалять без отдельного решения.
