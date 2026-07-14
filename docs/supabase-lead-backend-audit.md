# Аудит Supabase backend для онлайн-заявок

Дата актуализации: 14 июля 2026 года.

## Итоговый статус

Рабочий приём заявок обеспечивается Web3Forms. Supabase backend подготовлен в репозитории как будущий второй канал, но не введён в эксплуатацию.

```yaml
lead_capture:
  mode: "web3forms"
  endpoint: ""
```

Это означает:

- форма работает независимо от Supabase;
- Web3Forms отправляет email-копию;
- после успешного ответа открывается `/spasibo/`;
- SMS, MAX, ВКонтакте, Web Share и копирование остаются резервными способами;
- Supabase Edge Function не вызывается рабочим сайтом;
- наличие исходников не подтверждает миграции, deploy, secrets или Telegram.

## Проверенный комплект

Канонический порядок содержит десять миграций и хранится в `docs/supabase-migration-order.md`.

Проверены исходники:

- публичной `broker-public-lead`;
- закрытого notification retry;
- закрытого notification health;
- preparation-контекста;
- notification summary и атомарной доставки;
- retention;
- индивидуальных privacy-запросов;
- operational guard;
- browser-safe restricted status;
- минимального public response.

Проверки выполняют специализированные скрипты и агрегатор `scripts/audit-supabase-readiness.py`.

## Контракт формы

Edge Function принимает `schema_version: 1` с вложенными объектами:

```json
{
  "schema_version": 1,
  "request_id": "UUID",
  "form_version": "2",
  "client": {},
  "mortgage": {},
  "tracking": {},
  "qualification": {},
  "preparation": {},
  "spam_check": {},
  "personal_data_consent": "yes",
  "consent": true
}
```

Preparation необязателен. Паспорт, СНИЛС, банковские реквизиты, коды подтверждения, фотографии документов и полный кредитный отчёт запрещены.

## Идемпотентность

`request_id` создаётся браузером до отправки и защищён уникальным индексом.

Edge Function:

- ищет существующую строку до вставки;
- обрабатывает конкурентную ошибку уникальности;
- возвращает `duplicate: true` без создания второй записи;
- может завершить только ожидающее или зависшее уведомление обычной заявки;
- не запускает уведомление restricted, hold или anonymized заявки.

Внутренний UUID заявки не возвращается браузеру.

## Минимальный публичный response

Новая, обычная duplicate и restricted duplicate заявки используют единый envelope:

```json
{
  "ok": true,
  "success": true,
  "duplicate": false,
  "request_id": "<номер обращения>",
  "notification_status": "disabled"
}
```

Браузер не получает:

- внутренний `lead_id`;
- CRM status;
- `technical_priority`;
- `qualification`;
- контактные и ипотечные сведения;
- tracking и `raw_payload`;
- privacy и retention flags.

Внутренние поля сохраняются в защищённой серверной записи. Контракт проверяется `scripts/audit-public-lead-response.py`.

## Серверный rate limit

`consume_broker_lead_rate_limit` атомарно считает запросы.

Fingerprint строится из:

- серверно определённого IP;
- User-Agent;
- последних четырёх цифр нормализованного телефона.

Таблица не хранит исходный IP, полный телефон или payload. При отсутствии миграции или RPC функция возвращает `backend_migration_required` и прекращает обработку.

## CORS и входной запрос

Подготовлены:

- точное сравнение Origin;
- запрет `startsWith`;
- отдельный `OPTIONS`;
- запрет неизвестного и originless-запроса по умолчанию;
- JSON Content-Type;
- ограничение размера;
- проверка объектной структуры;
- безопасные ошибки без stack trace и secrets.

## Серверная валидация

Функция повторно проверяет:

- schema и request ID;
- имя, российский телефон и город;
- ипотечный сценарий;
- согласие;
- honeypot и время заполнения;
- длины текстов;
- URL;
- qualification;
- preparation whitelist.

Клиентская маска телефона не считается доверенным источником.

## Хранение и события

Серверная строка может хранить:

- контактные и ипотечные данные;
- tracking, qualification и spam_check;
- защищённый `raw_payload`;
- preparation;
- технический приоритет;
- notification metadata;
- privacy, retention и operational flags.

События содержат техническую историю без повторного хранения полного payload и текста Telegram-сообщения.

## Telegram и очередь

Основная функция использует:

- атомарный `claim_broker_lead_notification`;
- защищённую `broker_lead_notification_summary`;
- `complete_broker_lead_notification`.

Подготовлены:

- ручной retry только для `failed`;
- reason code whitelist;
- защита от параллельной отправки;
- восстановление зависшего `sending`;
- обезличенный health endpoint;
- операционный runbook.

Restricted, hold и anonymized заявки исключаются из уведомлений и health-очереди.

## Retention и privacy

Retention выключен по умолчанию и требует preview, terminal status, отсутствия hold и точного подтверждения. Лиды обезличиваются, а не удаляются физически.

Privacy workflow использует точную пару `lead_id + request_id` и этапы preview/start/verify/apply/cancel. Поиск по телефону и хранение документов проверки личности не предусмотрены.

`processing_restricted` блокирует уведомления, CRM update, follow-up, экспорт и обычные события.

## Source-аудиты

Workflow до Jekyll-сборки запускает:

- базовый backend audit;
- function security config;
- notification retry;
- notification health;
- retention;
- privacy requests;
- operational guard;
- restricted delivery response;
- минимальный public response;
- aggregate Supabase readiness.

После source-проверок выполняются сборка сайта и HTML/SEO/UX-аудиты.

## Что пока не подтверждено

Репозиторий не подтверждает:

- целевой Supabase-проект;
- фактическое применение всех миграций;
- deploy Edge Functions;
- production secrets и Origin;
- запись в таблицы;
- Telegram-получателя;
- роли реальных операторов;
- утверждённые сроки хранения;
- фактическое выполнение privacy-процедур;
- полный smoke и rollback.

## Безопасная последовательность запуска

1. Подтвердить целевой проект.
2. Применить десять миграций по каноническому порядку.
3. Запустить все source-аудиты.
4. Проверить таблицы, RLS, RPC и права.
5. Развернуть функции в тестовом окружении.
6. Настроить secrets и точные Origin.
7. Выполнить общий и специализированные smoke-тесты.
8. Проверить минимальный public response и `/spasibo/`.
9. Проверить Web3Forms, строку Supabase и Telegram на одном request ID.
10. Проверить retry, health, retention, privacy и operational guard.
11. Утвердить ответственных, сроки и rollback.
12. Обновить публичную политику под фактически развёрнутый канал.
13. Только после этого указать endpoint и рассматривать `hybrid`.

## Решение на текущем этапе

- Web3Forms остаётся рабочим каналом.
- Supabase считается подготовленным только на уровне исходников.
- `lead_capture.endpoint` остаётся пустым.
- `hybrid` не включается до полной приёмки.
- Issue №7 остаётся открытым до deploy и smoke.
- Issue №8 остаётся открытым до подтверждения email-получателя Web3Forms.