# Канонический порядок Supabase-миграций

Этот файл является единственным актуальным списком миграций для нового развёртывания. Разделы ранних smoke-чеклистов, перечисляющие меньшее количество файлов, описывают соответствующий этап разработки и не заменяют этот порядок.

Применять строго последовательно:

1. `202607070001_create_broker_leads.sql` — базовая таблица заявки;
2. `202607130002_broker_leads_v2.sql` — request ID, события и rate limit;
3. `202607130003_broker_lead_preparation.sql` — структурированный контекст подготовки;
4. `202607130004_broker_lead_notification_summary.sql` — защищённая серверная сводка;
5. `202607130005_broker_lead_notification_delivery.sql` — атомарный claim и delivery;
6. `202607130006_broker_lead_notification_manual_retry.sql` — ручной retry и health RPC;
7. `202607140001_broker_lead_retention.sql` — выключенная retention policy;
8. `202607140002_broker_lead_privacy_requests.sql` — индивидуальные privacy-запросы;
9. `202607140003_broker_lead_operational_guard.sql` — блокировка дальнейшей обработки;
10. `202607140004_broker_lead_restricted_delivery_status.sql` — browser-safe `disabled` для restricted duplicate.

## Обязательная проверка

После применения выполнить специализированные smoke-чеклисты в том же порядке, включая:

- `docs/supabase-restricted-delivery-response-smoke.md`;
- `docs/supabase-public-response-smoke.md`.

Затем выполнить:

```bash
python3 scripts/audit-public-lead-response.py
python3 scripts/audit-supabase-readiness.py
```

Агрегирующий аудит должен подтвердить десять миграций, минимальный публичный success response и все специализированные source-аудиты.

## До приёмки

Рабочая конфигурация сайта остаётся:

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

Применение миграций само по себе не включает `hybrid`, Telegram, health endpoint, административный retry, retention automation или публичный Supabase endpoint.