"""Validate portal/Evolution wiring without connecting a phone or sending messages."""
import argparse
import http.cookiejar
import json
from pathlib import Path
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--evolution-url", required=True)
    parser.add_argument("--env-file", required=True, type=Path)
    args = parser.parse_args()
    settings = dict(line.split("=", 1) for line in args.env_file.read_text().splitlines()
                    if line and not line.startswith("#") and "=" in line)
    base = args.base_url.rstrip("/")
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def portal(path, data=None, method=None, headers=None):
        request_headers = {"Origin": base, "Content-Type": "application/json", **(headers or {})}
        request = urllib.request.Request(base + "/api" + path, method=method,
            data=json.dumps(data).encode() if data is not None else None, headers=request_headers)
        with client.open(request, timeout=30) as response:
            return json.load(response)

    portal("/auth/login", {"email": settings["ADMIN_EMAIL"], "password": settings["ADMIN_PASSWORD"]})
    status = portal("/integrations/whatsapp/me")
    assert status["configured"] is True and status["linked"] is False, status
    link = portal("/integrations/whatsapp/link", {})
    assert link["message"].startswith("VINCULAR ") and link["expires_in_seconds"] == 600
    assert link["url"].startswith("https://wa.me/" + settings["EVOLUTION_BOT_PHONE"])
    portal("/integrations/whatsapp/me", method="DELETE")
    assert portal("/integrations/whatsapp/me")["linked"] is False
    print("Portal → login → vínculo temporário → cancelamento: OK")

    try:
        portal("/integrations/whatsapp/webhook", {"event": "messages.upsert"})
    except urllib.error.HTTPError as error:
        assert error.code == 401, error.code
    else:
        raise AssertionError("Webhook aceitou uma requisição sem segredo.")
    ignored = portal("/integrations/whatsapp/webhook", {"event": "messages.set"},
                     headers={"x-webhook-secret": settings["EVOLUTION_WEBHOOK_SECRET"]})
    assert ignored["status"] == "ignored"
    print("Webhook: segredo obrigatório e eventos não autorizados ignorados: OK")

    evolution = args.evolution_url.rstrip("/")
    request = urllib.request.Request(evolution + "/webhook/find/" + settings["EVOLUTION_INSTANCE"],
                                    headers={"apikey": settings["EVOLUTION_API_KEY"]})
    with urllib.request.urlopen(request, timeout=30) as response:
        webhook = json.load(response)
    assert webhook["enabled"] is True
    assert webhook["url"] == "http://api:8000/integrations/whatsapp/webhook"
    assert webhook["events"] == ["MESSAGES_UPSERT"]
    assert webhook["headers"]["x-webhook-secret"] == settings["EVOLUTION_WEBHOOK_SECRET"]
    with urllib.request.urlopen(evolution + "/manager", timeout=30) as response:
        assert response.status == 200
    print("Evolution: Manager acessível e webhook persistido com segredo: OK")
    print("Nenhum número conectado e nenhuma mensagem real enviada.")


if __name__ == "__main__":
    main()
