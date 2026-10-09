select tenant_id from {{ ref('mart_assortment') }}
where tenant_id <> {{ env_var('MARKET_TENANT_ID') | int }}
