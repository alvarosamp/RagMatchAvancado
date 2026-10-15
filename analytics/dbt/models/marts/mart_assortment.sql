{{ config(pre_hook=["select set_config('app.current_tenant_id', '" ~ (env_var('MARKET_TENANT_ID') | int) ~ "', true)", "{{ replace_tenant_slice(this) }}"]) }}
select tenant_id, coalesce(category,'unknown') as metric_key, category,
    count(*) as demand_items, sum(total_value) as observed_value,
    count(*) filter (where coverage='covered') as covered_items,
    sum(total_value) filter (where coverage='no_suitable_product') as confirmed_gap_value,
    coalesce(sum(total_value) filter (where coverage='covered'),0) / nullif(sum(total_value),0) as demand_weighted_coverage,
    count(*) filter (where coverage in ('unassessed','pending_review')) as pending_items
from {{ ref('fact_opportunity_item') }}
where source='crm' and active and tenant_id={{ env_var('MARKET_TENANT_ID') | int }}
group by tenant_id, category
