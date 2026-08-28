from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass
from typing import Literal

AutomatablePortal = Literal["BLL", "BNC"]

# Compras.gov.br fica de fora de propósito: desde 2011 o Serpro derruba a conexão
# de quem envia lances em intervalos curtos demais (padrão de robô), por força do
# Acórdão TCU 2601/2011. A forma correta de automatizar lá é a parametrização
# nativa do próprio sistema (IN SEGES/ME 73/2022, art. 19) — não scraping externo.
_UNSUPPORTED_MESSAGE = (
    "Sincronização automática não é suportada para Compras.gov.br. "
    "Use o campo de valor mínimo final nativo do próprio portal (IN 73/2022, art. 19); "
    "um robô externo ali é detectado e desconectado pelo sistema anti-bot do Serpro."
)


@dataclass
class PortalCredentials:
    username: str
    password: str


class PortalCredentialsMissing(RuntimeError):
    pass


class PortalAutomationUnavailable(RuntimeError):
    pass


def _credentials_for(portal: AutomatablePortal) -> PortalCredentials:
    """Le credenciais SOMENTE de variaveis de ambiente locais (.env), nunca do banco
    de dados ou de payload de API. Segue o mesmo padrao do projeto open-source
    LanceBot (LOGIN.env): a senha do portal fica no ambiente de quem opera o robo,
    nunca trafega pela aplicacao nem e persistida.
    """
    user = os.getenv(f"{portal}_PORTAL_USER")
    password = os.getenv(f"{portal}_PORTAL_PASSWORD")
    if not user or not password:
        raise PortalCredentialsMissing(
            f"Defina {portal}_PORTAL_USER e {portal}_PORTAL_PASSWORD no .env local "
            "para habilitar a sincronizacao automatica deste portal."
        )
    return PortalCredentials(username=user, password=password)


def _human_delay(min_seconds: float = 0.8, max_seconds: float = 2.4) -> None:
    """Pausa com variacao aleatoria entre acoes.

    Nao existe API de disputa/chat documentada para BLL/BNC — todo robo do mercado
    (comercial ou open-source, ex. LanceBot) opera via automacao de navegador sobre
    a sessao autenticada do proprio usuario. Isso NAO evita deteccao por padrao de
    velocidade; so evita o erro mais grosseiro (cliques em intervalos de milissegundos
    identicos aos de um script, que foi exatamente o padrao que o Comprasnet passou
    a bloquear em 2011). Calibrar os seletores abaixo e validar em um pregao de baixo
    risco antes de qualquer uso real e responsabilidade de quem operar este modulo.
    """
    time.sleep(random.uniform(min_seconds, max_seconds))


# Seletores de cada portal. NAO FORAM VALIDADOS contra o site real — foram deixados
# como pontos de calibracao explicitos porque este ambiente nao tem credenciais
# reais de BLL/BNC para testar o layout ao vivo. Antes do primeiro uso, inspecione
# a pagina logada (DevTools) e ajuste os seletores.
_PORTAL_CONFIG = {
    "BLL": {
        "login_url": "https://bll.org.br/login",
        "login_user_selector": "#usuario",
        "login_password_selector": "#senha",
        "login_submit_selector": "button[type=submit]",
        "best_bid_selector": "[data-testid=menor-lance]",
        "chat_message_selector": "[data-testid=chat-mensagem]",
    },
    "BNC": {
        "login_url": "https://bnc.org.br/login",
        "login_user_selector": "#usuario",
        "login_password_selector": "#senha",
        "login_submit_selector": "button[type=submit]",
        "best_bid_selector": "[data-testid=menor-lance]",
        "chat_message_selector": "[data-testid=chat-mensagem]",
    },
}


@dataclass
class PortalSyncResult:
    current_best_bid: float | None
    chat_messages: list[str]


def sync_session(portal: str, session_url: str) -> PortalSyncResult:
    """Loga no portal com credenciais locais e le o menor lance + chat da sessao.

    Le credenciais SOMENTE do ambiente local (nunca do banco). Levanta
    PortalAutomationUnavailable se o Playwright nao estiver instalado, e
    PortalCredentialsMissing se as variaveis de ambiente nao estiverem configuradas.
    """
    if portal == "COMPRAS_GOV":
        raise PortalAutomationUnavailable(_UNSUPPORTED_MESSAGE)
    if portal not in _PORTAL_CONFIG:
        raise PortalAutomationUnavailable(f"Portal '{portal}' nao suportado para sincronizacao automatica.")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise PortalAutomationUnavailable(
            "Playwright nao esta instalado neste ambiente. "
            "Rode `pip install playwright` e `playwright install chromium`."
        ) from exc

    credentials = _credentials_for(portal)  # type: ignore[arg-type]
    config = _PORTAL_CONFIG[portal]

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(config["login_url"])
            _human_delay()
            page.fill(config["login_user_selector"], credentials.username)
            _human_delay()
            page.fill(config["login_password_selector"], credentials.password)
            _human_delay()
            page.click(config["login_submit_selector"])
            page.wait_for_load_state("networkidle")

            _human_delay()
            page.goto(session_url)
            page.wait_for_load_state("networkidle")

            current_best_bid = None
            bid_locator = page.locator(config["best_bid_selector"]).first
            if bid_locator.count() > 0:
                raw_value = bid_locator.inner_text().strip()
                current_best_bid = _parse_currency(raw_value)

            chat_messages = [
                node.inner_text().strip()
                for node in page.locator(config["chat_message_selector"]).all()
            ]

            return PortalSyncResult(current_best_bid=current_best_bid, chat_messages=chat_messages)
        finally:
            browser.close()


def _parse_currency(raw_value: str) -> float | None:
    cleaned = raw_value.replace("R$", "").strip().replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None
