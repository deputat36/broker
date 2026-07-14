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

Применить все десять миграций строго по `docs/supabase-migration-order.md`.

После применения запустить:

```bash
python3 scripts/audit-supabase-readiness.py
```

Проверить наличие:

- `broker_leads`;
- `broker_lead_events`;
- `broker_lead_rate_limits`;
- privacy и retention таблиц;
- всех RPC из специализированных контрактов.

Проверить RLS, отсутствие публичной anon-вставки и отсутствие EXECUTE у `anon` и `authenticated` на служебных RPC.

## 2. Конфигурация Edge Functions

Основная функция требует:

- `SUPABASE_URL`;
- `SUPABASE_SERVICE_ROLE_KEY`;
- точный `ALLOWED_ORIGINS`;
- `ALLOW_ORIGINLESS=false`;
- лимиты размера, времени заполнения и rate limit.

Telegram secrets подключаются только к тестовому чату.

Закрытые функции используют отдельные:

- `NOTIFICATION_ADMIN_TOKEN`;
- `NOTIFICATION_MONITOR_TOKEN`.

Они не должны разрешать CORS.

## 3. CORS preflight

Разрешённый Origin должен получить HTTP `204`, точный `Access-Control-Allow-Origin` и `Vary: Origin`.

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
- notification metadata заполнена корректно.

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

## 8. Ошибки валидации

Проверить отдельно:

- отсутствует имя;
- неправильный телефон;
- отсутствует город или сценарий;
- `consent: false`;
- неправильный `schema_version`;
- неправильный `request_id`;
- слишком короткое время заполнения.

Ожидание: HTTP `422` с безопасными кодами.

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

## 12. Telegram

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

## 13. Ручной retry и health

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

## 14. Retention

Выполнить `docs/supabase-retention-smoke.md`.

Проверяются:

- `broker_lead_retention_preview`;
- `apply_broker_lead_retention`;
- `broker_retention_disabled` до явного включения;
- terminal status whitelist;
- `retention_hold`;
- отсутствие hard delete;
- атомарный откат.

## 15. Privacy и operational guard

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

## 16. Проверка прав

Под ролями `anon` и `authenticated` проверить отказ в прямом чтении, записи и выполнении служебных RPC.

Service_role используется только внутри Edge Functions и доверенного SQL Editor.

## 17. Проверка hybrid

Переходить к этому этапу только после всех source-аудитов и smoke-проверок.

1. Обновить политику под фактически развёрнутый Supabase-канал.
2. Указать проверенный HTTPS endpoint.
3. Перевести режим в `hybrid`.
4. Дождаться успешной Pages-сборки.
5. Отправить тестовую заявку с UTM.
6. Подтвердить Web3Forms email.
7. Подтвердить строку Supabase и внутренние события.
8. Подтвердить Telegram или рабочую очередь.
9. Сверить один request ID во всех каналах.
10. Проверить `/spasibo/` и отказ одного канала.

Deploy закрытых функций не означает автоматическое включение публичного hybrid.

## 18. Откат

При нестабильности вернуть:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

Затем остановить или ротировать secrets проблемной закрытой функции. Миграции и реальные данные оперативно не удалять.

## Критерий приёмки

Backend готов только когда пройдены все десять миграций, source-аудиты, специализированные smoke-тесты, минимальный public response, Web3Forms email, rollback и утверждённые операционные процедуры.