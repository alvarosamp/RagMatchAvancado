"""Idempotently provision the test Evolution instance/webhook; never send messages."""
import os
import time
from urllib.parse import quote

import httpx


def main():
    base = os.environ["EVOLUTION_BASE_URL"].rstrip("/")
    name = os.environ.get("EVOLUTION_INSTANCE", "ragmatch")
    webhook_url = os.environ.get("EVOLUTION_WEBHOOK_URL", "http://api:8000/integrations/whatsapp/webhook")
    with httpx.Client(base_url=base, headers={"apikey": os.environ["EVOLUTION_API_KEY"]}, timeout=30) as client:
        for attempt in range(60):
            try:
                ready = client.get("/instance/fetchInstances")
                if ready.is_success:
                    break
                if ready.status_code in {401, 403}:
                    raise RuntimeError("A chave EVOLUTION_API_KEY não foi aceita pela Evolution.")
            except httpx.TransportError:
                pass
            time.sleep(3)
        else:
            raise RuntimeError("Evolution não ficou disponível para configuração.")

        instances = ready.json()
        if not isinstance(instances, list):
            raise RuntimeError("Resposta inesperada da Evolution ao consultar instâncias.")
        names = {item.get("name") or item.get("instance", {}).get("instanceName")
                 for item in instances if isinstance(item, dict)}
        if name not in names:
            response = client.post("/instance/create", json={
                "instanceName": name, "integration": "WHATSAPP-BAILEYS", "qrcode": False,
                "groupsIgnore": True, "readMessages": False, "syncFullHistory": False,
            })
            if not response.is_success:
                raise RuntimeError(f"Falha ao criar instância Evolution (HTTP {response.status_code}).")
        response = client.post(f"/webhook/set/{quote(name, safe='')}", json={"webhook": {
            "enabled": True, "url": webhook_url, "byEvents": False, "base64": False,
            "headers": {"x-webhook-secret": os.environ["EVOLUTION_WEBHOOK_SECRET"]},
            "events": ["MESSAGES_UPSERT"],
        }})
        if not response.is_success:
            raise RuntimeError(f"Falha ao configurar webhook (HTTP {response.status_code}).")
        print("Instância Baileys e webhook configurados. Abra o Manager e conecte o número pelo QR Code.")


if __name__ == "__main__":
    main()
