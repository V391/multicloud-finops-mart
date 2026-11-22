-- Canonical tags per charge. Raw tag keys drift across teams and providers
-- (env / Environment / ENV, " org" with a leading space, "Project " with a trailing
-- one). Keys are matched on lower(trim(key)) against the tag_key_map seed; when a
-- charge carries two keys for the same canonical tag, the lower priority number wins.

with charges as (
    select charge_id, tags_json
    from {{ ref('stg_focus__charges') }}
    where tags_json is not null
),

key_values as (
    select
        charge_id,
        tags_json,
        unnest(json_keys(tags_json)) as raw_key
    from charges
),

mapped as (
    select
        kv.charge_id,
        m.canonical_key,
        m.priority,
        nullif(trim(json_extract_string(kv.tags_json, '$."' || kv.raw_key || '"')), '') as tag_value
    from key_values kv
    join {{ ref('tag_key_map') }} m
      on m.raw_key = lower(trim(kv.raw_key))
)

select
    charge_id,
    lower(arg_min(tag_value, priority) filter (where canonical_key = 'environment')) as environment,
    arg_min(tag_value, priority) filter (where canonical_key = 'owner')              as owner,
    arg_min(tag_value, priority) filter (where canonical_key = 'application')        as application
from mapped
where tag_value is not null
group by charge_id
