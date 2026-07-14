-- Индивидуальные запросы клиента на ограничение обработки или обезличивание заявки.
--
-- Миграция не выполняет действий над существующими заявками при применении.
-- Процесс доступен только service_role, требует точных lead_id + request_id,
-- отдельной проверки личности и явных строк подтверждения. Поиск по телефону,
-- свободные комментарии и публичный browser endpoint намеренно отсутствуют.

alter table public.broker_leads
  add column if not exists processing_restricted boolean not null default false;

create table if not exists public.broker_lead_privacy_requests (
  id uuid primary key default gen_random_uuid(),
  lead_id uuid not null references public.broker_leads(id) on delete restrict,
  request_id text not null,
  action_code text not null
    check (action_code in ('anonymize', 'restrict_processing')),
  status text not null default 'pending_verification'
    check (status in ('pending_verification', 'verified', 'completed', 'cancelled')),
  verification_method_code text
    check (
      verification_method_code is null
      or verification_method_code in (
        'same_contact_channel',
        'callback_verified',
        'documented_internal_check'
      )
    ),
  cancellation_reason_code text
    check (
      cancellation_reason_code is null
      or cancellation_reason_code in (
        'identity_not_verified',
        'duplicate_request',
        'request_withdrawn'
      )
    ),
  requested_at timestamptz not null default now(),
  verified_at timestamptz,
  completed_at timestamptz,
  cancelled_at timestamptz,
  previous_retention_hold boolean not null default false,
  previous_processing_restricted boolean not null default false,
  reference_hash text not null,
  check (length(reference_hash) = 64)
);

create unique index if not exists broker_lead_privacy_requests_open_lead_uidx
  on public.broker_lead_privacy_requests (lead_id)
  where status in ('pending_verification', 'verified');

create index if not exists broker_lead_privacy_requests_status_idx
  on public.broker_lead_privacy_requests (status, requested_at desc);

alter table public.broker_lead_privacy_requests enable row level security;

create or replace function public.broker_lead_privacy_request_preview(
  p_lead_id uuid,
  p_request_id text
)
returns table (
  lead_found boolean,
  can_start boolean,
  lead_status text,
  notification_status text,
  retention_hold boolean,
  processing_restricted boolean,
  anonymized boolean,
  open_request_count bigint,
  blocker_code text
)
language plpgsql
security definer
set search_path = public
stable
as $$
declare
  v_lead public.broker_leads%rowtype;
  v_open_count bigint := 0;
  v_blocker text := '';
begin
  select *
  into v_lead
  from public.broker_leads as leads
  where leads.id = p_lead_id
    and leads.request_id = p_request_id;

  if not found then
    return query select false, false, null::text, null::text, false, false, false, 0::bigint, 'lead_not_found'::text;
    return;
  end if;

  select count(*)::bigint
  into v_open_count
  from public.broker_lead_privacy_requests as requests
  where requests.lead_id = p_lead_id
    and requests.status in ('pending_verification', 'verified');

  v_blocker := case
    when v_lead.anonymized_at is not null then 'already_anonymized'
    when v_lead.retention_hold then 'existing_retention_hold'
    when v_lead.notification_status in ('pending', 'sending') then 'notification_unresolved'
    when v_open_count > 0 then 'open_privacy_request_exists'
    else ''
  end;

  return query select
    true,
    v_blocker = '',
    v_lead.status,
    v_lead.notification_status,
    v_lead.retention_hold,
    v_lead.processing_restricted,
    v_lead.anonymized_at is not null,
    v_open_count,
    nullif(v_blocker, '');
end;
$$;

create or replace function public.start_broker_lead_privacy_request(
  p_lead_id uuid,
  p_request_id text,
  p_action_code text,
  p_confirmation text
)
returns table (
  privacy_request_id uuid,
  privacy_status text,
  action_code text,
  retention_hold boolean,
  processing_restricted boolean
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_lead public.broker_leads%rowtype;
  v_action_code text := lower(trim(coalesce(p_action_code, '')));
  v_privacy_request_id uuid := gen_random_uuid();
begin
  if coalesce(trim(p_confirmation), '') <> 'START_BROKER_PRIVACY_REQUEST' then
    raise exception 'broker_privacy_start_confirmation_required';
  end if;

  if v_action_code not in ('anonymize', 'restrict_processing') then
    raise exception 'broker_privacy_action_invalid';
  end if;

  select *
  into v_lead
  from public.broker_leads as leads
  where leads.id = p_lead_id
    and leads.request_id = p_request_id
  for update;

  if not found then
    raise exception 'broker_privacy_lead_not_found';
  end if;
  if v_lead.anonymized_at is not null then
    raise exception 'broker_privacy_already_anonymized';
  end if;
  if v_lead.retention_hold then
    raise exception 'broker_privacy_existing_hold';
  end if;
  if v_lead.notification_status in ('pending', 'sending') then
    raise exception 'broker_privacy_notification_unresolved';
  end if;
  if exists (
    select 1
    from public.broker_lead_privacy_requests as requests
    where requests.lead_id = p_lead_id
      and requests.status in ('pending_verification', 'verified')
  ) then
    raise exception 'broker_privacy_open_request_exists';
  end if;

  insert into public.broker_lead_privacy_requests (
    id,
    lead_id,
    request_id,
    action_code,
    previous_retention_hold,
    previous_processing_restricted,
    reference_hash
  ) values (
    v_privacy_request_id,
    p_lead_id,
    p_request_id,
    v_action_code,
    v_lead.retention_hold,
    v_lead.processing_restricted,
    encode(digest(p_lead_id::text || ':' || p_request_id, 'sha256'), 'hex')
  );

  update public.broker_leads as leads
  set
    retention_hold = true,
    processing_restricted = true
  where leads.id = p_lead_id;

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
    'privacy_request_started',
    'Начата проверка индивидуального запроса клиента',
    'Обработка ограничена до проверки запроса',
    jsonb_build_object('action_code', v_action_code)
  );

  return query select
    v_privacy_request_id,
    'pending_verification'::text,
    v_action_code,
    true,
    true;
