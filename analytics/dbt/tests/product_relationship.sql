select f.id from {{ source('ledger','facts') }} f
left join {{ source('ledger','entities') }} p on f.tenant_id=p.tenant_id and f.product_id=p.id and p.kind='product'
where f.product_id is not null and p.id is null
