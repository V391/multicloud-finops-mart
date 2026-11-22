-- Fails if any provider x charge category in the mart does not tie back to the
-- raw source on row count, billed cost or effective cost.
select *
from {{ ref('mart_reconciliation') }}
where coalesce(source_rows, -1) <> coalesce(mart_rows, -1)
   or abs(billed_diff) > {{ var('reconcile_tolerance') }}
   or abs(effective_diff) > {{ var('reconcile_tolerance') }}
