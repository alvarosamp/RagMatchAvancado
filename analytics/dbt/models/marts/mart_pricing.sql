{{ config(pre_hook=["select set_config('app.current_tenant_id', '" ~ (env_var('MARKET_TENANT_ID') | int) ~ "', true)", "{{ replace_tenant_slice(this) }}"]) }}
select tenant_id, md5(jsonb_build_array(product_id,unit,currency,state,price_type)::text) as metric_key,
    product_id,unit,currency,state,price_type,count(*) as sample,
    percentile_cont(0.25) within group (order by unit_price) as p25,
    percentile_cont(0.5) within group (order by unit_price) as median_price,
    percentile_cont(0.75) within group (order by unit_price) as p75
from {{ ref('fact_price_observation') }}
where active and product_id is not null and unit is not null and unit_price>0
    and tenant_id={{ env_var('MARKET_TENANT_ID') | int }}
group by tenant_id,product_id,unit,currency,state,price_type
