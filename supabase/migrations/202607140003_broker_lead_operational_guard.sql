-- Единый guard операционных действий для заявок с ограниченной обработкой.
--
-- Миграция не включает публичный Supabase endpoint и не выполняет действий над
-- существующими заявками. Она блокирует уведомления, повторную обработку,
-- обычные события, CRM-изменения и контролируемый экспорт для строк с
-- processing_restricted, retention_hold или anonymized_at.

create or replace function public.broker_lead_operational_guard(
  p_lead_id uuid,
  p_request_id text,
  p_action_code text
)
returns table (
  allowed boolean,
  blocker_code text,
  lead_status text,
  notification_status text,
  notification_attempt_count integer,
  processing_restricted boolean,
  retention_hold boolean,
  anonymized boolean
)
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  v_action_code text := lower(trim(coalesce(p_action_code, '')));
  v_lead public.broker_leads%rowtype;
  v_blocker text := '';
begin
  if v_action_code not in (
    'notification_claim',
    'notification_complete',
    'notification_summary',
    'notification_retry',
    'crm_read',
    'crm_update',
    'export',
    'follow_up'
  ) then
    raise exception 'broker_operational_action_invalid';
  end if;

  select *
  into v_lead
  from public.broker_leads as leads
  where leads.id = p_lead_id
    and leads.request_id = p_request_id;

  if not found then
    return query select
      false,
      'lead_not_found'::text,
      null::text,
      null::text,
      0,
      false,
      false,
      false;
    return;
  end if;

  v_blocker := case
    when v_lead.anonymized_at is not null then 'already_anonymized'
    when v_lead.processing_restricted then 'processing_restricted'
    when v_lead.retention_hold then 'retention_hold'
    else ''
  end;

  return query select
    v_blocker = '',
    nullif(v_blocker, ''),
    v_lead.status,
    v_lead.notification_status,
    coalesce(v_lead.notification_attempt_count, 0),
    v_lead.processing_restricted,
    v_lead.retention_hold,
    v_lead.anonymized_at is not null;
end;
$$;

create or replace function public.broker_lead_operational_snapshot(
  p_lead_id uuid,
  p_request_id text,
  p_action_code text
)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  v_action_code text := lower(trim(coalesce(p_action_code, '')));
  v_guard record;
  v_snapshot jsonb;
begin
  if v_action_code not in ('crm_read', 'export', 'follow_up') then
    raise exception 'broker_operational_snapshot_action_invalid';
  end if;

  select *
  into v_guard
  from public.broker_lead_operational_guard(p_lead_id, p_request_id, v_action_code);

  if not coalesce(v_guard.allowed, false) then
    raise exception 'broker_operational_blocked:%', coalesce(v_guard.blocker_code, 'unknown');
  end if;

  select jsonb_build_object(
    'lead_id', leads.id,
    'request_id', leads.request_id,
    'status', leads.status,
    'submitted_at', leads.submitted_at,
    'created_at', leads.created_at,
    'client', jsonb_build_object(
      'name', coalesce(leads.client_name, ''),
      'phone', coalesce(leads.phone, ''),
      'city', coalesce(leads.city, ''),
      'preferred_contact', coalesce(leads.preferred_contact, leads.contact_time, '')
    ),
    'mortgage', jsonb_build_object(
      'scenario', coalesce(leads.scenario, leads.mortgage_goal, ''),
      'object_type', coalesce(leads.object_type, leads.property_type, ''),
      'object_price', coalesce(leads.object_price_text, ''),
      'down_payment', coalesce(leads.down_payment_text, ''),
      'income_type', coalesce(leads.income_type, ''),
      'bank_history', coalesce(leads.bank_history, ''),
      'comment', coalesce(leads.comment, '')
    ),
    'technical_priority', coalesce(leads.technical_priority, ''),
    'source_page', coalesce(leads.source_page, ''),
    'qualification', coalesce(leads.qualification, '{}'::jsonb)
  )
  into v_snapshot
  from public.broker_leads as leads
  where leads.id = p_lead_id
    and leads.request_id = p_request_id;

  return coalesce(v_snapshot, '{}'::jsonb);
end;
$$;

