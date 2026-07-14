-- Безопасная политика хранения и очистки заявок ипотечного брокера.
--
-- Миграция ничего не удаляет при применении и создаёт политику в выключенном состоянии.
-- Обезличивание возможно только после отдельного включения, preview и точного подтверждения.
-- Активные лиды, заявки с unresolved-уведомлением и строки с retention hold не затрагиваются.

alter table public.broker_leads
  add column if not exists retention_hold boolean not null default false,
  add column if not exists anonymized_at timestamptz,
  add column if not exists retention_reason_code text;

alter table public.broker_leads
  drop constraint if exists broker_leads_retention_reason_check;

alter table public.broker_leads
  add constraint broker_leads_retention_reason_check
  check (
    retention_reason_code is null
    or retention_reason_code in ('scheduled_anonymization', 'manual_privacy_request')
  );

create index if not exists broker_leads_retention_candidate_idx
  on public.broker_leads (status, notification_status, submitted_at, created_at)
  where anonymized_at is null and retention_hold = false;

create table if not exists public.broker_lead_retention_settings (
  singleton boolean primary key default true check (singleton = true),
  enabled boolean not null default false,
  anonymize_after_days integer not null default 365
    check (anonymize_after_days between 30 and 3650),
  delete_events_after_days integer not null default 180
    check (delete_events_after_days between 30 and 3650),
  delete_rate_limits_after_days integer not null default 7
    check (delete_rate_limits_after_days between 1 and 90),
  terminal_statuses text[] not null default array['closed', 'lost', 'archived']::text[],
  updated_at timestamptz not null default now(),
  check (cardinality(terminal_statuses) between 1 and 4),
  check (
    terminal_statuses <@ array['closed', 'lost', 'archived', 'cancelled']::text[]
  )
);

insert into public.broker_lead_retention_settings (singleton)
values (true)
on conflict (singleton) do nothing;

create table if not exists public.broker_lead_retention_runs (
  id uuid primary key default gen_random_uuid(),
  started_at timestamptz not null,
  finished_at timestamptz not null,
  status text not null default 'completed'
    check (status = 'completed'),
  policy_snapshot jsonb not null default '{}'::jsonb,
  anonymized_leads bigint not null default 0,
  deleted_events bigint not null default 0,
  deleted_rate_limits bigint not null default 0
);

create index if not exists broker_lead_retention_runs_started_idx
  on public.broker_lead_retention_runs (started_at desc);

alter table public.broker_lead_retention_settings enable row level security;
alter table public.broker_lead_retention_runs enable row level security;

create or replace function public.broker_lead_retention_preview()
returns table (
  policy_enabled boolean,
  anonymize_after_days integer,
  delete_events_after_days integer,
  delete_rate_limits_after_days integer,
  eligible_terminal_leads bigint,
  protected_active_or_unknown_leads bigint,
  protected_notification_leads bigint,
  protected_hold_leads bigint,
  eligible_events bigint,
  eligible_rate_limits bigint,
  oldest_eligible_lead_at timestamptz
)
language plpgsql
security definer
set search_path = public
stable
as $$
declare
  v_settings public.broker_lead_retention_settings%rowtype;
begin
  select *
  into v_settings
  from public.broker_lead_retention_settings
  where singleton = true;

  if not found then
    raise exception 'broker_retention_settings_missing';
  end if;

  return query
  with lead_flags as (
    select
      leads.*,
      coalesce(leads.submitted_at, leads.created_at) as retention_date,
      (
        leads.status = any(v_settings.terminal_statuses)
        and leads.status in ('closed', 'lost', 'archived', 'cancelled')
      ) as terminal_status,
      leads.notification_status in ('sent', 'disabled') as notification_resolved
    from public.broker_leads as leads
    where leads.anonymized_at is null
  )
  select
    v_settings.enabled,
    v_settings.anonymize_after_days,
    v_settings.delete_events_after_days,
    v_settings.delete_rate_limits_after_days,
    count(*) filter (
      where flags.retention_hold = false
        and flags.terminal_status
        and flags.notification_resolved
        and flags.retention_date < now() - make_interval(days => v_settings.anonymize_after_days)
    )::bigint,
    count(*) filter (
      where flags.retention_hold = false
        and not flags.terminal_status
    )::bigint,
    count(*) filter (
      where flags.retention_hold = false
        and flags.notification_status in ('pending', 'sending', 'failed')
    )::bigint,
    count(*) filter (where flags.retention_hold)::bigint,
    (
      select count(*)::bigint
      from public.broker_lead_events as events
      join public.broker_leads as leads on leads.id = events.lead_id
      where leads.retention_hold = false
        and events.created_at < now() - make_interval(days => v_settings.delete_events_after_days)
        and (
          leads.anonymized_at is not null
          or (
            leads.anonymized_at is null
            and leads.status = any(v_settings.terminal_statuses)
            and leads.status in ('closed', 'lost', 'archived', 'cancelled')
            and leads.notification_status in ('sent', 'disabled')
            and coalesce(leads.submitted_at, leads.created_at)
              < now() - make_interval(days => v_settings.anonymize_after_days)
          )
        )
    ),
    (
      select count(*)::bigint
      from public.broker_lead_rate_limits as limits
      where limits.window_start < now() - make_interval(days => v_settings.delete_rate_limits_after_days)
    ),
    min(flags.retention_date) filter (
      where flags.retention_hold = false
        and flags.terminal_status
        and flags.notification_resolved
        and flags.retention_date < now() - make_interval(days => v_settings.anonymize_after_days)
    )
  from lead_flags as flags;
end;
$$;

