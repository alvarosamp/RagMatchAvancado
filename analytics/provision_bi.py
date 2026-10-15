"""Generate reviewable SQL for a fixed-tenant, read-only BI connection.

No SQL is executed and no passwords are written. Apply the generated SQL as a
migration administrator, then set the login password through the secret store.
"""

import argparse

TABLES = {
    "core": ["entities", "product_suppliers", "facts"],
    "mart": ["model_runs"],
}


def provision_sql(tenant_id: int) -> str:
    if tenant_id <= 0:
        raise ValueError("Tenant must be positive.")
    owner, reader, schema = (
        f"market_bi_owner_{tenant_id}",
        f"market_bi_{tenant_id}",
        f"bi_tenant_{tenant_id}",
    )
    statements = [
        "BEGIN;",
        f"CREATE ROLE {owner} NOLOGIN NOSUPERUSER NOBYPASSRLS;",
        f"CREATE ROLE {reader} LOGIN NOSUPERUSER NOBYPASSRLS;",
        f"CREATE SCHEMA {schema} AUTHORIZATION {owner};",
        f"REVOKE ALL ON SCHEMA {schema} FROM PUBLIC;",
        f"GRANT USAGE ON SCHEMA {schema} TO {reader};",
    ]
    for source_schema, tables in TABLES.items():
        statements.append(f"GRANT USAGE ON SCHEMA {source_schema} TO {owner};")
        for table in tables:
            relation = f"{source_schema}.{table}"
            statements.extend(
                [
                    f"GRANT SELECT ON {relation} TO {owner};",
                    f"CREATE POLICY bi_read_{tenant_id} ON {relation} FOR SELECT TO {owner} USING (tenant_id = {tenant_id});",
                    f"CREATE VIEW {schema}.{table} WITH (security_barrier=true) AS SELECT * FROM {relation} WHERE tenant_id = {tenant_id};",
                    f"ALTER VIEW {schema}.{table} OWNER TO {owner};",
                    f"GRANT SELECT ON {schema}.{table} TO {reader};",
                ]
            )
    statements.extend(
        ["COMMIT;", f"-- Connect Metabase with {reader}; expose only schema {schema}."]
    )
    return "\n".join(statements)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", type=int, required=True)
    print(provision_sql(parser.parse_args().tenant))
