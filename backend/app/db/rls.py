"""Tenant-owned tables protected by PostgreSQL row-level security."""

CRM_RLS_TABLES = (
    "crm_bid_assist_logs",
    "crm_catalog_product_datasheets",
    "crm_catalog_products",
    "crm_checklist_template_items",
    "crm_checklist_templates",
    "crm_item_fulfillment_history",
    "crm_item_fulfillment_invoices",
    "crm_item_fulfillments",
    "crm_notice_competitors",
    "crm_notice_documents",
    "crm_notice_history",
    "crm_notice_item_results",
    "crm_notice_product_datasheets",
    "crm_notice_product_matches",
    "crm_notice_products",
    "crm_notice_sessions",
    "crm_notices",
    "crm_organs",
    "crm_portals",
    "crm_post_auction_transitions",
)

OTHER_TENANT_RLS_TABLES = (
    "analysis_documents",
    "document_files",
    "document_schemas",
    "document_signature_requests",
    "import_batches",
    "opportunity_decisions",
    "tenders",
    "tender_sync_checkpoints",
    "user_role_audit",
)

BLING_RLS_TABLES = ("bling_tenant_integrations",)

RLS_TABLES = (
    "editais",
    "jobs",
    *CRM_RLS_TABLES,
    *OTHER_TENANT_RLS_TABLES,
    *BLING_RLS_TABLES,
)
