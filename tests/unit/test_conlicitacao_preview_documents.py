import json

from app.integrations.conlicitacao.lab import preview_documents


def test_preview_hides_signed_urls_and_preserves_download_indexes():
    source = {"id": 123, "orgao": {}, "documento": [
        {"filename": "vazio.pdf", "url": ""},
        {"filename": "edital.pdf", "url": "/download?auth=provider-secret"},
    ]}
    preview = preview_documents(source)

    assert preview == [{"filename": "edital.pdf", "index": 1}]
    assert "provider-secret" not in json.dumps(preview)
