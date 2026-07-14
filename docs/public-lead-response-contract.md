# Минимальный публичный ответ заявки

## Назначение

Публичная Edge Function принимает заявку, но браузеру не нужны внутренние сведения CRM. Успешный HTTP-ответ подтверждает только факт приёма или идемпотентного повтора и состояние серверного уведомления.

Серверное хранение заявки, qualification, technical priority, внутренний UUID и события не меняются.

## Единый успешный envelope

Новая заявка возвращает HTTP `201`:

```json
{
  "ok": true,
  "success": true,
  "duplicate": false,
  "request_id": "<номер обращения>",
  "notification_status": "sent"
}
```

Повтор существующей заявки возвращает HTTP `200`:

```json
{
  "ok": true,
  "success": true,
  "duplicate": true,
  "request_id": "<тот же номер обращения>",
  "notification_status": "sent"
}
```

Для restricted, hold или anonymized заявки используется тот же envelope с `notification_status: "disabled"`.

Допустимые значения `notification_status`:

- `pending`;
- `sending`;
- `sent`;
- `failed`;
- `disabled`.

## Поля, запрещённые в публичном success response

Браузеру не возвращаются:

- `lead_id` и другие внутренние UUID;
- `crm_status`;
- `technical_priority`;
- `qualification` и score;
- имя, телефон, город и ипотечные вводные;
- tracking, UTM, referrer и User-Agent;
- `raw_payload`;
- признаки privacy, retention и operational guard;
- причины ошибок Telegram и административные blocker codes.

`request_id` сохраняется: его создаёт браузер до отправки, он уже известен пользователю и используется как номер обращения.

## Клиентская совместимость

`assets/js/online-application.js` считает канал успешным по HTTP-статусу и признакам `ok`/`success`. Переход на `/spasibo/`, локальная 24-часовая сводка и аналитика строятся из исходного payload формы, а не из `lead_id`, CRM-статуса или qualification ответа.

Поэтому минимизация не меняет:

- страницу подтверждения;
- Web3Forms;
- резервные SMS, MAX, ВКонтакте и копирование;
- серверную квалификацию и приоритет;
- Telegram и внутреннюю очередь.

## Ошибочные ответы

Ошибочные ответы сохраняют безопасные технические коды, например:

- `origin_not_allowed`;
- `method_not_allowed`;
- `content_type_not_supported`;
- `payload_too_large`;
- `invalid_json`;
- `request_rejected`;
- `rate_limit_exceeded`;
- `backend_migration_required`;
- `lead_storage_failed`.

Они не должны содержать stack trace, SQL-текст, secrets, персональные данные или внутренние строки заявки.

## Граница применения

Контракт относится к будущему Supabase Edge Function. На рабочем сайте сохраняются `mode: "web3forms"` и пустой `endpoint` до общей приёмки backend.