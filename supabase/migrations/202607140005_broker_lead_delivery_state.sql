-- Техническое состояние доставки заявки через независимые каналы.
--
-- Миграция не включает hybrid и не отправляет данные наружу. Строка, созданная
-- публичной Supabase Edge Function, изначально подтверждает только канал
-- Supabase. После успешной доставки email браузер может отправить отдельную
-- обезличенную квитанцию, которая монотонно повышает состояние до both.

alter table public.broker_leads
  add column if not exists client_delivery_state text not null default 'supabase_only',
  add column if not exists delivery_state_updated_at timestamptz not null default now();

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'broker_leads_client_delivery_state_check'
      and conrelid = 'public.broker_leads'::regclass
  ) then
    alter table public.broker_leads
      add constraint broker_leads_client_delivery_state_check
      check (client_delivery_state in ('supabase_only', 'both'));
  end if;
end;
$$;

update public.broker_leads as leads
set
  client_delivery_state = case
    when leads.delivery_channel = 'both' then 'both'
    else 'supabase_only'
  end,
  delivery_state_updated_at = coalesce(leads.updated_at, leads.created_at, now())
where leads.client_delivery_state not in ('supabase_only', 'both')
   or leads.client_delivery_state is null;

create index if not exists broker_leads_client_delivery_state_idx
  on public.broker_leads (client_delivery_state, delivery_state_updated_at desc);

create or replace function public.mark_broker_lead_delivery_both(
  p_request_id text
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_request_id text := trim(coalesce(p_request_id, ''));
  v_lead_id uuid;
  v_current_state text;
begin
  if v_request_id = '' or length(v_request_id) > 80 then
    raise exception 'broker_delivery_request_id_invalid';
  end if;

  select leads.id, leads.client_delivery_state
  into v_lead_id, v_current_state
  from public.broker_leads as leads
  where leads.request_id = v_request_id
    and leads.processing_restricted = false
    and leads.retention_hold = false
    and leads.anonymized_at is null;

  if not found then
    return false;
  end if;

  if v_current_state = 'both' then
    return true;
  end if;

  update public.broker_leads as leads
  set
    client_delivery_state = 'both',
    delivery_channel = 'both',
    delivery_state_updated_at = now()
  where leads.id = v_lead_id
    and leads.request_id = v_request_id
    and leads.processing_restricted = false
    and leads.retention_hold = false
    and leads.anonymized_at is null
    and leads.client_delivery_state = 'supabase_only';

  if not found then
    return false;
  end if;

  insert into public.broker_lead_events (
    lead_id,
    request_id,
    event_type,
    event_title,
    event_comment,
    payload
  ) values (
    v_lead_id,
    v_request_id,
    'delivery_state_updated',
    'Подтверждены оба канала доставки',
    'Web3Forms и Supabase подтвердили приём заявки',
    jsonb_build_object('delivery_state', 'both')
  );

  return true;
end;
$$;

create or replace function public.broker_lead_delivery_state(
  p_lead_id uuid,
  p_request_id text
)
returns table (
  delivery_state text,
  delivery_state_updated_at timestamptz
)
language plpgsql
stable
security definer
set search_path = ''
as $$
declare
  v_guard record;
begin
  select *
  into v_guard
  from public.broker_lead_operational_guard(
    p_lead_id,
    p_request_id,
    'crm_read'
  );

  if not coalesce(v_guard.allowed, false) then
    raise exception 'broker_operational_blocked:%', coalesce(v_guard.blocker_code, 'unknown');
  end if;

  return query
  select
    leads.client_delivery_state,
    leads.delivery_state_updated_at
  from public.broker_leads as leads
  where leads.id = p_lead_id
    and leads.request_id = p_request_id;
end;
$$;

revoke all on function public.mark_broker_lead_delivery_both(text)
  from public, anon, authenticated;
grant execute on function public.mark_broker_lead_delivery_both(text)
  to service_role;

revoke all on function public.broker_lead_delivery_state(uuid, text)
  from public, anon, authenticated;
grant execute on function public.broker_lead_delivery_state(uuid, text)
  to service_role;

comment on column public.broker_leads.client_delivery_state is
  'Техническое подтверждение каналов: supabase_only или both. Web3Forms-only существует только в email-канале без строки broker_leads.';
comment on function public.mark_broker_lead_delivery_both(text) is
  'Монотонно подтверждает оба канала по request_id; не изменяет restricted, hold или anonymized заявку.';
comment on function public.broker_lead_delivery_state(uuid, text) is
  'Возвращает состояние каналов доверенному CRM-коду после operational guard.';
