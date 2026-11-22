-- Attribution gaps: usage cost that showback cannot assign to an owner or an
-- environment, by provider and service. This is the list to fix before chargeback.

select
    provider,
    service_name,
    sum(billed_cost)                                                      as usage_cost,
    sum(billed_cost) filter (where owner is null)                         as no_owner_cost,
    sum(billed_cost) filter (where environment is null)                   as no_environment_cost,
    sum(billed_cost) filter (where owner is null and environment is null and application is null) as untagged_cost,
    round(sum(billed_cost) filter (where owner is null) / nullif(sum(billed_cost), 0), 4) as no_owner_share
from {{ ref('fct_daily_cost') }}
where charge_category = 'usage'
group by all