create or replace function public.broker_lead_notification_summary(
  p_lead_id uuid
)
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_lead public.broker_leads%rowtype;
  v_guard record;
  v_preparation_text text := '';
  v_completed_text text := '';
begin
  select *
  into v_lead
  from public.broker_leads as leads
  where leads.id = p_lead_id;

  if not found then
    raise exception 'broker_lead_not_found';
  end if;

  select *
  into v_guard
  from public.broker_lead_operational_guard(
    v_lead.id,
    v_lead.request_id,
    'notification_summary'
  );

  if not coalesce(v_guard.allowed, false) then
    raise exception 'broker_operational_blocked:%', coalesce(v_guard.blocker_code, 'unknown');
  end if;

  if jsonb_typeof(v_lead.preparation_completed) = 'array' then
    select string_agg(left(trim(value), 180), '; ' order by ordinality)
    into v_completed_text
    from jsonb_array_elements_text(v_lead.preparation_completed)
      with ordinality as completed(value, ordinality)
    where trim(value) <> '';
  end if;

  if coalesce(v_lead.journey_type, '') <> ''
    or coalesce(v_lead.journey_stage, '') <> ''
    or coalesce(v_lead.journey_scenario_slug, '') <> ''
    or coalesce(v_completed_text, '') <> ''
    or coalesce(v_lead.remaining_questions, '') <> '' then
    v_preparation_text := concat(
      E'\n\nПОДГОТОВКА ДО ОБРАЩЕНИЯ',
      E'\nТип маршрута: ', coalesce(nullif(v_lead.journey_type, ''), 'не указан'),
      E'\nЭтап: ', coalesce(nullif(v_lead.journey_stage, ''), 'не указан'),
      E'\nСценарий: ', coalesce(nullif(v_lead.journey_scenario_slug, ''), 'не указан'),
      E'\nЧто уже проверено: ', coalesce(nullif(v_completed_text, ''), 'не отмечено'),
      E'\nЧто осталось уточнить: ', coalesce(nullif(v_lead.remaining_questions, ''), 'не указано')
    );
  end if;

  return concat(
    'Новая заявка ипотечному брокеру',
    E'\nID: ', coalesce(v_lead.request_id, v_lead.id::text),
    E'\nИмя: ', coalesce(v_lead.client_name, ''),
    E'\nТелефон: ', coalesce(v_lead.phone, ''),
    E'\nГород: ', coalesce(v_lead.city, ''),
    E'\nСвязь: ', coalesce(v_lead.preferred_contact, v_lead.contact_time, ''),
    E'\nЗадача: ', coalesce(v_lead.scenario, v_lead.mortgage_goal, ''),
    E'\nОбъект: ', coalesce(v_lead.object_type, v_lead.property_type, ''),
    E'\nСтоимость: ', coalesce(v_lead.object_price_text, ''),
    E'\nВзнос: ', coalesce(v_lead.down_payment_text, ''),
    E'\nДоход: ', coalesce(v_lead.income_type, ''),
    E'\nПриоритет: ', coalesce(v_lead.technical_priority, ''),
    E'\nИсточник: ', coalesce(v_lead.source_page, v_lead.page_url, ''),
    v_preparation_text
  );
end;
$$;

