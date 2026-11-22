-- Ties the mart back to the raw file, per provider and charge category, for every
-- cost measure. billed_diff must be 0 (a singular test enforces it).
-- effective_vs_billed shows how far the two cost measures sit apart in the source.

with src as (
    select
        ProviderName                               as provider,
        lower(ChargeCategory)                      as charge_category,
        count(*)                                   as source_rows,
        sum(cast(BilledCost as double))            as source_billed,
        sum(cast(EffectiveCost as double))         as source_effective
    from {{ source('focus', 'focus_charges') }}
    group by all
),

mart as (
    select
        provider,
        charge_category,
        sum(charge_count)                          as mart_rows,
        sum(billed_cost)                           as mart_billed,
        sum(effective_cost)                        as mart_effective
    from {{ ref('fct_daily_cost') }}
    group by all
)

select
    coalesce(s.provider, m.provider)               as provider,
    coalesce(s.charge_category, m.charge_category) as charge_category,
    s.source_rows,
    m.mart_rows,
    round(s.source_billed, 4)                      as source_billed,
    round(m.mart_billed, 4)                        as mart_billed,
    round(coalesce(m.mart_billed, 0) - coalesce(s.source_billed, 0), 6)       as billed_diff,
    round(coalesce(m.mart_effective, 0) - coalesce(s.source_effective, 0), 6) as effective_diff,
    round(s.source_effective - s.source_billed, 4) as effective_vs_billed
from src s
full outer join mart m
  on s.provider is not distinct from m.provider
 and s.charge_category is not distinct from m.charge_category
