# Smoke-тест Supabase backend

## Назначение

Проверка подтверждает, что Supabase может безопасно работать вторым каналом рядом с Web3Forms. Это обзорный smoke-план; детальные сценарии выполняются по специализированным документам.

До полной приёмки сайт сохраняет:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

Тесты выполняются только в подтверждённом тестовом проекте и с явно тестовыми данными.

## 1. Проверка миграций

Применить все 11 миграций строго по `docs/supabase-migration-order.md`.

После применения запустить:

```bash
python3 scripts/audit-supabase-readiness.py
```

Проверить наличие:

- `broker_leads`;
- `broker_lead_events`;
- `broker_lead_rate_limits`;
- privacy и retention таблиц;
- `client_delivery_state`;
- всех RPC из специализированных контрактов.

Проверить RLS, отсутствие публичной anon-вставки и отсутствие EXECUTE у `anon` и `authenticated` на служебных RPC.

## 2. Конфигурация Edge Functions

Основная и receipt-функции требуют:

- `SUPABASE_URL`;
- `SUPABASE_SERVICE_ROLE_KEY`;
- точный `ALLOWED_ORIGINS`;
- `ALLOW_ORIGINLESS=false`;
- ограничения размера и метода.

Основная функция дополнительно использует время заполнения и rate limit.

Telegram secrets подключаются только к тестовому чату.

Закрытые функции используют отдельные:

- `NOTIFICATION_ADMIN_TOKEN`;
- `NOTIFICATION_MONITOR_TOKEN`.

Retry и health не должны разрешать CORS. `broker-public-lead` и `broker-delivery-receipt` разрешают только точные подтверждённые Origin.

## 3. CORS preflight

Для `broker-public-lead` и `broker-delivery-receipt` разрешённый Origin должен получить HTTP `204`, точный `Access-Control-Allow-Origin` и `Vary: Origin`.

Запрещённый Origin должен получить HTTP `403` без разрешающего заголовка.

Запрос без Origin при `ALLOW_ORIGINLESS=false` отклоняется.

## 4. Валидный payload

Отправить заявку со следующими признаками:

- `schema_version: 1`;
- уникальный `request_id`;
- корректный российский телефон;
- город и сценарий;
- согласие;
- пустой honeypot;
- `form_fill_ms` больше минимального значения;
- при необходимости корректный `preparation`.

Ожидание: HTTP `201` и минимальный публичный ответ:

```json
{
  "ok": true,
  "success": true,
  "duplicate": false,
  "request_id": "<исходный request_id>",
  "notification_status": "disabled"
}
```

Фактический notification status зависит от тестовой конфигурации Telegram.

Ответ не содержит `lead_id`, CRM status, `technical_priority` или `qualification`.

## 5. Проверка записи

В доверенном SQL Editor подтвердить:

- создана одна строка;
- внутренний UUID существует;
- телефон нормализован;
- qualification и technical priority сохранены;
- preparation очищен whitelist-механизмом;
- `raw_payload` доступен только доверенному серверному коду;
- User-Agent получен из HTTP-заголовка;
- notification metadata заполнена корректно;
- `client_delivery_state = 'supabase_only'` до receipt-квитанции.

Минимизация HTTP-ответа не удаляет внутренние серверные поля.

## 6. Идемпотентность

Повторить POST с тем же `request_id`.

Ожидание: HTTP `200`, `duplicate: true`, тот же request ID и тот же пятиключевой envelope.

Вторая строка не создаётся. Второе обычное Telegram-сообщение после завершённого `sent` не отправляется.

Restricted, hold и anonymized сценарии проверяются по `docs/supabase-restricted-delivery-response-smoke.md`.

## 7. Минимальный public response

Выполнить `docs/supabase-public-response-smoke.md`.

Проверяются:

- новая заявка;
- обычный duplicate;
- restricted duplicate;
- отсутствие внутренних UUID, CRM status, priority и qualification;
- совместимость страницы `/spasibo/`;
- сохранение внутренних данных в базе.

## 8. Безопасные ошибки

Выполнить `docs/supabase-public-error-smoke.md` и `docs/application-error-ui-smoke.md`.

Проверить:

- server error envelope;
- correlation request ID;
- отсутствие SQLSTATE и внутренних полей;
- понятное сообщение клиенту;
- сохранение резервных каналов;
- отсутствие request ID в аналитике.

