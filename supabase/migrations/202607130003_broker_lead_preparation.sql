-- Структурированный контекст подготовки онлайн-заявки.
--
-- Миграция не меняет публичный schema_version=1. Edge Function продолжает
-- сохранять исходный raw_payload, а серверный trigger извлекает необязательный
-- объект preparation в отдельные CRM-поля по белому списку.

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
  v_raw jsonb;
  v_preparation jsonb;
  v_checks jsonb := '[]'::jsonb;
  v_labels jsonb := '[]'::jsonb;
  v_item text;
  v_context_version integer := 1;
  v_journey_type text;
  v_journey_stage text;
  v_scenario_slug text;
  v_remaining_questions text;
begin
  v_raw := case
    when jsonb_typeof(new.raw_payload -> 'preparation') = 'object'
      then new.raw_payload -> 'preparation'
    else '{}'::jsonb
  end;

  if jsonb_typeof(v_raw -> 'completed_checks') = 'array' then
    for v_item in
      select value
      from jsonb_array_elements_text(v_raw -> 'completed_checks')
      limit 4
    loop
      v_item := left(trim(v_item), 80);
      if v_item in ('diagnosis', 'finances', 'documents', 'next_step')
         and not (v_checks @> jsonb_build_array(v_item)) then
        v_checks := v_checks || jsonb_build_array(v_item);
      end if;
    end loop;
  end if;

  if jsonb_typeof(v_raw -> 'completed_labels') = 'array' then
    for v_item in
      select value
      from jsonb_array_elements_text(v_raw -> 'completed_labels')
      limit 4
    loop
      v_item := left(trim(regexp_replace(v_item, '\s+', ' ', 'g')), 180);
      if v_item <> '' and not (v_labels @> jsonb_build_array(v_item)) then
        v_labels := v_labels || jsonb_build_array(v_item);
      end if;
    end loop;
  end if;

  if coalesce(v_raw ->> 'context_version', '') ~ '^\d{1,3}$' then
    v_context_version := least(greatest((v_raw ->> 'context_version')::integer, 1), 100);
  end if;

  v_journey_type := nullif(left(trim(regexp_replace(coalesce(v_raw ->> 'journey_type', ''), '\s+', ' ', 'g')), 160), '');
  v_journey_stage := nullif(left(trim(regexp_replace(coalesce(v_raw ->> 'journey_stage', ''), '\s+', ' ', 'g')), 200), '');
  v_scenario_slug := nullif(left(trim(coalesce(v_raw ->> 'scenario_slug', '')), 160), '');
  v_remaining_questions := nullif(left(trim(coalesce(v_raw ->> 'remaining_questions', '')), 700), '');

  if v_scenario_slug not in (
    'otkazali-v-ipoteke',
    'ipoteka-s-plohoy-kreditnoy-istoriey',
    'ipoteka-bez-oficialnogo-dohoda',
    'ipoteka-bez-pervonachalnogo-vznosa'
  ) then
    v_scenario_slug := null;
  end if;

  v_preparation := jsonb_build_object(
    'context_version', v_context_version,
    'active', coalesce(v_raw ->> 'active', 'false') = 'true' and v_scenario_slug is not null,
    'journey_type', coalesce(v_journey_type, ''),
    'journey_stage', coalesce(v_journey_stage, ''),
    'scenario_slug', coalesce(v_scenario_slug, ''),
    'completed_checks', v_checks,
    'completed_labels', v_labels,
    'remaining_questions', coalesce(v_remaining_questions, '')
  );

  new.preparation := v_preparation;
  new.preparation_completed := v_labels;
  new.journey_type := v_journey_type;
  new.journey_stage := v_journey_stage;
  new.journey_scenario_slug := v_scenario_slug;
  new.remaining_questions := v_remaining_questions;

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
  'Очищенный по белому списку структурированный объект preparation из raw_payload';
comment on column public.broker_leads.preparation_completed is
  'Добровольные пользовательские отметки уже выполненных проверок';
comment on column public.broker_leads.remaining_questions is
  'Что клиент считает непонятным или требующим дополнительной проверки';
comment on function public.sync_broker_lead_preparation() is
  'Извлекает и очищает необязательный preparation из raw_payload в отдельные CRM-поля';