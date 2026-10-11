"""Built frontend + real API/DB. Only explicit outage tests intercept traffic."""

import re

from playwright.sync_api import expect
import pytest

from conftest import WEB_URL


PAGES = [
    ("/dashboard", "Olá"), ("/usuarios", "Usuários"),
    ("/analytics", "Performance de Produtos"), ("/relatorios", "Relatorio executivo de licitacoes"),
    ("/controle", "Controle de Editais"), ("/upload", "Adicionar processos ao portal"),
    ("/configuracoes", "Configurações"), ("/assinatura", "Entrada, versoes e assinatura de documentos"),
    ("/radar", "Radar de oportunidades"), ("/integracoes/bling", "Bling ERP"),
]

CRM_PAGES = [
    ("orgaos", "Órgãos"), ("portais", "Portais"),
    ("produtos", "Catalogo de produtos"), ("resultados", "Resultados"),
    ("expedicao", "Etiquetagem e postagem"), ("descartados", "Descartados"),
    ("editais/suspensos", "Editais suspensos"), ("templates", "Repositorio de documentos"),
    ("usuarios", "Usuários"), ("match", "Fila de match"),
    ("inteligencia-mercado", "Inteligência de mercado"),
]


@pytest.mark.parametrize("width", [390, 1440], ids=["mobile", "desktop"])
@pytest.mark.parametrize("path,title", CRM_PAGES)
def test_embedded_crm_screens_open_with_real_backend(authenticated_page, path, title, width):
    page = authenticated_page
    page.set_viewport_size({"width": width, "height": 900})
    errors, failed = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda response: failed.append(response.url) if response.status >= 500 and "/api/" in response.url else None)
    assert page.goto(WEB_URL + "/crm/" + path).status == 200
    expect(page.get_by_role("heading", name=title, exact=True).first).to_be_visible(timeout=15000)
    assert not errors, errors
    assert not failed, failed


@pytest.mark.parametrize("width", [390, 1440], ids=["mobile", "desktop"])
@pytest.mark.parametrize("path,title", PAGES)
def test_main_screens_open_with_real_data_without_js_or_server_errors(authenticated_page, path, title, width):
    page = authenticated_page
    page.set_viewport_size({"width": width, "height": 900})
    errors, failed = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda response: failed.append(response.url) if response.status >= 500 and "/api/" in response.url else None)
    response = page.goto(WEB_URL + path)
    assert response.status == 200
    expect(page.get_by_role("heading", name=re.compile(re.escape(title))).first).to_be_visible(timeout=15000)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), f"Horizontal overflow at {width}px on {path}"
    assert not errors, errors
    assert not failed, failed


@pytest.mark.parametrize("width", [390, 1440], ids=["mobile", "desktop"])
def test_dashboard_displays_persisted_document_and_company(authenticated_page, width):
    page = authenticated_page
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(WEB_URL + "/dashboard")
    expect(page.get_by_text("edital-qa-alpha.pdf", exact=False).first).to_be_visible(timeout=15000)
    expect(page.get_by_text("edital-qa-beta.pdf", exact=False)).to_have_count(0)


@pytest.mark.parametrize("width", [390, 1440], ids=["mobile", "desktop"])
def test_embedded_crm_displays_actual_company_and_notice(authenticated_page, width):
    page = authenticated_page
    page.set_viewport_size({"width": width, "height": 900})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    with page.expect_response(lambda response: "/api/crm/dashboard-data" in response.url) as data:
        page.goto(WEB_URL + "/crm/")
    assert data.value.status == 200
    assert data.value.json()["tenant_name"] == "Empresa QA Alpha"
    expect(page.get_by_text("Empresa QA Alpha", exact=False).first).to_be_visible(timeout=15000)
    notices = data.value.json()["notices"]
    assert any(row["number"] == "QA-alpha-001" for row in notices)
    assert not any(row["number"] == "QA-beta-001" for row in notices)
    expect(page.get_by_text(notices[0]["number"], exact=False).first).to_be_visible()
    expect(page.get_by_text("QA-beta-001", exact=False)).to_have_count(0)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    assert not errors, errors


