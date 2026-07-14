# Контракт отображения ошибок онлайн-заявки

## Назначение

Интерфейс формы не показывает клиенту сырой `error_code`, SQLSTATE, текст исключения или внутренние сведения Supabase. Серверный allowlist-код переводится в понятное действие, а безопасный `request_id` используется как технический номер для обращения в поддержку.

Контур подготовлен для будущего Supabase endpoint. Пока рабочий режим остаётся `web3forms`, а `endpoint` пуст.

## Источник данных

Модуль внутри `assets/js/application-inputs.js` выполняется до `assets/js/online-application.js` и наблюдает только JSON-ответы со структурой:

```json
{
  "ok": false,
  "success": false,
  "error_code": "validation_failed",
  "request_id": "UUID или IP-идентификатор"
}
```

Ответы Web3Forms без `error_code` не изменяются.

## Категории интерфейса

Публичные коды объединяются в пять стабильных категорий:

- `validation` — `validation_failed`;
- `rate_limit` — `rate_limit_exceeded`;
- `rejected` — `request_rejected`;
- `backend` — `backend_unavailable`, `backend_migration_required`, `lead_storage_failed`;
- `request` — `origin_not_allowed`, `method_not_allowed`, `content_type_not_supported`, `payload_too_large`, `invalid_json`.

Сетевая ошибка без JSON получает отдельную локальную категорию `network`.

Клиенту не показывается исходный `error_code`. Атрибут `data-error-category` содержит только одну из безопасных категорий.

## Технический номер

Для интерфейса принимаются только:

- UUID;
- fallback вида `IP-YYYYMMDD-XXXXXXXX`.

При ответе сервера используется его correlation `request_id`. При таймауте или сетевой ошибке используется request ID, уже созданный формой.

Технический номер:

- не содержит телефон, имя или текст заявки;
- не сохраняется модулем ошибок в `localStorage` или `sessionStorage`;
- существует только в памяти страницы и в уже подготовленном тексте заявки;
- сбрасывается перед новой попыткой отправки.

## Сообщение клиенту

Ошибка должна содержать:

1. понятное описание следующего действия;
2. технический номер, если он валиден;
3. напоминание, что готовый текст не потерян;
4. резервные способы: SMS, MAX, ВКонтакте или ручное копирование.

Для `rate_limit_exceeded` разрешено показать приблизительное число минут из `retry_after_seconds`. Значение принимается только в диапазоне от 1 секунды до 24 часов.

## Hybrid

Если Web3Forms успешно принял заявку, а будущий Supabase endpoint вернул ошибку, общий `Promise.allSettled` сохраняет успешный результат. Клиент переходит на `/spasibo/`, потому что хотя бы один рабочий канал принял заявку.

Ошибка дополнительного endpoint в этом случае может попасть в аналитику, но не должна заменять успешное сообщение клиенту.

## Аналитика

Используются только фиксированные цели без request ID и персональных данных:

- `online_application_endpoint_error`;
- `online_application_endpoint_error_validation`;
- `online_application_endpoint_error_rate_limit`;
- `online_application_endpoint_error_rejected`;
- `online_application_endpoint_error_backend`;
- `online_application_endpoint_error_request`.

Сырой `error_code`, телефон, город, сценарий и технический номер в Метрику не передаются.

## Запрещённое поведение

Нельзя:

- показывать пользователю SQLSTATE, stack trace или текст PostgreSQL;
- вставлять сырой `error_code` в сообщение;
- сохранять ошибку или request ID в отдельное локальное хранилище;
- отправлять request ID в аналитику;
- скрывать резервные каналы;
- считать ошибку дополнительного endpoint провалом всей hybrid-отправки, если Web3Forms уже успешен;
- перехватывать ответы, не содержащие одновременно `ok: false`, `success: false` и allowlist `error_code`.
