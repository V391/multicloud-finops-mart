-- The date spine may add zero rows but must not add or lose usage cost.
with a as (select sum(usage_cost) as v from {{ ref('mart_daily_usage') }}),
     b as (select sum(billed_cost) as v from {{ ref('fct_daily_cost') }} where charge_category = 'usage')
select a.v as spine_total, b.v as fact_total
from a, b
where abs(a.v - b.v) > {{ var('reconcile_tolerance') }}
