"""Verify bytes on disk, persisted versions and isolation through HTTP."""
from io import BytesIO
from zipfile import ZipFile

import pytest


@pytest.fixture
def document(api, seed, unique):
    content = b"%PDF-1.4\nQA document content\n%%EOF\n"
    response = api.post("/documents/files", files={"file": (f"qa-{unique}.pdf", content, "application/pdf")},
                        data={"title": f"QA document {unique}", "crm_notice_id": seed["tenants"]["alpha"]["notice_id"]})
    assert response.status_code == 200, response.text
    data = response.json()
    yield data, content
    response = api.request("DELETE", f"/documents/files/{data['id']}")
    assert response.status_code in {204, 404}, response.text


def test_upload_download_and_metadata_are_persisted(api, document, admin_db):
    data, content = document
    response = api.get(f"/documents/files/{data['id']}/download")
    assert response.status_code == 200 and response.content == content
    assert "attachment" in response.headers["Content-Disposition"]
    with admin_db.cursor() as cursor:
        cursor.execute("SELECT size_bytes,version FROM document_files WHERE id=%s", (data["id"],))
        assert cursor.fetchone() == (len(content), 1)


def test_new_document_version_preserves_original_bytes(api, document):
    data, original = document
    content = b"%PDF-1.4\nQA revised document\n%%EOF\n"
    response = api.post(f"/documents/files/{data['id']}/versions", files={"file": ("revised.pdf", content, "application/pdf")})
    assert response.status_code == 200, response.text
    revision = response.json()
    try:
        assert revision["version"] == 2
        assert revision["parent_document_id"] == data["id"]
        assert api.get(f"/documents/files/{revision['id']}/download").content == content
        assert api.get(f"/documents/files/{data['id']}/download").content == original
    finally:
        assert api.request("DELETE", f"/documents/files/{revision['id']}").status_code == 204


@pytest.mark.parametrize("operation", ["download", "versions", "attach", "delete"])
def test_other_company_cannot_access_or_modify_uploaded_file(clients, document, operation, seed):
    data, _ = document
    client = clients("beta")
    path = f"/documents/files/{data['id']}"
    if operation == "download":
        response = client.get(path + "/download")
    elif operation == "versions":
        response = client.post(path + "/versions", files={"file": ("forbidden.pdf", b"foreign", "application/pdf")})
    elif operation == "attach":
        response = client.post(path + "/attach", json={"crm_notice_id": seed["tenants"]["beta"]["notice_id"]})
    else:
        response = client.request("DELETE", path)
    assert response.status_code == 404, response.text


def test_notice_zip_contains_uploaded_file_bytes(api, document, seed):
    data, content = document
    response = api.get(f"/documents/files/notice/{seed['tenants']['alpha']['notice_id']}/download-all")
    assert response.status_code == 200, response.text
    with ZipFile(BytesIO(response.content)) as archive:
        assert any(archive.read(name) == content for name in archive.namelist())


def test_viewer_cannot_upload_files(clients):
    response = clients(role="viewer").post("/documents/files", files={"file": ("forbidden.pdf", b"QA", "application/pdf")})
    assert response.status_code == 403
