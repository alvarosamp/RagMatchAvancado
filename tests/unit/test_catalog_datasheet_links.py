from pathlib import Path
from types import SimpleNamespace

from app.crm.models import CrmChecklistStatus
from app.services import catalog_datasheets
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


class _Query:
    def __init__(self, result):
        self.result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.result


class _Db:
    def __init__(self, query_result=None):
        self.query_result = query_result

    def query(self, *args, **kwargs):
        return _Query(self.query_result)

    def get(self, *args, **kwargs):
        return None


class _Field:
    def __eq__(self, other):
        return other


class _DocumentFile:
    tenant_id = _Field()
    generation_key = _Field()


def test_catalog_datasheet_becomes_the_notice_checklist_attachment(monkeypatch):
    source_path = Path(__file__)
    datasheet = SimpleNamespace(
        id="datasheet-2",
        storage_path=str(source_path),
        uploaded_by=7,
        original_filename="switch.pdf",
        content_type="application/pdf",
    )
    link = SimpleNamespace(
        tenant_id=3,
        notice_id="notice-1",
        notice_product_id="item-1",
        catalog_product_id="product-1",
        catalog_datasheet_id=None,
        document_file_id=None,
    )
    checklist_document = SimpleNamespace(
        name="Datasheet - Switch",
        category="Datasheets de produtos",
        notes="Produto do catalogo: Switch.",
        attached_document_file_id=None,
        source_kind=None,
        source_url=None,
        status=CrmChecklistStatus.PENDING,
    )
    stored = SimpleNamespace(id="notice-file-1", catalog_product_id=None)
    store_payload = {}

    def store_document(*args, **kwargs):
        store_payload.update(kwargs)
        return stored

    monkeypatch.setattr(catalog_datasheets, "DocumentFile", _DocumentFile)
    monkeypatch.setattr(document_files, "store_document_file", store_document)

    result = catalog_datasheets.attach_catalog_datasheet_to_notice_document(
        _Db(), link=link, document=checklist_document, datasheet=datasheet,
    )

    assert result is stored
    assert link.catalog_datasheet_id == datasheet.id
    assert link.document_file_id == stored.id
    assert checklist_document.attached_document_file_id == stored.id
    assert checklist_document.status == CrmChecklistStatus.READY
    assert checklist_document.source_kind == "catalog_datasheet"
    assert stored.catalog_product_id == "product-1"
    assert store_payload["crm_notice_id"] == "notice-1"
    assert store_payload["generation_key"] == "catalog-datasheet:item-1:datasheet-2"


def test_resync_does_not_replace_an_already_signed_checklist_attachment(monkeypatch):
    datasheet = SimpleNamespace(id="datasheet-2")
    materialized = SimpleNamespace(id="notice-file-1", generation_key="catalog-datasheet:item-1:datasheet-2")
    link = SimpleNamespace(
        tenant_id=3,
        notice_id="notice-1",
        notice_product_id="item-1",
        catalog_product_id="product-1",
        catalog_datasheet_id="datasheet-2",
        document_file_id="notice-file-1",
    )
    checklist_document = SimpleNamespace(
        attached_document_file_id="signed-result-1",
        source_kind="catalog_datasheet",
        source_url=None,
        status=CrmChecklistStatus.READY,
    )

    monkeypatch.setattr(catalog_datasheets, "DocumentFile", _DocumentFile)
    catalog_datasheets.attach_catalog_datasheet_to_notice_document(
        _Db(materialized), link=link, document=checklist_document, datasheet=datasheet,
    )

    assert checklist_document.attached_document_file_id == "signed-result-1"
