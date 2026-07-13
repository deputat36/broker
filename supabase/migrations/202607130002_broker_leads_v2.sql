-- Backend v2 для онлайн-заявок ипотечного брокера.
--
-- Миграция расширяет существующую public.broker_leads без удаления legacy-полей,
-- добавляет идемпотентность по request_id, историю событий и атомарный rate limit.
-- Применять только к подтверждённому Supabase-проекту через штатный migration workflow.

create extension if not exists pgcrypto;

alter table public.broker_leads
  add column if not exists request_id text,
  add column if not exists schema_version smallint,
  add column if not exists form_version text,
  add column if not exists submitted_at timestamptz,
  add column if not exists form_fill_ms integer,
  add column if not exists phone_normalized text,
  add column if not exists preferred_contact text,
  add column if not exists scenario text,
  add column if not exists object_type text,
  add column if not exists object_price_text text,
  add column if not exists down_payment_text text,
  add column if not exists income_type text,
  add column if not exists bank_history text,
  add column if not exists page_url text,
  add column if not exists referrer text,
  add column if not exists tracking jsonb not null default '{}'::jsonb,
  add column if not exists qualification jsonb not null default '{}'::jsonb,
  add column if not exists spam_check jsonb not null default '{}'::jsonb,
  add column if not exists raw_payload jsonb not null default '{}'::jsonb,
  add column if not exists personal_data_consent boolean not null default false,
  add column if not exists technical_priority text,
  add column if not exists delivery_channel text not null default 'supabase',
  add column if not exists notification_status text not null default 'pending';

create unique index if not exists broker_leads_request_id_uidx
  on public.broker_leads (request_id)
  where request_id is not null;

create index if not exists broker_leads_phone_normalized_idx
  on public.broker_leads (phone_normalized);

create index if not exists broker_leads_submitted_at_idx
  on public.broker_leads (submitted_at desc)
  where submitted_at is not null;

create index if not exists broker_leads_tracking_gin_idx
  on public.broker_leads using gin (tracking);

create index if not exists broker_leads_qualification_gin_idx
  on public.broker_leads using gin (qualification);

create index if not exists broker_leads_spam_check_gin_idx
  on public.broker_leads using gin (spam_check);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'broker_leads_schema_version_check'
      and conrelid = 'public.broker_leads'::regclass
  ) then
    alter table public.broker_leads
      add constraint broker_leads_schema_version_check
      check (schema_version is null or schema_version = 1);
  end if;

  if not exists (
    select 1
    from pg_constraint
    where conname = 'broker_leads_notification_status_check'
      and conrelid = 'public.broker_leads'::regclass
  ) then
    alter table public.broker_leads
      add constraint broker_leads_notification_status_check
      check (notification_status in ('pending', 'sent', 'failed', 'disabled'));
  end if;
end
$$;

create table if not exists public.broker_lead_events (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid not null references public.broker_leads(id) on delete cascade,
  request_id text,
  created_at timestamptz not null default now(),
  event_type text not null,
  event_title text,
  event_comment text,
  payload jsonb not null default '{}'::jsonb
);

create index if not exists broker_lead_events_lead_id_idx
  on public.broker_lead_events (lead_id, created_at desc);

create index if not exists broker_lead_events_request_id_idx
  on public.broker_lead_events (request_id, created_at desc)
  where request_id is not null;

create index if not exists broker_lead_events_event_type_idx
  on public.broker_lead_events (event_type);

create table if not exists public.broker_lead_rate_limits (
  id uuid primary key default gen_random_uuid(),
  fingerprint text not null,
  window_start timestamptz not null,
  attempt_count integer not null default 1,
  first_attempt_at timestamptz not null default now(),
  last_attempt_at timestamptz not null default now(),
  last_request_id text,
  constraint broker_lead_rate_limits_unique_window unique (fingerprint, window_start),
  constraint broker_lead_rate_limits_attempt_count_check check (attempt_count > 0)
);

create index if not exists broker_lead_rate_limits_fingerprint_idx
  on public.broker_lead_rate_limits (fingerprint);

create index if not exists broker_lead_rate_limits_window_start_idx
  on public.broker_lead_rate_limits (window_start desc);

create or replace function public.consume_broker_lead_rate_limit(
  p_fingerprint text,
  p_window_start timestamptz,
  p_request_id text,
  p_limit integer default 8
)
returns table (
  allowed boolean,
  attempt_count integer,
  rate_limit integer
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_attempt_count integer;
  v_limit integer := greatest(coalesce(p_limit, 8), 1);
begin
  if coalesce(trim(p_fingerprint), '') = '' then
    raise exception 'fingerprint_required';
  end if;

  insert into public.broker_lead_rate_limits (
    fingerprint,
    window_start,
    attempt_count,
    first_attempt_at,
    last_attempt_at,
    last_request_id
  ) values (
    p_fingerprint,
    date_trunc('hour', coalesce(p_window_start, now())),
    1,
    now(),
    now(),
    nullif(trim(p_request_id), '')
  )
  on conflict (fingerprint, window_start)
  do update set
    attempt_count = public.broker_lead_rate_limits.attempt_count + 1,
    last_attempt_at = now(),
    last_request_id = excluded.last_request_id
  returning public.broker_lead_rate_limits.attempt_count
  into v_attempt_count;

  return query
  select
    v_attempt_count <= v_limit,
    v_attempt_count,
    v_limit;
end;
$$;

revoke all on function public.consume_broker_lead_rate_limit(text, timestamptz, text, integer)
  from public, anon, authenticated;
grant execute on function public.consume_broker_lead_rate_limit(text, timestamptz, text, integer)
  to service_role;

create or replace function public.purge_broker_lead_rate_limits(
  p_before timestamptz default now() - interval '7 days'
)
returns bigint
language plpgsql
security definer
set search_path = public
as $$
declare
  v_deleted bigint;
begin
  delete from public.broker_lead_rate_limits
  where window_start < p_before;

  get diagnostics v_deleted = row_count;
  return v_deleted;
end;
$$;

revoke all on function public.purge_broker_lead_rate_limits(timestamptz)
  from public, anon, authenticated;
grant execute on function public.purge_broker_lead_rate_limits(timestamptz)
  to service_role;

alter table public.broker_leads enable row level security;
alter table public.broker_lead_events enable row level security;
alter table public.broker_lead_rate_limits enable row level security;

comment on column public.broker_leads.request_id is
  'Идемпотентный идентификатор, сформированный клиентской формой';
comment on column public.broker_leads.raw_payload is
  'Исходный JSON заявки schema_version=1; доступ только серверной роли и уполномоченным сотрудникам';
comment on table public.broker_lead_events is
  'История технических и операционных событий по заявкам ипотечного брокера';
comment on table public.broker_lead_rate_limits is
  'Обезличенные счётчики ограничения частоты; IP и полный payload не сохраняются';
comment on function public.consume_broker_lead_rate_limit(text, timestamptz, text, integer) is
  'Атомарно увеличивает обезличенный счётчик запросов и возвращает решение rate limit';
comment on function public.purge_broker_lead_rate_limits(timestamptz) is
  'Удаляет истёкшие технические счётчики rate limit; рекомендуется запускать по расписанию';