end;
$$;

create or replace function public.verify_broker_lead_privacy_request(
  p_privacy_request_id uuid,
  p_verification_method_code text,
  p_confirmation text
)
returns table (
  privacy_request_id uuid,
  privacy_status text,
  verification_method_code text
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_request public.broker_lead_privacy_requests%rowtype;
  v_method text := lower(trim(coalesce(p_verification_method_code, '')));
begin
  if coalesce(trim(p_confirmation), '') <> 'VERIFY_BROKER_PRIVACY_REQUEST' then
    raise exception 'broker_privacy_verify_confirmation_required';
  end if;
  if v_method not in ('same_contact_channel', 'callback_verified', 'documented_internal_check') then
    raise exception 'broker_privacy_verification_method_invalid';
  end if;

  select *
  into v_request
  from public.broker_lead_privacy_requests as requests
  where requests.id = p_privacy_request_id
  for update;

  if not found then
    raise exception 'broker_privacy_request_not_found';
  end if;
  if v_request.status <> 'pending_verification' then
    raise exception 'broker_privacy_request_not_pending';
  end if;

  update public.broker_lead_privacy_requests
  set
    status = 'verified',
    verification_method_code = v_method,
    verified_at = now()
  where id = p_privacy_request_id;

  insert into public.broker_lead_events (
    lead_id,
    request_id,
    event_type,
    event_title,
    event_comment,
    payload
  ) values (
    v_request.lead_id,
    v_request.request_id,
    'privacy_request_verified',
    'Индивидуальный запрос клиента подтверждён',
    'Личность проверена вне публичной формы',
    jsonb_build_object(
      'action_code', v_request.action_code,
      'verification_method_code', v_method
    )
  );

  return query select p_privacy_request_id, 'verified'::text, v_method;
end;
$$;

create or replace function public.apply_broker_lead_privacy_request(
  p_privacy_request_id uuid,
  p_confirmation text
)
returns table (
  privacy_request_id uuid,
  privacy_status text,
  action_code text,
  anonymized boolean,
  processing_restricted boolean
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_request public.broker_lead_privacy_requests%rowtype;
  v_anonymized boolean := false;
begin
  if coalesce(trim(p_confirmation), '') <> 'APPLY_BROKER_PRIVACY_REQUEST' then
    raise exception 'broker_privacy_apply_confirmation_required';
  end if;

  select *
  into v_request
  from public.broker_lead_privacy_requests as requests
  where requests.id = p_privacy_request_id
  for update;

  if not found then
    raise exception 'broker_privacy_request_not_found';
  end if;
  if v_request.status <> 'verified' or v_request.verified_at is null then
    raise exception 'broker_privacy_request_not_verified';
  end if;

  perform 1
  from public.broker_leads as leads
  where leads.id = v_request.lead_id
    and leads.request_id = v_request.request_id
    and leads.retention_hold = true
    and leads.processing_restricted = true
    and leads.notification_status not in ('pending', 'sending')
  for update;

  if not found then
    raise exception 'broker_privacy_lead_state_changed';
  end if;

  if v_request.action_code = 'anonymize' then
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
      retention_hold = false,
      processing_restricted = true,
      retention_reason_code = 'manual_privacy_request',
      anonymized_at = now()
    where leads.id = v_request.lead_id;

    v_anonymized := true;
  end if;

  update public.broker_lead_privacy_requests
  set
    status = 'completed',
    completed_at = now()
  where id = p_privacy_request_id;

  insert into public.broker_lead_events (
    lead_id,
    request_id,
    event_type,
    event_title,
    event_comment,
    payload
  ) values (
    v_request.lead_id,
    v_request.request_id,
    'privacy_request_completed',
    'Индивидуальный запрос клиента выполнен',
    case
      when v_request.action_code = 'anonymize' then 'Заявка необратимо обезличена'
      else 'Дальнейшая обработка заявки ограничена'
    end,
    jsonb_build_object('action_code', v_request.action_code)
  );

  return query select
    p_privacy_request_id,
    'completed'::text,
    v_request.action_code,
    v_anonymized,
    true;
end;
$$;

create or replace function public.cancel_broker_lead_privacy_request(
  p_privacy_request_id uuid,
  p_cancellation_reason_code text,
  p_confirmation text
)
returns table (
  privacy_request_id uuid,
  privacy_status text,
  cancellation_reason_code text
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_request public.broker_lead_privacy_requests%rowtype;
  v_reason text := lower(trim(coalesce(p_cancellation_reason_code, '')));
begin
  if coalesce(trim(p_confirmation), '') <> 'CANCEL_BROKER_PRIVACY_REQUEST' then
    raise exception 'broker_privacy_cancel_confirmation_required';
  end if;
  if v_reason not in ('identity_not_verified', 'duplicate_request', 'request_withdrawn') then
    raise exception 'broker_privacy_cancellation_reason_invalid';
  end if;

  select *
  into v_request
  from public.broker_lead_privacy_requests as requests
  where requests.id = p_privacy_request_id
  for update;

  if not found then
    raise exception 'broker_privacy_request_not_found';
  end if;
  if v_request.status not in ('pending_verification', 'verified') then
    raise exception 'broker_privacy_request_not_open';
  end if;

  update public.broker_leads as leads
  set
    retention_hold = v_request.previous_retention_hold,
    processing_restricted = v_request.previous_processing_restricted
  where leads.id = v_request.lead_id
    and leads.anonymized_at is null;

  update public.broker_lead_privacy_requests
  set
    status = 'cancelled',
    cancellation_reason_code = v_reason,
    cancelled_at = now()
  where id = p_privacy_request_id;

  insert into public.broker_lead_events (
    lead_id,
    request_id,
    event_type,
    event_title,
    event_comment,
    payload
  ) values (
    v_request.lead_id,
    v_request.request_id,
    'privacy_request_cancelled',
    'Индивидуальный запрос клиента закрыт без применения',
    'Исходные технические ограничения восстановлены',
    jsonb_build_object(
      'action_code', v_request.action_code,
      'cancellation_reason_code', v_reason
    )
  );

  return query select p_privacy_request_id, 'cancelled'::text, v_reason;
end;
$$;

revoke all on table public.broker_lead_privacy_requests
  from public, anon, authenticated;
grant select, insert, update on table public.broker_lead_privacy_requests
  to service_role;

revoke all on function public.broker_lead_privacy_request_preview(uuid, text)
  from public, anon, authenticated;
grant execute on function public.broker_lead_privacy_request_preview(uuid, text)
  to service_role;

revoke all on function public.start_broker_lead_privacy_request(uuid, text, text, text)
  from public, anon, authenticated;
grant execute on function public.start_broker_lead_privacy_request(uuid, text, text, text)
  to service_role;

revoke all on function public.verify_broker_lead_privacy_request(uuid, text, text)
  from public, anon, authenticated;
grant execute on function public.verify_broker_lead_privacy_request(uuid, text, text)
  to service_role;

revoke all on function public.apply_broker_lead_privacy_request(uuid, text)
  from public, anon, authenticated;
grant execute on function public.apply_broker_lead_privacy_request(uuid, text)
  to service_role;

revoke all on function public.cancel_broker_lead_privacy_request(uuid, text, text)
  from public, anon, authenticated;
grant execute on function public.cancel_broker_lead_privacy_request(uuid, text, text)
  to service_role;

comment on column public.broker_leads.processing_restricted is
  'Запрещает дальнейшую операционную обработку заявки после подтверждённого индивидуального запроса клиента';
comment on table public.broker_lead_privacy_requests is
  'Технический журнал индивидуальных privacy-запросов без свободного текста и поиска по персональным данным';
comment on function public.broker_lead_privacy_request_preview(uuid, text) is
  'Возвращает только техническую готовность заявки к privacy-процессу без имени, телефона и содержимого';
comment on function public.start_broker_lead_privacy_request(uuid, text, text, text) is
  'Ставит точную заявку на hold и ограничивает обработку до проверки личности клиента';
comment on function public.verify_broker_lead_privacy_request(uuid, text, text) is
  'Фиксирует проверку личности по коду метода без сохранения документов и свободного комментария';
comment on function public.apply_broker_lead_privacy_request(uuid, text) is
  'Выполняет подтверждённое ограничение обработки либо необратимое обезличивание одной заявки';
comment on function public.cancel_broker_lead_privacy_request(uuid, text, text) is
  'Закрывает неподтверждённый или отозванный запрос и восстанавливает предыдущие технические ограничения';