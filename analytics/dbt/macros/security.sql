{% macro generate_schema_name(custom_schema_name, node) -%}
{{ custom_schema_name | trim if custom_schema_name else target.schema }}
{%- endmacro %}

{% macro secure_mart(relation) %}
alter table {{ relation }} enable row level security;
alter table {{ relation }} force row level security;
drop policy if exists tenant_isolation on {{ relation }};
create policy tenant_isolation on {{ relation }}
using (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::integer)
with check (tenant_id = nullif(current_setting('app.current_tenant_id', true), '')::integer)
{% endmacro %}

{% macro replace_tenant_slice(relation) %}
{% if is_incremental() %}
delete from {{ relation }} where tenant_id = {{ env_var('MARKET_TENANT_ID') | int }}
{% else %}
select 1
{% endif %}
{% endmacro %}
