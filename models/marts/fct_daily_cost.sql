-- Daily cost fact. Grain: one row per day x provider x account x service x region
-- x charge category x pricing category x canonical tags. Every charge lands in
-- exactly one row, so totals here must equal the raw source (see tests/).

with charges as (
    select
        c.*,
        t.environment,
        t.owner,
        t.application
    from {{ ref('stg_focus__charges') }} c
    left join {{ ref('int_charge_tags') }} t using (charge_id)
),

grouped as (
    select
        charge_date,
        provider,
        billing_account_id,
        sub_account_id,
        service_category,
        service_name,
        region_id,
        charge_category,
        pricing_category,
        environment,
        owner,
        application,
        count(*)                    as charge_count,
        sum(billed_cost)            as billed_cost,
        sum(effective_cost)         as effective_cost,
        sum(list_cost)              as list_cost,
        sum(contracted_cost)        as contracted_cost
    from charges
    group by all
)

select
    md5(concat_ws('|',
        charge_date, provider, billing_account_id, sub_account_id, service_category,
        service_name, region_id, charge_category, pricing_category,
        coalesce(environment, '~'), coalesce(owner, '~'), coalesce(application, '~'),
        -- concat_ws skips nulls, so mark them to keep keys distinct
        case when sub_account_id is null then 'n' else 'v' end,
        case when region_id is null then 'n' else 'v' end,
        case when service_name is null then 'n' else 'v' end,
        case when service_category is null then 'n' else 'v' end,
        case when pricing_category is null then 'n' else 'v' end,
        case when billing_account_id is null then 'n' else 'v' end
    )) as daily_cost_key,
    *
from grouped