def test_crm_document_templates_tab_loads_actual_checklists(authenticated_page):
    page = authenticated_page
    page.goto(WEB_URL + "/crm/templates")
    page.get_by_role("tab", name="Modelos padrao").click()
    expect(page.get_by_role("heading", name="Documentacao padrao")).to_be_visible()


@pytest.mark.parametrize("path", ["/dashboard", "/usuarios", "/controle", "/relatorios", "/configuracoes"])
def test_protected_screens_redirect_anonymous_visitor_to_login(page, path):
    page.goto(WEB_URL + path)
    expect(page).to_have_url(re.compile(r"/login$"))
    expect(page.get_by_role("heading", name="Entrar no portal")).to_be_visible()


def test_real_login_form_persists_cookie_and_survives_reload(page, seed):
    page.goto(WEB_URL + "/login")
    page.locator('input[type="email"]').fill("alpha-admin@example.com")
    page.locator('input[type="password"]').fill(seed["password"])
    page.get_by_role("button", name="Entrar", exact=True).click()
    expect(page).to_have_url(re.compile(r"/dashboard$"))
    expect(page.get_by_text("edital-qa-alpha.pdf", exact=False).first).to_be_visible(timeout=15000)
    assert page.evaluate("localStorage.getItem('access_token')") is None
    assert any(cookie["name"] == "access_token" and cookie["httpOnly"] for cookie in page.context.cookies())
    page.reload()
    expect(page.get_by_text("edital-qa-alpha.pdf", exact=False).first).to_be_visible(timeout=15000)


def test_wrong_password_shows_error_and_does_not_open_dashboard(page):
    page.goto(WEB_URL + "/login")
    page.locator('input[type="email"]').fill("missing-browser@example.com")
    page.locator('input[type="password"]').fill("wrong-password")
    page.get_by_role("button", name="Entrar", exact=True).click()
    expect(page.get_by_text("Email ou senha incorretos.")).to_be_visible()
    expect(page).to_have_url(re.compile(r"/login$"))


def test_viewer_cannot_open_user_administration(page, identities):
    page.context.add_cookies([{"name": "access_token", "value": identities["alpha", "viewer"]["access_token"], "url": WEB_URL}])
    page.goto(WEB_URL + "/usuarios")
    expect(page).to_have_url(re.compile(r"/dashboard$"))


def test_analytics_outage_is_visible_and_not_reported_as_empty(authenticated_page):
    page = authenticated_page
    page.route("**/api/analytics/**", lambda route: route.fulfill(status=500, content_type="application/json", body='{"detail":"QA simulated outage"}'))
    page.goto(WEB_URL + "/analytics")
    expect(page.get_by_text("Erro ao carregar dados", exact=False)).to_be_visible(timeout=15000)
    expect(page.get_by_text("Nenhum dado de matching ainda", exact=False)).to_have_count(0)


def test_crm_outage_does_not_invent_zero_indicators(authenticated_page):
    page = authenticated_page
    page.route("**/api/crm/dashboard-data", lambda route: route.fulfill(status=500, content_type="application/json", body='{"detail":"QA simulated outage"}'))
    page.goto(WEB_URL + "/crm/")
    expect(page.get_by_text(re.compile("500|indisponível|indisponivel"), exact=False).first).to_be_visible(timeout=15000)


def test_user_page_displays_real_users_and_hides_other_company(authenticated_page):
    page = authenticated_page
    page.goto(WEB_URL + "/usuarios")
    expect(page.get_by_text("alpha-viewer@example.com", exact=False)).to_be_visible(timeout=15000)
    expect(page.get_by_text("beta-viewer@example.com", exact=False)).to_have_count(0)
