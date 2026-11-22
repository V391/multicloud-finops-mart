-- One row per FOCUS charge, typed and normalized. No rows are dropped here:
-- every source row must survive so the marts can reconcile back to the source.

with src as (
    select * from {{ source('focus', 'focus_charges') }}
)

select
    Id                                              as charge_id,
    ProviderName                                    as provider,
    BillingAccountId                                as billing_account_id,
    SubAccountId                                    as sub_account_id,
    SubAccountName                                  as sub_account_name,
    BillingCurrency                                 as billing_currency,

    -- FOCUS values arrive in mixed case ("Usage" / "usage", "Usage-Based" / "Usage-based").
    lower(ChargeCategory)                           as charge_category,
    lower(ChargeFrequency)                          as charge_frequency,
    PricingCategory                                 as pricing_category,
    CommitmentDiscountCategory                      as commitment_discount_category,
    ChargeDescription                               as charge_description,

    ServiceCategory                                 as service_category,
    ServiceName                                     as service_name,
    RegionId                                        as region_id,
    ResourceId                                      as resource_id,
    ResourceType                                    as resource_type,

    cast(BillingPeriodStart as date)                as billing_period_start,
    cast(ChargePeriodStart as timestamp)            as charge_period_start,
    cast(ChargePeriodStart as date)                 as charge_date,

    cast(BilledCost as double)                      as billed_cost,
    cast(EffectiveCost as double)                   as effective_cost,
    try_cast(ListCost as double)                    as list_cost,
    try_cast(ContractedCost as double)              as contracted_cost,

    -- Some providers write the literal string 'NULL' or '{}' for "no tags".
    nullif(nullif(trim(Tags), 'NULL'), '{}')        as tags_json

from src
