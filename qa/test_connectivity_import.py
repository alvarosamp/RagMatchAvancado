"""Expanded analyzer contract through HTTP, real PostgreSQL and CRM readback."""

from copy import deepcopy


def connectivity_payload(unique):
    specs = [
        ("Switch", {"quantidade_portas": "24 Portas", "recursos_redundancia": ["Stacking", "MLAG"]}),
        ("Access Point", {"faixas_frequencia": "2,4/5 GHz", "interface_lan": "Gigabit"}),
        ("Transceiver", {"formato": "SFP+", "velocidade": "10G", "alcance": "N/C"}),
        ("Modulo optico", {"formato": "SFP+", "tipo_meio": "N/C"}),
        ("Cabo DAC", {"formato": "SFP+", "comprimento": "3 m", "tipo_cabo": "Passivo", "bitola_awg": "30 AWG"}),
        ("Cabo AOC", {"formato": "QSFP28", "velocidade": "100G", "comprimento": "5 m"}),
        ("Patch cord", {"meio": "Optico", "conector_lado_a": "LC", "conector_lado_b": "SC", "comprimento": "2,5 m", "tipo_fibra": "N/C"}),
    ]
    result = {
        "schema_version": "7.4.4", "n_interno": f"QA-CONNECTIVITY-{unique}",
        "controle": {"versao_analisador": "V7.4.7"},
        "edital": {"orgao": "Prefeitura conectividade QA", "uf": "SP", "numero_pregao": f"QA-{unique}", "status": "🟢"},
        "itens_elegiveis": [
            {"numero_item_edital": str(i), "categoria": category, "descricao_original": f"{category} QA {unique}",
             "quantidade": "2", "preco_unitario": "R$ 100,00", "valor_total_item": "R$ 200,00", "caracteristicas_bi": features}
            for i, (category, features) in enumerate(specs, 1)
        ],
    }
    payload = {"source_kind": "edital", "source_name": "connectivity-contract.json", "result": result}
    return payload


def test_connectivity_import_reimport_and_tenant_isolation(api, clients, unique):
    payload = connectivity_payload(unique)
    result = payload["result"]
    response = api.post("/analysis/documents", json=payload)
    assert response.status_code == 200, response.text
    document = response.json()
    assert not document["duplicate"]
    assert len(document["items"]) == 7
    notice_id = document["crm_sync"]["notice_id"]
    assert document["crm_sync"]["products"] == 7
    for original, stored in zip(result["itens_elegiveis"], sorted(document["items"], key=lambda item: int(item["item_number"]))):
        assert all(stored["caracteristicas_bi"][key] == value for key, value in original["caracteristicas_bi"].items())
        assert all(value == "N/C" for key, value in stored["caracteristicas_bi"].items() if key not in original["caracteristicas_bi"])
        assert stored["raw_payload"]["_raw_input"] == original

    repeated = api.post("/analysis/documents", json=payload)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["id"] == document["id"] and repeated.json()["duplicate"]

    # A new extracted item must extend the existing notice without duplicating it.
    expanded = deepcopy(payload)
    extra = deepcopy(result["itens_elegiveis"][-1])
    extra.update(numero_item_edital="8", descricao_original="Patch cord adicional QA")
    expanded["result"]["itens_elegiveis"].append(extra)
    changed = api.post("/analysis/documents", json=expanded)
    assert changed.status_code == 200, changed.text
    assert changed.json()["id"] == document["id"] and not changed.json()["duplicate"]
    assert changed.json()["crm_sync"]["notice_id"] == notice_id
    assert len(changed.json()["items"]) == 8

    products_response = api.get("/crm/query/notice_products")
    assert products_response.status_code == 200, products_response.text
    products = [p for p in products_response.json()["data"] if p["notice_id"] == notice_id]
    assert len(products) == 8
    for product in products:
        expected = expanded["result"]["itens_elegiveis"][int(product["item_number"]) - 1]["caracteristicas_bi"]
        assert all(product["bi_features"][key] == value for key, value in expected.items())
        assert product["reference_total_price"] == 200

    dashboard_response = api.get("/analysis/dashboard")
    assert dashboard_response.status_code == 200, dashboard_response.text
    categories = {c["categoria"]: c for c in dashboard_response.json()["categories"]}
    assert categories["Cabo óptico AOC"]["breakdowns"]["comprimento"][0]["valor"] == "5 m"
    assert categories["Patch cord"]["breakdowns"]["tipo_fibra"] == []
    assert any(row["valor"] == "LC" for row in categories["Patch cord"]["breakdowns"]["conector_lado_a"])

    other = clients("beta")
    response = other.get("/analysis/documents")
    assert response.status_code == 200, response.text
    assert document["id"] not in [d["id"] for d in response.json()]
    response = other.get("/crm/query/notice_products")
    assert response.status_code == 200, response.text
    assert not any(p["notice_id"] == notice_id for p in response.json()["data"])
