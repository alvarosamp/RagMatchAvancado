"""Exercise the user's manual JSON upload against the Docker application."""

import json

from playwright.sync_api import expect

from qa.test_connectivity_import import connectivity_payload


def test_manual_connectivity_json_upload(page, identities, api, unique):
    page.context.add_cookies([
        {"name": name, "value": value, "url": "http://127.0.0.1:13089"}
        for name, value in identities["alpha", "admin"].items()
    ])
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    response = page.goto("http://127.0.0.1:13089/upload")
    assert response.status == 200
    expect(page.get_by_role("heading", name="Adicionar processos ao portal")).to_be_visible()
    payload = connectivity_payload(unique)
    page.locator('input[type="file"]').first.set_input_files({
        "name": "connectivity-contract.json", "mimeType": "application/json",
        "buffer": json.dumps(payload["result"], ensure_ascii=False).encode("utf-8"),
    })
    page.get_by_role("checkbox", name="Somente analise, nao sincronizar CRM").uncheck()
    with page.expect_response(lambda r: r.url.endswith("/analysis/documents") and r.request.method == "POST") as stored:
        page.get_by_role("button", name="Processar arquivos", exact=True).click()
    assert stored.value.status == 200, stored.value.text()
    document = stored.value.json()
    assert document["crm_sync"]["products"] == 7
    expect(page.get_by_text("Importado", exact=True)).to_be_visible()
    persisted = api.get(f'/analysis/documents/{document["id"]}')
    assert persisted.status_code == 200, persisted.text
    assert len(persisted.json()["items"]) == 7
    products = api.get("/crm/query/notice_products")
    assert products.status_code == 200, products.text
    products = [p for p in products.json()["data"] if p["notice_id"] == document["crm_sync"]["notice_id"]]
    assert len(products) == 7
    assert next(p for p in products if p["category"] == "Patch cord")["bi_features"]["conector_lado_a"] == "LC"
    assert not errors, errors
