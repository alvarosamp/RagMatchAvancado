"""Product analytics in the built CRM with real API, catalog and database."""

import json
from pathlib import Path

from playwright.sync_api import expect


def test_product_profiles_catalog_identity_and_export(page, identities, api, unique):
    model, compatibility = f"QA-MOD-{unique}", f"QA-SW-{unique}"
    for code, brand in [(model, "Fabricante QA Produtos"), (compatibility, "Fabricante QA Compatibilidade")]:
        response = api.post("/crm/query/catalog_products/insert", json={"values": {"name": code, "model": code, "brand": brand}})
        assert response.status_code == 200, response.text
    result = {
        "schema_version": "7.4.4", "n_interno": f"QA-PROFILES-{unique}",
        "edital": {"orgao": "Órgão QA Produtos", "numero_pregao": unique, "uf": "SP"},
        "itens_elegiveis": [{
            "numero_item_edital": "38", "categoria": "Modulo optico", "quantidade": "10", "preco_unitario": "R$ 100,00",
            "descricao_original": f"GBIC {model} COMPATÍVEL COM SWITCH {compatibility}",
            "caracteristicas_bi": {"formato": "SFP+", "velocidade": "10G", "tipo_meio": "Monomodo", "alcance": "10km"},
        }],
    }
    response = api.post("/analysis/documents", json={"source_kind": "edital", "source_name": "qa-products.json", "result": result})
    assert response.status_code == 200, response.text
    document_id = response.json()['id']
    page.context.add_cookies([
        {"name": name, "value": value, "url": "http://127.0.0.1:13089"}
        for name, value in identities["alpha", "admin"].items()
    ])
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    assert page.goto("http://127.0.0.1:13089/crm/inteligencia-mercado").status == 200
    expect(page.get_by_role("heading", name="Inteligência de produtos", exact=True)).to_be_visible(timeout=20000)
    page.get_by_text("Refinar a análise · período, categoria e atributos", exact=True).click()
    page.get_by_placeholder("Buscar marca, modelo, produto, UF ou portal...").fill(unique)
    section = page.locator('section[aria-labelledby="product-demand-title"]')
    expect(section.get_by_text("Fabricante QA Produtos", exact=True)).to_be_visible()
    expect(section.get_by_text("Associação no catálogo", exact=True)).to_be_visible()
    expect(section.get_by_text("Fabricante QA Compatibilidade", exact=True)).to_have_count(0)
    expect(section.get_by_text("1 de 1 itens", exact=True)).to_have_count(2)
    expect(page.get_by_role('heading', name='Modulo optico · SFP+ · 10G', exact=True)).to_be_visible()
    original_description = result['itens_elegiveis'][0]['descricao_original']
    expect(page.get_by_text(original_description, exact=True)).to_be_hidden()
    page.get_by_text('Descrição completa do edital', exact=True).click()
    expect(page.get_by_text(original_description, exact=True)).to_be_visible()
    readback = api.get(f'/analysis/documents/{document_id}')
    assert readback.status_code == 200, readback.text
    assert readback.json()['items'][0]['description'] == original_description
    with page.expect_download() as download:
        section.get_by_role("button", name="Exportar análise de produtos").click()
    exported = json.loads(download.value.path().read_text(encoding="utf-8"))
    assert exported["quality"]["catalogMapped"] == 1
    assert exported["quality"]["items"] == 1
    assert exported["profiles"][0]["quantity"] == 10
    assert exported["profiles"][0]["estimatedValue"] == 1000
    assert exported["items"][0]["identity"]["associatedBrands"] == ["Fabricante QA Produtos"]
    assert compatibility in exported["items"][0]["identity"]["compatibility"]
    assert not errors, errors
    Path('.qa-runtime').mkdir(exist_ok=True)
    Path('.qa-runtime/product-intelligence-export.json').write_text(json.dumps(exported, ensure_ascii=False, indent=2), encoding='utf-8')
    page.screenshot(path='.qa-runtime/product-intelligence.png', full_page=True)
