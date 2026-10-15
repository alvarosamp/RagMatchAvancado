{{ config(pre_hook=["select set_config('app.current_tenant_id', '" ~ (env_var('MARKET_TENANT_ID') | int) ~ "', true)", "{{ replace_tenant_slice(this) }}"]) }}
select s.tenant_id,s.id as metric_key,s.name,s.tax_id,
    count(p.id) as purchase_lines,sum(p.total_value) as committed_purchase_value
from {{ ref('dim_supplier') }} s
left join {{ ref('fact_purchase_line') }} p on p.tenant_id=s.tenant_id and p.supplier_id=s.id and p.active
where s.active and s.tenant_id={{ env_var('MARKET_TENANT_ID') | int }}
    and (coalesce(s.attributes->>'supplier_role_verified','true') <> 'false'
         or exists (select 1 from {{ ref('fact_purchase_line') }} evidence where evidence.tenant_id=s.tenant_id and evidence.supplier_id=s.id and evidence.active)
         or exists (select 1 from {{ source('ledger','product_suppliers') }} relation where relation.tenant_id=s.tenant_id and relation.supplier_id=s.id and relation.active))
group by s.tenant_id,s.id,s.name,s.tax_id
