-- Daily usage cost per provider and service on a complete date spine, so a day
-- with no usage reads as 0 instead of going missing. Usage only: credits,
-- purchases and tax are kept out so a credit day does not look like a cost drop.
-- This is the input to the anomaly check.

with usage as (
    select charge_date, provider, coalesce(service_name, '(none)') as service_name, sum(billed_cost) as usage_cost
    from {{ ref('fct_daily_cost') }}
    where charge_category = 'usage'
    group by all
),

bounds as (
    select provider, min(charge_date) as d0, max(charge_date) as d1
    from usage
    group by provider
),

spine as (
    select b.provider, s.service_name, cast(g.d as date) as charge_date
    from bounds b
    join (select distinct provider, service_name from usage) s using (provider)
    cross join lateral generate_series(b.d0, b.d1, interval 1 day) as g(d)
)

select
    s.charge_date,
    s.provider,
    s.service_name,
    coalesce(u.usage_cost, 0) as usage_cost
from spine s
left join usage u using (charge_date, provider, service_name)
