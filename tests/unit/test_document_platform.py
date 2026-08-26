import pytest
from types import SimpleNamespace
from fastapi import HTTPException

from app.db.models import DocumentSignatureStatus
from app.services import document_files as document_file_service

from app.services.document_platform import (
    build_document_business_key,
    normalize_document_payload,
    resolve_document_schema,
    validate_document_payload,
)


def test_edital_usa_schema_padrao_e_preserva_outro():
    payload = {
        "n_interno": "PE-12-2026",
        "edital": {"numero_pregao": "12/2026", "orgao": "Prefeitura X"},
        "itens_elegiveis": [
            {
                "numero_item_edital": "10",
                "categoria": "Outro",
                "descricao_original": "Equipamento especial",
            }
        ],
    }

    schema = resolve_document_schema("edital")
    normalized = normalize_document_payload("edital", payload)

    assert schema.name == "edital"
    assert schema.version == "7.4"
    assert normalized["itens_elegiveis"][0]["categoria"] == "Outro"


def test_edital_sem_identificacao_nao_avanca():
    schema = resolve_document_schema("edital")

    with pytest.raises(HTTPException) as exc:
        validate_document_payload("edital", {"edital": {}, "itens_elegiveis": []}, schema)

    assert exc.value.status_code == 422


def test_datasheet_tor_gera_business_key_estavel():
    schema = resolve_document_schema("datasheet_tor")
    payload = {
        "produto": {
            "fabricante": "TP-Link",
            "modelo": "TL-SG3210",
            "part_number": "SG3210",
        }
    }

    first = build_document_business_key("datasheet_tor", payload, schema)
    second = build_document_business_key("datasheet_tor", dict(payload), schema)

    assert first == second
    assert first.startswith("datasheet_tor|meta|")


class _Query:
    def __init__(self, result):
        self.result = result

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.result


class _Db:
    def __init__(self, query_results):
        self.query_results = list(query_results)
        self.added = []

    def query(self, *args, **kwargs):
        return _Query(self.query_results.pop(0))

    def add(self, value):
        self.added.append(value)


class _Field:
    def __eq__(self, other):
        return other


class _SignatureRequest:
    tenant_id = _Field()
    document_id = _Field()
    status = _Field()

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.status = DocumentSignatureStatus.PENDING
        self.requester_notification_dismissed = False


class _User:
    id = _Field()
    tenant_id = _Field()


def test_assinatura_mantem_vinculo_do_edital_e_notifica_solicitante(monkeypatch):
    original = SimpleNamespace(
        id="original",
        title="Contrato social",
        category="Jurídico",
        crm_notice_id="edital-1",
        edital_id=None,
        expires_at=None,
        status="active",
    )
    signer = SimpleNamespace(id=22)
    db = _Db([signer, None])
    monkeypatch.setattr(document_file_service, "User", _User)
    monkeypatch.setattr(document_file_service, "DocumentSignatureRequest", _SignatureRequest)
    monkeypatch.setattr(document_file_service, "get_tenant_document_file", lambda *args, **kwargs: original)

    request = document_file_service.create_signature_request(
        db,
        tenant_id=1,
        document_id=original.id,
        requester_id=11,
        signer_id=signer.id,
        message="Assine e reenvie o PDF.",
    )

    assert request.document_id == original.id
    assert request.status == DocumentSignatureStatus.PENDING
    assert original.status == "signature_pending"
    request.document = original

    signed_file = SimpleNamespace(id="signed-file")
    stored_payload = {}
    monkeypatch.setattr(document_file_service, "get_tenant_signature_request", lambda *args, **kwargs: request)

    def store_signed(*args, **kwargs):
        stored_payload.update(kwargs)
        return signed_file

    monkeypatch.setattr(document_file_service, "store_document_file", store_signed)
    completed = document_file_service.complete_signature_request(
        db,
        tenant_id=1,
        request_id=request.id,
        signer_id=signer.id,
        fileobj=SimpleNamespace(),
        original_filename="contrato-assinado.pdf",
        content_type="application/pdf",
    )

    assert completed.status == DocumentSignatureStatus.SIGNED
    assert completed.signed_document_id == "signed-file"
    assert completed.requester_notification_dismissed is False
    assert original.status == "signed"
    assert stored_payload["crm_notice_id"] == "edital-1"
    assert stored_payload["parent_document_id"] == original.id
    assert stored_payload["status_value"] == "signed_result"


def test_assinatura_pendente_impede_solicitacao_duplicada(monkeypatch):
    original = SimpleNamespace(id="original", status="active")
    signer = SimpleNamespace(id=22)
    db = _Db([signer, SimpleNamespace(id="pending")])
    monkeypatch.setattr(document_file_service, "User", _User)
    monkeypatch.setattr(document_file_service, "DocumentSignatureRequest", _SignatureRequest)
    monkeypatch.setattr(document_file_service, "get_tenant_document_file", lambda *args, **kwargs: original)

    with pytest.raises(HTTPException) as exc:
        document_file_service.create_signature_request(
            db,
            tenant_id=1,
            document_id=original.id,
            requester_id=11,
            signer_id=signer.id,
        )

    assert exc.value.status_code == 400
    assert original.status == "active"
