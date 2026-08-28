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
        _ensure_opportunity_decisions_schema_updates()
        _ensure_pncp_radar_items_schema_updates()
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
            "bid_number": "VARCHAR",
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
            "decision_recommendation": "VARCHAR",
            "decision_score": "INTEGER",
            "decision_risk_score": "INTEGER",
            "decision_intelligence": "JSON",
            "bi_item_summary": "TEXT",
            "bi_criterion": "VARCHAR",
            "bi_interval": "VARCHAR",
            "bi_exclusivity": "VARCHAR",
            "bi_risk_identified": "VARCHAR",
            "bi_risk_operational": "TEXT",
            "bi_risk_documental": "TEXT",
            "sales_status": "VARCHAR",
            "import_key": "VARCHAR",
            "import_batch_id": "INTEGER",
            "analysis_document_id": "INTEGER",
        },
    )
    _ensure_columns(
        inspector,
        "document_files",
        {
            "expires_at": "TIMESTAMP",
            "catalog_product_id": "VARCHAR(36)",
            "is_repository_signed_archive": "BOOLEAN NOT NULL DEFAULT FALSE",
        },
    )
    _ensure_columns(
        inspector,
        "document_signature_requests",
        {
            "signed_document_id": "VARCHAR(36)",
            "signer_notification_dismissed": "BOOLEAN NOT NULL DEFAULT FALSE",
            "requester_notification_dismissed": "BOOLEAN NOT NULL DEFAULT FALSE",
            "archive_signed_result": "BOOLEAN NOT NULL DEFAULT TRUE",
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
            "category": "VARCHAR",
            "technical_characteristics": "TEXT",
            "risk_associated": "TEXT",
            "brand_direction_exists": "BOOLEAN",
            "brand_direction_model": "VARCHAR",
            "brand_direction_type": "VARCHAR",
            "brand_direction_justification": "TEXT",
            "bi_features": "JSON",
            "bi_feature_quantidade_portas": "VARCHAR",
            "bi_feature_portas_acesso": "VARCHAR",
            "bi_feature_gerenciamento": "VARCHAR",
            "bi_feature_alimentacao_poe": "VARCHAR",
            "bi_feature_uplinks": "VARCHAR",
            "bi_feature_camada": "VARCHAR",
            "bi_feature_tecnologia_wifi": "VARCHAR",
            "bi_feature_alimentacao": "VARCHAR",
            "bi_feature_ambiente": "VARCHAR",
            "bi_feature_formato": "VARCHAR",
            "bi_feature_velocidade": "VARCHAR",
            "bi_feature_tipo_meio": "VARCHAR",
            "bi_feature_alcance": "VARCHAR",
            "raw_payload": "JSON",
            "cost": "DOUBLE PRECISION",
            "reference_total_price": "DOUBLE PRECISION",
            "selected_for_dispute": "BOOLEAN NOT NULL DEFAULT TRUE",
            "catalog_match_source": "VARCHAR",
            "catalog_match_confirmed_by": "INTEGER",
            "catalog_match_confirmed_at": "TIMESTAMP",
            "catalog_match_model_version": "VARCHAR",
            "catalog_match_notes": "TEXT",
            "catalog_lpu_version": "VARCHAR",
        },
    )
    _ensure_columns(
        inspector,
        "crm_notice_documents",
        {
            "source_url": "TEXT",
            "source_kind": "VARCHAR",
            "attached_document_file_id": "VARCHAR(36)",
        },
    )
    _ensure_columns(
        inspector,
        "crm_catalog_products",
        {
            "keywords": "TEXT",
            "category": "VARCHAR",
            "min_price": "DOUBLE PRECISION",
            "manufacturer_part_number": "VARCHAR",
            "lpu_version": "VARCHAR",
            "lpu_drive_url": "TEXT",
            "supplier_name": "VARCHAR",
            "datasheet_url": "TEXT",
            "certificate_url": "TEXT",
            "equivalent_skus": "TEXT",
        },
    )
    _ensure_indexes(
        [
            "CREATE INDEX IF NOT EXISTS ix_crm_notices_tenant_tor_id ON crm_notices (tenant_id, tor_id)",
            "CREATE INDEX IF NOT EXISTS ix_crm_notices_tenant_municipality ON crm_notices (tenant_id, municipality_name)",
            "CREATE INDEX IF NOT EXISTS ix_crm_notices_import_batch_id ON crm_notices (import_batch_id)",
            "CREATE INDEX IF NOT EXISTS ix_crm_notices_analysis_document_id ON crm_notices (analysis_document_id)",
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
            "caracteristicas_tecnicas": "TEXT",
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


def _ensure_opportunity_decisions_schema_updates() -> None:
    inspector = inspect(engine)
    if "opportunity_decisions" not in inspector.get_table_names():
        return
    _ensure_columns(
        inspector,
        "opportunity_decisions",
        {
            "score": "INTEGER",
            "priority": "VARCHAR",
            "reason": "TEXT",
            "notice_snapshot": "JSON",
            "crm_notice_id": "VARCHAR",
            "import_job_id": "VARCHAR",
            "pncp_files_count": "INTEGER DEFAULT 0",
            "import_error": "TEXT",
            "updated_at": "TIMESTAMP",
        },
    )
    _ensure_indexes(
        [
            "CREATE INDEX IF NOT EXISTS ix_opportunity_decisions_tenant_id ON opportunity_decisions (tenant_id)",
            "CREATE INDEX IF NOT EXISTS ix_opportunity_decisions_id_pncp ON opportunity_decisions (id_pncp)",
            "CREATE INDEX IF NOT EXISTS ix_opportunity_decisions_decision ON opportunity_decisions (decision)",
            "CREATE INDEX IF NOT EXISTS ix_opportunity_decisions_crm_notice_id ON opportunity_decisions (crm_notice_id)",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_opportunity_decisions_tenant_id_pncp ON opportunity_decisions (tenant_id, id_pncp)",
        ]
    )


def _ensure_pncp_radar_items_schema_updates() -> None:
    inspector = inspect(engine)
    if "pncp_radar_items" not in inspector.get_table_names():
        return
    _ensure_columns(
        inspector,
        "pncp_radar_items",
        {
            "id_pncp": "VARCHAR",
            "notice": "JSON",
            "search_terms": "VARCHAR",
            "status": "VARCHAR DEFAULT 'active'",
            "first_seen_at": "TIMESTAMP",
            "last_seen_at": "TIMESTAMP",
        },
    )
    _ensure_indexes(
        [
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_pncp_radar_items_id_pncp ON pncp_radar_items (id_pncp)",
            "CREATE INDEX IF NOT EXISTS ix_pncp_radar_items_status ON pncp_radar_items (status)",
            "CREATE INDEX IF NOT EXISTS ix_pncp_radar_items_last_seen_at ON pncp_radar_items (last_seen_at)",
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
            "import_batch_id": "INTEGER",
            "source_path": "VARCHAR",
            "storage_key": "VARCHAR",
            "analysis_only": "BOOLEAN DEFAULT FALSE",
        },
    )
    _ensure_indexes(
        [
            "CREATE INDEX IF NOT EXISTS ix_editais_source_hash ON editais (source_hash)",
            "CREATE INDEX IF NOT EXISTS ix_editais_business_key ON editais (business_key)",
            "CREATE INDEX IF NOT EXISTS ix_editais_status ON editais (status)",
            "CREATE INDEX IF NOT EXISTS ix_editais_import_batch_id ON editais (import_batch_id)",
            "CREATE INDEX IF NOT EXISTS ix_editais_storage_key ON editais (storage_key)",
            "CREATE INDEX IF NOT EXISTS ix_editais_analysis_only ON editais (analysis_only)",
        ]
    )


def _ensure_analysis_documents_schema_updates() -> None:
    inspector = inspect(engine)
    _ensure_columns(
        inspector,
        "analysis_documents",
        {
            "schema_name": "VARCHAR",
            "schema_version": "VARCHAR",
            "import_batch_id": "INTEGER",
            "business_key": "VARCHAR",
            "source_path": "VARCHAR",
            "analysis_only": "BOOLEAN DEFAULT FALSE",
            "crm_notice_id": "VARCHAR",
        },
    )
    _ensure_indexes(
        [
            "CREATE INDEX IF NOT EXISTS ix_analysis_documents_schema_name ON analysis_documents (schema_name)",
            "CREATE INDEX IF NOT EXISTS ix_analysis_documents_schema_version ON analysis_documents (schema_version)",
            "CREATE INDEX IF NOT EXISTS ix_analysis_documents_import_batch_id ON analysis_documents (import_batch_id)",
            "CREATE INDEX IF NOT EXISTS ix_analysis_documents_business_key ON analysis_documents (business_key)",
            "CREATE INDEX IF NOT EXISTS ix_analysis_documents_analysis_only ON analysis_documents (analysis_only)",
            "CREATE INDEX IF NOT EXISTS ix_analysis_documents_crm_notice_id ON analysis_documents (crm_notice_id)",
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
