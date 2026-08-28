from types import SimpleNamespace

from app.services import document_files


def test_catalog_datasheet_serialization_exposes_product_and_version():
    document = SimpleNamespace(
        id="datasheet-v2", title="Datasheet - Switch", original_filename="switch.pdf",
        content_type="application/pdf", size_bytes=123, category="Datasheet", status="active",
        version=2, parent_document_id="datasheet-v1", catalog_product_id="product-1",
        crm_notice_id=None, edital_id=None, uploaded_by=4, notes=None, expires_at=None,
        created_at=None, updated_at=None,
    )

    payload = document_files.serialize_document_file(document)

    assert payload["catalog_product_id"] == "product-1"
    assert payload["version"] == 2
    assert payload["download_url"].endswith("/datasheet-v2/download")


def test_datasheet_filename_is_sanitized_before_storage():
    assert document_files._safe_filename("../../datasheet.pdf") == "datasheet.pdf"
