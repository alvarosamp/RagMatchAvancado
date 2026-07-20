from sqlalchemy.orm import Session
from sqlalchemy import inspect, text

from app.db.models import Base
from app.db.session import engine
from app.logs.config import logger
from app.services.catalog_loader import load_switch_catalog
from app.vector.pgvector_store import ensure_pgvector_extension


def init_db(db: Session) -> dict:
    """
    Cria tabelas do portal principal e do CRM no mesmo banco.
    """
    import app.auth.models  # noqa: F401
    import app.crm.models  # noqa: F401
    import app.jobs.models  # noqa: F401

    try:
        ensure_pgvector_extension(db)
        Base.metadata.create_all(bind=engine)
        _ensure_job_enum_updates()
        _ensure_crm_schema_updates()
        _ensure_analysis_items_schema_updates()
        _ensure_products_schema_updates()
        _ensure_editais_schema_updates()
        _ensure_analysis_documents_schema_updates()
        logger.info("Tabelas do portal e do CRM criadas com sucesso.")

        inserted = load_switch_catalog(db)
        logger.info("Switches inseridos: %s", inserted)

        return {"tables_created": True, "switches_inserted": inserted}
    except Exception as exc:
        logger.error(f"Erro ao inicializar banco: {exc}")
        raise


def _ensure_crm_schema_updates() -> None:
    inspector = inspect(engine)
    _ensure_columns(
        inspector,
        "crm_notices",
        {
            "tor_id": "VARCHAR",
            "municipality_name": "VARCHAR",
            "proposal_link": "TEXT",
            "supplier_proposal_link": "TEXT",
            "address": "VARCHAR",
            "zipcode": "VARCHAR",
            "uasg": "VARCHAR",
            "state": "VARCHAR",
            "proposal_validity": "VARCHAR",
            "document_delivery_moment": "VARCHAR",
            "analysis_status": "VARCHAR",
            "analysis_mode": "VARCHAR",
            "analysis_confidence": "VARCHAR",
            "sales_status": "VARCHAR",
            "import_key": "VARCHAR",
        },
    )
    _ensure_columns(
        inspector,
        "crm_notice_products",
        {
            "lot": "VARCHAR",
            "product_code": "VARCHAR",
            "is_exclusive_epp": "BOOLEAN",
            "exclusive_epp_label": "VARCHAR",
            "warranty": "VARCHAR",
            "delivery_deadline": "VARCHAR",
            "bi_features": "JSON",
            "cost": "DOUBLE PRECISION",
            "reference_total_price": "DOUBLE PRECISION",
        },
    )
    _ensure_columns(
        inspector,
        "crm_catalog_products",
        {
            "keywords": "TEXT",
            "category": "VARCHAR",
        },
    )
    _ensure_indexes(
        [
            "CREATE INDEX IF NOT EXISTS ix_crm_notices_tenant_tor_id ON crm_notices (tenant_id, tor_id)",
            "CREATE INDEX IF NOT EXISTS ix_crm_notices_tenant_municipality ON crm_notices (tenant_id, municipality_name)",
        ]
    )

def _ensure_analysis_items_schema_updates() -> None:
    inspector = inspect(engine)
    _ensure_columns(
        inspector,
        "analysis_items",
        {
            "categoria": "VARCHAR",
            "uf": "VARCHAR",
            "lote_grupo": "VARCHAR",
            "garantia": "VARCHAR",
            "prazo_entrega": "VARCHAR",
            "exclusividade_me_epp_item": "VARCHAR",
            "risco_associado": "TEXT",
            "direcionamento_marca_tipo": "VARCHAR",
            "direcionamento_marca_justificativa": "TEXT",
            "has_direcionamento_marca": "BOOLEAN",
            "has_risco": "BOOLEAN",
            "caracteristicas_bi": "JSON",
        },
    )
    _ensure_indexes(
        [
            "CREATE INDEX IF NOT EXISTS ix_analysis_items_categoria ON analysis_items (categoria)",
            "CREATE INDEX IF NOT EXISTS ix_analysis_items_uf ON analysis_items (uf)",
            "CREATE INDEX IF NOT EXISTS ix_analysis_items_prazo_entrega ON analysis_items (prazo_entrega)",
        ]
    )


def _ensure_products_schema_updates() -> None:
    inspector = inspect(engine)
    _ensure_columns(
        inspector,
        "products",
        {
            "manufacturer": "VARCHAR",
            "is_competitor": "BOOLEAN DEFAULT FALSE",
        },
    )
    _ensure_indexes(
        [
            "CREATE INDEX IF NOT EXISTS ix_products_is_competitor ON products (is_competitor)",
        ]
    )


def _ensure_editais_schema_updates() -> None:
    inspector = inspect(engine)
    _ensure_columns(
        inspector,
        "editais",
        {
            "source_hash": "VARCHAR",
            "business_key": "VARCHAR",
            "status": "VARCHAR DEFAULT 'done'",
        },
    )
    _ensure_indexes(
        [
            "CREATE INDEX IF NOT EXISTS ix_editais_source_hash ON editais (source_hash)",
            "CREATE INDEX IF NOT EXISTS ix_editais_business_key ON editais (business_key)",
            "CREATE INDEX IF NOT EXISTS ix_editais_status ON editais (status)",
        ]
    )


def _ensure_analysis_documents_schema_updates() -> None:
    inspector = inspect(engine)
    _ensure_columns(
        inspector,
        "analysis_documents",
        {
            "business_key": "VARCHAR",
        },
    )
    _ensure_indexes(
        [
            "CREATE INDEX IF NOT EXISTS ix_analysis_documents_business_key ON analysis_documents (business_key)",
        ]
    )


def _ensure_job_enum_updates() -> None:
    """
    O SQLAlchemy Enum(JobType) gera um enum nativo no Postgres (tipo `jobtype`).
    Em bancos já criados, precisamos adicionar novos valores ao tipo para suportar
    novos jobs sem recriar a base.
    """
    statements = [
        "ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'CRM_NOTICE_MATCH'",
    ]
    with engine.begin() as connection:
        for statement in statements:
            try:
                connection.execute(text(statement))
            except Exception as exc:
                # Se o tipo ainda não existir (primeira execução) ou se o banco não for Postgres,
                # o create_all já cuidará; aqui é só um best-effort para bases existentes.
                logger.info("Skip enum update (%s): %s", statement, exc)


def _ensure_columns(inspector, table_name: str, columns: dict[str, str]) -> None:
    existing = {column["name"] for column in inspector.get_columns(table_name)}
    with engine.begin() as connection:
        for column_name, sql_type in columns.items():
            if column_name in existing:
                continue
            connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {sql_type}"))
            logger.info("Coluna adicionada: %s.%s", table_name, column_name)


def _ensure_indexes(statements: list[str]) -> None:
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
