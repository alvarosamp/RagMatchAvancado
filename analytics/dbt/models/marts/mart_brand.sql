{{ config(pre_hook=["select set_config('app.current_tenant_id', '" ~ (env_var('MARKET_TENANT_ID') | int) ~ "', true)", "{{ replace_tenant_slice(this) }}"]) }}
select tenant_id, source || ':' || coalesce(brand,'unknown') as metric_key, source,brand,
    count(*) as requested_items,sum(total_value) as requested_value
from {{ ref('fact_opportunity_item') }}
where active and tenant_id={{ env_var('MARKET_TENANT_ID') | int }}
group by tenant_id,source,brand