create or replace function public.apply_broker_lead_retention(
  p_confirmation text
)
returns table (
  run_id uuid,
  anonymized_leads bigint,
  deleted_events bigint,
  deleted_rate_limits bigint
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_settings public.broker_lead_retention_settings%rowtype;
  v_run_id uuid := gen_random_uuid();
  v_started_at timestamptz := now();
  v_anonymized bigint := 0;
  v_deleted_events bigint := 0;
  v_deleted_rate_limits bigint := 0;
begin
  if coalesce(trim(p_confirmation), '') <> 'APPLY_BROKER_RETENTION' then
    raise exception 'broker_retention_confirmation_required';
  end if;

  select *
  into v_settings
  from public.broker_lead_retention_settings
  where singleton = true
  for update;

  if not found then
    raise exception 'broker_retention_settings_missing';
  end if;

  if not v_settings.enabled then
    raise exception 'broker_retention_disabled';
  end if;

  update public.broker_leads as leads
  set
    client_name = null,
    phone = '[anonymized]',
    city = null,
    contact_time = null,
    mortgage_goal = null,
    property_type = null,
    property_price = null,
    down_payment = null,
    monthly_income = null,
    has_matkapital = null,
    has_bad_credit_history = null,
    has_previous_rejection = null,
    comment = null,
    utm_source = null,
    utm_medium = null,
    utm_campaign = null,
    utm_content = null,
    utm_term = null,
    user_agent = null,
    page_title = null,
    source_page = null,
    phone_normalized = null,
    preferred_contact = null,
    scenario = null,
    object_type = null,
    object_price_text = null,
    down_payment_text = null,
    income_type = null,
    bank_history = null,
    page_url = null,
    referrer = null,
    tracking = '{}'::jsonb,
    qualification = '{}'::jsonb,
    spam_check = '{}'::jsonb,
    raw_payload = '{}'::jsonb,
    technical_priority = null,
    journey_type = null,
    journey_stage = null,
    journey_scenario_slug = null,
    preparation = '{}'::jsonb,
    preparation_completed = '[]'::jsonb,
    remaining_questions = null,
    notification_last_error = null,
    retention_reason_code = 'scheduled_anonymization',
    anonymized_at = now()
  where leads.anonymized_at is null
    and leads.retention_hold = false
    and leads.status = any(v_settings.terminal_statuses)
    and leads.status in ('closed', 'lost', 'archived', 'cancelled')
    and leads.notification_status in ('sent', 'disabled')
    and coalesce(leads.submitted_at, leads.created_at)
      < now() - make_interval(days => v_settings.anonymize_after_days);

  get diagnostics v_anonymized = row_count;

  delete from public.broker_lead_events as events
  using public.broker_leads as leads
  where leads.id = events.lead_id
    and leads.anonymized_at is not null
    and leads.retention_hold = false
    and events.created_at < now() - make_interval(days => v_settings.delete_events_after_days);

  get diagnostics v_deleted_events = row_count;

  select public.purge_broker_lead_rate_limits(
    now() - make_interval(days => v_settings.delete_rate_limits_after_days)
  ) into v_deleted_rate_limits;

  insert into public.broker_lead_retention_runs (
    id,
    started_at,
    finished_at,
    status,
    policy_snapshot,
    anonymized_leads,
    deleted_events,
    deleted_rate_limits
  ) values (
    v_run_id,
    v_started_at,
    now(),
    'completed',
    jsonb_build_object(
      'anonymize_after_days', v_settings.anonymize_after_days,
      'delete_events_after_days', v_settings.delete_events_after_days,
      'delete_rate_limits_after_days', v_settings.delete_rate_limits_after_days,
      'terminal_statuses', to_jsonb(v_settings.terminal_statuses)
    ),
    v_anonymized,
    v_deleted_events,
    coalesce(v_deleted_rate_limits, 0)
  );

  return query select
    v_run_id,
    v_anonymized,
    v_deleted_events,
    coalesce(v_deleted_rate_limits, 0);
end;
$$;

revoke all on table public.broker_lead_retention_settings
  from public, anon, authenticated;
grant select, insert, update on table public.broker_lead_retention_settings
  to service_role;

revoke all on table public.broker_lead_retention_runs
  from public, anon, authenticated;
grant select, insert on table public.broker_lead_retention_runs
  to service_role;

revoke all on function public.broker_lead_retention_preview()
  from public, anon, authenticated;
grant execute on function public.broker_lead_retention_preview()
  to service_role;

revoke all on function public.apply_broker_lead_retention(text)
  from public, anon, authenticated;
grant execute on function public.apply_broker_lead_retention(text)
  to service_role;

comment on column public.broker_leads.retention_hold is
  'Запрещает автоматическое обезличивание и очистку связанных событий до ручного снятия hold';
comment on column public.broker_leads.anonymized_at is
  'Время необратимого удаления контактных и содержательных полей заявки';
comment on column public.broker_leads.retention_reason_code is
  'Код основания обезличивания из фиксированного списка без свободного текста';
comment on table public.broker_lead_retention_settings is
  'Выключенная по умолчанию техническая конфигурация хранения; активируется только после утверждения сроков';
comment on table public.broker_lead_retention_runs is
  'Обезличенный журнал только успешно завершённых retention-запусков без идентификаторов и содержимого заявок';
comment on function public.broker_lead_retention_preview() is
  'Возвращает агрегированные количества кандидатов, защищённых записей и событий, которые будут удалены в том же запуске';
comment on function public.apply_broker_lead_retention(text) is
  'Обезличивает только завершённые лиды с разрешённым notification status, очищает старые события и rate-limit записи после явного подтверждения';
