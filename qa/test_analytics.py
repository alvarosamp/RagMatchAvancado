"""Check numerical results using persisted matching rows, including foreign data."""
import pytest


@pytest.fixture
def matching_data(admin_db, seed, unique):
    products, requirements = [], []
    for tenant in ("alpha", "beta"):
        with admin_db.cursor() as cursor:
            cursor.execute("INSERT INTO products(model,category) VALUES (%s,'switch') RETURNING id", (f"QA-{tenant}-{unique}",))
            product_id = cursor.fetchone()[0]
            products.append(product_id)
            cursor.execute("INSERT INTO requirements(edital_id,attribute,raw_value) VALUES (%s,%s,'48 portas') RETURNING id",
                           (seed["tenants"][tenant]["edital_id"], f"qa-ports-{unique}"))
            requirement_id = cursor.fetchone()[0]
            requirements.append(requirement_id)
            for status, score in zip(["ATENDE", "VERIFICAR", "NAO_ATENDE"], [1.0, 0.5, 0.0]):
                cursor.execute("INSERT INTO matching_results(product_id,requirements_id,status,score) VALUES (%s,%s,%s,%s)",
                               (product_id, requirement_id, status, score if tenant == "alpha" else 0))
    admin_db.commit()
    yield f"QA-alpha-{unique}", f"qa-ports-{unique}"
    with admin_db.cursor() as cursor:
        cursor.execute("DELETE FROM matching_results WHERE product_id=ANY(%s)", (products,))
        cursor.execute("DELETE FROM requirements WHERE id=ANY(%s)", (requirements,))
        cursor.execute("DELETE FROM products WHERE id=ANY(%s)", (products,))
    admin_db.commit()


def test_overview_uses_actual_scores_and_excludes_other_tenant(api, matching_data):
    model, _ = matching_data
    data = api.get("/analytics/overview").json()
    assert data["total_matchings"] == 3
    assert data["score_medio"] == 0.5
    assert data["taxa_atendimento"] == 0.333
    assert data["melhor_produto"] == model


def test_product_statistics_include_all_verdicts(api, matching_data):
    model, _ = matching_data
    rows = api.get("/analytics/produtos").json()
    assert len(rows) == 1 and rows[0]["produto"] == model
    assert rows[0]["total"] == 3
    assert rows[0]["mediana"] == 0.5
    assert rows[0]["desvio"] == pytest.approx(0.408, abs=0.001)
    assert [rows[0][key] for key in ("atende", "verificar", "nao_atende")] == [1, 1, 1]


def test_requirement_gap_statistics_and_evolution_match_database(api, matching_data, seed):
    _, attribute = matching_data
    rows = api.get("/analytics/requisitos").json()
    assert len(rows) == 1 and rows[0]["requisito"] == attribute
    assert rows[0]["taxa_falha"] == 0.667
    evolution = api.get("/analytics/evolucao").json()
    assert len(evolution) == 1
    assert evolution[0]["edital_id"] == seed["tenants"]["alpha"]["edital_id"]
    assert evolution[0]["score_medio"] == 0.5


def test_histogram_includes_zero_middle_and_perfect_scores(api, matching_data):
    data = api.get("/analytics/distribuicao").json()
    assert data["total"] == 3
    assert [row["count"] for row in data["buckets"]] == [1, 0, 0, 0, 0, 1, 0, 0, 0, 1]


@pytest.mark.parametrize("endpoint", ["produtos", "requisitos", "evolucao"])
def test_empty_company_does_not_receive_foreign_analytics(clients, matching_data, endpoint):
    assert clients("empty").get(f"/analytics/{endpoint}").json() == []