create or replace function public.claim_broker_lead_notification(
  p_lead_id uuid,
  p_request_id text
)
returns table (
  claimed boolean,
  current_status text,
  attempt_count integer
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_guard record;
  v_status text;
  v_attempt_count integer;
begin
  select *
  into v_guard
  from public.broker_lead_operational_guard(
    p_lead_id,
    p_request_id,
    'notification_claim'
  );

  if not coalesce(v_guard.allowed, false) then
    return query select
      false,
      case when v_guard.blocker_code = 'lead_not_found' then 'missing' else 'restricted' end,
      coalesce(v_guard.notification_attempt_count, 0);
    return;
  end if;

  update public.broker_leads as leads
  set
    notification_status = 'sending',
    notification_attempt_count = leads.notification_attempt_count + 1,
    notification_attempted_at = now(),
    notification_last_error = null
  where leads.id = p_lead_id
    and leads.request_id = p_request_id
    and leads.processing_restricted = false
    and leads.retention_hold = false
    and leads.anonymized_at is null
    and (
      leads.notification_status = 'pending'
      or (
        leads.notification_status = 'sending'
        and coalesce(leads.notification_attempted_at, '-infinity'::timestamptz) < now() - interval '15 minutes'
      )
    )
  returning leads.notification_status, leads.notification_attempt_count
  into v_status, v_attempt_count;

  if found then
    return query select true, v_status, v_attempt_count;
    return;
  end if;

  select
    case
      when leads.processing_restricted or leads.retention_hold or leads.anonymized_at is not null then 'restricted'
      else leads.notification_status
    end,
    leads.notification_attempt_count
  into v_status, v_attempt_count
  from public.broker_leads as leads
  where leads.id = p_lead_id
    and leads.request_id = p_request_id;

  return query select false, coalesce(v_status, 'missing'), coalesce(v_attempt_count, 0);
end;
$$;

create or replace function public.complete_broker_lead_notification(
  p_lead_id uuid,
  p_request_id text,
  p_success boolean,
  p_error text default null
)
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_guard record;
  v_status text;
begin
  select *
  into v_guard
  from public.broker_lead_operational_guard(
    p_lead_id,
    p_request_id,
    'notification_complete'
  );

  if not coalesce(v_guard.allowed, false) then
    return case when v_guard.blocker_code = 'lead_not_found' then 'unchanged' else 'restricted' end;
  end if;

  update public.broker_leads as leads
  set
    notification_status = case when p_success then 'sent' else 'failed' end,
    notification_sent_at = case when p_success then now() else leads.notification_sent_at end,
    notification_last_error = case
      when p_success then null
      else nullif(left(trim(coalesce(p_error, 'notification_failed')), 300), '')
    end
  where leads.id = p_lead_id
    and leads.request_id = p_request_id
    and leads.processing_restricted = false
    and leads.retention_hold = false
    and leads.anonymized_at is null
    and leads.notification_status = 'sending'
  returning leads.notification_status
  into v_status;

  return coalesce(v_status, 'unchanged');
end;
$$;

create or replace function public.request_broker_lead_notification_retry(
  p_lead_id uuid,
  p_request_id text,
  p_reason_code text
)
returns table (
  retry_requested boolean,
  current_status text,
  retry_count integer,
  reason_code text
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_guard record;
  v_reason_code text := lower(trim(coalesce(p_reason_code, '')));
  v_retry_count integer;
  v_attempt_count integer;
  v_status text;
  v_stored_reason_code text;
begin
  if v_reason_code not in (
    'telegram_config_fixed',
    'telegram_temporary_error',
    'notification_summary_fixed',
    'manual_recovery'
  ) then
    raise exception 'invalid_notification_retry_reason';
  end if;

  select *
  into v_guard
  from public.broker_lead_operational_guard(
    p_lead_id,
    p_request_id,
    'notification_retry'
  );

  if not coalesce(v_guard.allowed, false) then
    return query select
      false,
      case when v_guard.blocker_code = 'lead_not_found' then 'missing' else 'restricted' end,
      0,
      ''::text;
    return;
  end if;

  update public.broker_leads as leads
  set
    notification_status = 'pending',
    notification_manual_retry_count = leads.notification_manual_retry_count + 1,
    notification_manual_retry_requested_at = now(),
    notification_manual_retry_reason_code = v_reason_code
  where leads.id = p_lead_id
    and leads.request_id = p_request_id
    and leads.processing_restricted = false
    and leads.retention_hold = false
    and leads.anonymized_at is null
    and leads.notification_status = 'failed'
  returning
    leads.notification_manual_retry_count,
    leads.notification_attempt_count,
    leads.notification_status,
    leads.notification_manual_retry_reason_code
  into v_retry_count, v_attempt_count, v_status, v_stored_reason_code;

  if found then
    insert into public.broker_lead_events (
      lead_id,
      request_id,
      event_type,
      event_title,
      event_comment,
      payload
    ) values (
      p_lead_id,
      p_request_id,
      'notification_retry_requested',
      'Запрошен ручной повтор уведомления',
      'Уведомление переведено из failed в pending',
      jsonb_build_object(
        'reason_code', v_stored_reason_code,
        'manual_retry_count', v_retry_count,
        'previous_attempt_count', coalesce(v_attempt_count, 0)
      )
    );

    return query select true, v_status, v_retry_count, v_stored_reason_code;
    return;
  end if;

  select
    case
      when leads.processing_restricted or leads.retention_hold or leads.anonymized_at is not null then 'restricted'
      else leads.notification_status
    end,
    leads.notification_manual_retry_count,
    leads.notification_manual_retry_reason_code
  into v_status, v_retry_count, v_stored_reason_code
  from public.broker_leads as leads
  where leads.id = p_lead_id
    and leads.request_id = p_request_id;

  return query select
    false,
    coalesce(v_status, 'missing'),
    coalesce(v_retry_count, 0),
    coalesce(v_stored_reason_code, '');
end;
$$;

create or replace function public.broker_lead_notification_queue_health()
returns table (
  notification_status text,
  lead_count bigint,
  oldest_lead_at timestamptz,
  oldest_attempted_at timestamptz,
  stale_count bigint,
  max_attempt_count integer,
  total_manual_retries bigint
)
language sql
stable
security definer
set search_path = ''
as $$
  select
    leads.notification_status,
    count(*)::bigint as lead_count,
    min(coalesce(leads.submitted_at, leads.created_at)) as oldest_lead_at,
    min(leads.notification_attempted_at) as oldest_attempted_at,
    count(*) filter (
      where leads.notification_status = 'sending'
        and coalesce(leads.notification_attempted_at, '-infinity'::timestamptz) < now() - interval '15 minutes'
    )::bigint as stale_count,
    max(leads.notification_attempt_count)::integer as max_attempt_count,
    sum(leads.notification_manual_retry_count)::bigint as total_manual_retries
  from public.broker_leads as leads
  where leads.processing_restricted = false
    and leads.retention_hold = false
    and leads.anonymized_at is null
  group by leads.notification_status
  order by case leads.notification_status
    when 'failed' then 1
    when 'sending' then 2
    when 'pending' then 3
    when 'sent' then 4
    when 'disabled' then 5
    else 6
  end;
$$;

create or replace function public.enforce_broker_lead_operational_restriction()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_request public.broker_lead_privacy_requests%rowtype;
  v_anonymization_fields text[] := array[
    'updated_at',
    'client_name',
    'phone',
    'city',
    'contact_time',
    'mortgage_goal',
    'property_type',
    'property_price',
    'down_payment',
    'monthly_income',
    'has_matkapital',
    'has_bad_credit_history',
    'has_previous_rejection',
    'comment',
    'utm_source',
    'utm_medium',
    'utm_campaign',
    'utm_content',
    'utm_term',
    'user_agent',
    'page_title',
    'source_page',
    'phone_normalized',
    'preferred_contact',
    'scenario',
    'object_type',
    'object_price_text',
    'down_payment_text',
    'income_type',
    'bank_history',
    'page_url',
    'referrer',
    'tracking',
    'qualification',
    'spam_check',
    'raw_payload',
    'technical_priority',
    'journey_type',
    'journey_stage',
    'journey_scenario_slug',
    'preparation',
    'preparation_completed',
    'remaining_questions',
    'notification_last_error',
    'retention_hold',
    'processing_restricted',
    'retention_reason_code',
    'anonymized_at'
  ];
begin
  if old.anonymized_at is not null then
    raise exception 'broker_lead_already_anonymized';
  end if;

  if not old.processing_restricted and not old.retention_hold then
    return new;
  end if;

  select *
  into v_request
  from public.broker_lead_privacy_requests as requests
  where requests.lead_id = old.id
    and requests.request_id = old.request_id
    and requests.status = 'verified'
    and requests.action_code = 'anonymize'
  order by requests.verified_at desc
  limit 1;

  if found
    and new.client_name is null
    and new.phone = '[anonymized]'
    and new.city is null
    and new.comment is null
    and new.phone_normalized is null
    and new.tracking = '{}'::jsonb
    and new.qualification = '{}'::jsonb
    and new.spam_check = '{}'::jsonb
    and new.raw_payload = '{}'::jsonb
    and new.preparation = '{}'::jsonb
    and new.preparation_completed = '[]'::jsonb
    and new.remaining_questions is null
    and new.retention_hold = false
    and new.processing_restricted = true
    and new.retention_reason_code = 'manual_privacy_request'
    and new.anonymized_at is not null
    and (to_jsonb(new) - v_anonymization_fields) = (to_jsonb(old) - v_anonymization_fields) then
    return new;
  end if;

  select *
  into v_request
  from public.broker_lead_privacy_requests as requests
  where requests.lead_id = old.id
    and requests.request_id = old.request_id
    and requests.status in ('pending_verification', 'verified')
  order by requests.requested_at desc
  limit 1;

  if found
    and new.retention_hold = v_request.previous_retention_hold
    and new.processing_restricted = v_request.previous_processing_restricted
    and (to_jsonb(new) - array['updated_at', 'retention_hold', 'processing_restricted']::text[])
      = (to_jsonb(old) - array['updated_at', 'retention_hold', 'processing_restricted']::text[]) then
    return new;
  end if;

  raise exception 'broker_lead_processing_restricted';
end;
$$;

create or replace function public.enforce_broker_lead_event_restriction()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_restricted boolean := false;
begin
  select
    leads.processing_restricted
      or leads.retention_hold
      or leads.anonymized_at is not null
  into v_restricted
  from public.broker_leads as leads
  where leads.id = new.lead_id;

  if coalesce(v_restricted, false)
    and new.event_type not in (
      'privacy_request_started',
      'privacy_request_verified',
      'privacy_request_completed',
      'privacy_request_cancelled'
    ) then
    raise exception 'broker_lead_processing_restricted';
  end if;

  return new;
end;
$$;

drop trigger if exists broker_leads_guard_restricted_updates on public.broker_leads;
create trigger broker_leads_guard_restricted_updates
before update on public.broker_leads
for each row
execute function public.enforce_broker_lead_operational_restriction();

drop trigger if exists broker_lead_events_guard_restricted_insert on public.broker_lead_events;
create trigger broker_lead_events_guard_restricted_insert
before insert on public.broker_lead_events
for each row
execute function public.enforce_broker_lead_event_restriction();

revoke all on function public.broker_lead_operational_guard(uuid, text, text)
  from public, anon, authenticated;
grant execute on function public.broker_lead_operational_guard(uuid, text, text)
  to service_role;

revoke all on function public.broker_lead_operational_snapshot(uuid, text, text)
  from public, anon, authenticated;
grant execute on function public.broker_lead_operational_snapshot(uuid, text, text)
  to service_role;

revoke all on function public.broker_lead_notification_summary(uuid)
  from public, anon, authenticated;
grant execute on function public.broker_lead_notification_summary(uuid)
  to service_role;

revoke all on function public.claim_broker_lead_notification(uuid, text)
  from public, anon, authenticated;
grant execute on function public.claim_broker_lead_notification(uuid, text)
  to service_role;

revoke all on function public.complete_broker_lead_notification(uuid, text, boolean, text)
  from public, anon, authenticated;
grant execute on function public.complete_broker_lead_notification(uuid, text, boolean, text)
  to service_role;

revoke all on function public.request_broker_lead_notification_retry(uuid, text, text)
  from public, anon, authenticated;
grant execute on function public.request_broker_lead_notification_retry(uuid, text, text)
  to service_role;

revoke all on function public.broker_lead_notification_queue_health()
  from public, anon, authenticated;
grant execute on function public.broker_lead_notification_queue_health()
  to service_role;

revoke all on function public.enforce_broker_lead_operational_restriction()
  from public, anon, authenticated, service_role;
revoke all on function public.enforce_broker_lead_event_restriction()
  from public, anon, authenticated, service_role;

comment on function public.broker_lead_operational_guard(uuid, text, text) is
  'Единообразно блокирует уведомления, CRM-действия, follow-up и экспорт для restricted, hold или anonymized заявки';
comment on function public.broker_lead_operational_snapshot(uuid, text, text) is
  'Возвращает ограниченный CRM/export snapshot только для заявки, прошедшей operational guard; raw_payload не выдаётся';
comment on function public.enforce_broker_lead_operational_restriction() is
  'Блокирует прямые изменения restricted/hold/anonymized заявки, кроме подтверждённого privacy apply или cancel';
comment on function public.enforce_broker_lead_event_restriction() is
  'Запрещает обычные события для restricted/hold/anonymized заявки и оставляет только события privacy workflow';