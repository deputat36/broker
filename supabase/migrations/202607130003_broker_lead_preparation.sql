-- Структурированный контекст подготовки онлайн-заявки.
--
-- Миграция не меняет публичный schema_version=1. Edge Function продолжает
-- сохранять исходный raw_payload, а серверный trigger извлекает необязательный
-- объект preparation в отдельные CRM-поля.

alter table public.broker_leads
  add column if not exists journey_type text,
  add column if not exists journey_stage text,
  add column if not exists journey_scenario_slug text,
  add column if not exists preparation jsonb not null default '{}'::jsonb,
  add column if not exists preparation_completed jsonb not null default '[]'::jsonb,
  add column if not exists remaining_questions text;

create index if not exists broker_leads_preparation_gin_idx
  on public.broker_leads using gin (preparation);

create index if not exists broker_leads_journey_scenario_idx
  on public.broker_leads (journey_scenario_slug)
  where journey_scenario_slug is not null;

create or replace function public.sync_broker_lead_preparation()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_preparation jsonb;
  v_completed jsonb;
begin
  v_preparation := case
    when jsonb_typeof(new.raw_payload -> 'preparation') = 'object'
      then new.raw_payload -> 'preparation'
    else '{}'::jsonb
  end;

  v_completed := case
    when jsonb_typeof(v_preparation -> 'completed_labels') = 'array'
      then v_preparation -> 'completed_labels'
    else '[]'::jsonb
  end;

  new.preparation := v_preparation;
  new.preparation_completed := v_completed;
  new.journey_type := nullif(left(trim(coalesce(v_preparation ->> 'journey_type', '')), 160), '');
  new.journey_stage := nullif(left(trim(coalesce(v_preparation ->> 'journey_stage', '')), 200), '');
  new.journey_scenario_slug := nullif(left(trim(coalesce(v_preparation ->> 'scenario_slug', '')), 160), '');
  new.remaining_questions := nullif(left(trim(coalesce(v_preparation ->> 'remaining_questions', '')), 700), '');

  return new;
end;
$$;

revoke all on function public.sync_broker_lead_preparation()
  from public, anon, authenticated;
grant execute on function public.sync_broker_lead_preparation()
  to service_role;

drop trigger if exists broker_leads_sync_preparation on public.broker_leads;
create trigger broker_leads_sync_preparation
before insert or update of raw_payload on public.broker_leads
for each row
execute function public.sync_broker_lead_preparation();

update public.broker_leads
set raw_payload = raw_payload
where jsonb_typeof(raw_payload -> 'preparation') = 'object';

comment on column public.broker_leads.journey_type is
  'Пользовательский маршрут до онлайн-заявки; необязательное поле';
comment on column public.broker_leads.journey_stage is
  'Этап подготовки, с которого клиент продолжает разбор';
comment on column public.broker_leads.journey_scenario_slug is
  'Стабильный slug сложного сценария без персональных данных';
comment on column public.broker_leads.preparation is
  'Очищенный структурированный объект preparation из raw_payload';
comment on column public.broker_leads.preparation_completed is
  'Добровольные пользовательские отметки уже выполненных проверок';
comment on column public.broker_leads.remaining_questions is
  'Что клиент считает непонятным или требующим дополнительной проверки';
comment on function public.sync_broker_lead_preparation() is
  'Извлекает необязательный preparation из raw_payload в отдельные CRM-поля';