## 9. Spam-блок

Honeypot или `likely_bot: true` должны вернуть HTTP `202`, `success: false` и `request_rejected` без записи заявки.

## 10. Content-Type, JSON и размер

Проверить:

- неподдерживаемый Content-Type — HTTP `415`;
- некорректный JSON — HTTP `400`;
- oversized payload — HTTP `413`;
- отсутствие необходимых миграций — безопасный `backend_migration_required`.

## 11. Rate limit

В тестовой среде временно снизить лимит.

Последний запрос должен получить HTTP `429` и `rate_limit_exceeded`.

Проверить, что таблица лимитов не хранит исходный IP, полный телефон или payload. Очистку проверить через `purge_broker_lead_rate_limits`.

## 12. Hybrid delivery state

Выполнить `docs/hybrid-delivery-state-smoke.md`.

Проверяются:

- `web3forms_only`;
- `supabase_only`;
- `both`;
- ожидание Supabase не более 2500 мс перед Web3Forms;
- обезличенная receipt-квитанция;
- монотонный переход `supabase_only → both`;
- неизменная `/spasibo/`;
- отсутствие PII и request ID в аналитике;
- отказ изменения restricted, hold и anonymized строки.

## 13. Telegram

Выполнить `docs/supabase-notification-smoke.md`.

Проверяются:

- `broker_lead_notification_summary`;
- первый и повторный `claim_broker_lead_notification`;
- `complete_broker_lead_notification`;
- `sending`, `sent`, `failed`;
- зависшее sending;
- duplicate request ID;
- остаточное аварийное окно Telegram.

Неизвестный UUID должен вернуть `broker_lead_not_found` только доверенному серверному вызову.

## 14. Ручной retry и health

Выполнить:

- `docs/supabase-notification-retry-smoke.md`;
- `docs/supabase-notification-health-smoke.md`.

Проверяются:

- `request_broker_lead_notification_retry`;
- `broker_lead_notification_queue_health`;
- failed-only переход;
- `retry_not_allowed`;
- reason code whitelist;
- отсутствие CORS;
- обезличенные агрегаты очереди;
- отсутствие массового retry.

## 15. Retention

Выполнить `docs/supabase-retention-smoke.md`.

Проверяются:

- `broker_lead_retention_preview`;
- `apply_broker_lead_retention`;
- `broker_retention_disabled` до явного включения;
- terminal status whitelist;
- `retention_hold`;
- отсутствие hard delete;
- атомарный откат.

## 16. Privacy и operational guard

Выполнить:

- `docs/supabase-privacy-request-smoke.md`;
- `docs/supabase-operational-restriction-smoke.md`.

Проверяются:

- точная пара `lead_id + request_id`;
- preview/start/verify/apply/cancel;
- блокировка pending и sending;
- restricted CRM update, export, follow-up и события;
- разрешённые privacy-исключения;
- отсутствие поиска по телефону.

## 17. Проверка прав

Под ролями `anon` и `authenticated` проверить отказ в прямом чтении, записи и выполнении служебных RPC.

Service_role используется только внутри Edge Functions и доверенного SQL Editor.

## 18. Проверка hybrid

Переходить к этому этапу только после всех source-аудитов и smoke-проверок.

1. Обновить политику под фактически развёрнутый Supabase-канал.
2. Указать проверенный HTTPS endpoint `broker-public-lead`.
3. Развернуть `broker-delivery-receipt` с тем же точным Origin.
4. Перевести режим в `hybrid`.
5. Дождаться успешной Pages-сборки.
6. Отправить тестовую заявку с UTM.
7. Подтвердить Web3Forms email.
8. Подтвердить строку Supabase и внутренние события.
9. Подтвердить состояние каналов и receipt.
10. Подтвердить Telegram или рабочую очередь.
11. Сверить один request ID во всех каналах.
12. Проверить `/spasibo/` и отказ одного канала.

Deploy закрытых функций не означает автоматическое включение публичного hybrid.

## 19. Откат

При нестабильности вернуть:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

Затем остановить или ротировать secrets проблемной функции. Миграции и реальные данные оперативно не удалять.

## Критерий приёмки

Backend готов только когда пройдены все 11 миграций, source-аудиты, специализированные smoke-тесты, минимальный public response, безопасные ошибки, три состояния доставки, Web3Forms email, rollback и утверждённые операционные процедуры.
