"""Generate a standalone pull-only Hostinger test composition (no credentials)."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
TAG = "evolution-hostinger-20261028-v1"


def main():
    config = yaml.safe_load((ROOT / "deploy/products/compose.panel.yaml").read_text())
    config["name"] = "ragmatch-evolution-test"
    services = config["services"]
    for service in services.values():
        if "image" in service:
            service["image"] = service["image"].replace("products-hostinger-20261028-v4", TAG)

    whatsapp = yaml.safe_load((ROOT / "deploy/docker-compose.whatsapp.yml").read_text())
    for name in ("api", "scheduler"):
        services[name]["environment"].update(whatsapp["services"][name]["environment"])
        services[name]["environment"]["EVOLUTION_BASE_URL"] = "http://evolution:8080"
        services[name]["environment"]["EVOLUTION_ENABLED"] = "${EVOLUTION_ENABLED:-1}"

    evolution = yaml.safe_load((ROOT / "deploy/docker-compose.evolution.yml").read_text())
    for name in ("evolution", "evolution-db", "evolution-redis"):
        services[name] = evolution["services"][name]
        services[name]["pull_policy"] = "always"
    services["evolution"]["ports"] = ["${EVOLUTION_HTTP_PORT:-8090}:8080"]
    services["evolution"]["environment"]["CORS_ORIGIN"] = "*"
    services["evolution"]["environment"]["CORS_CREDENTIALS"] = "true"
    services["evolution-setup"] = {
        "image": f"alvarocareli/ragmatch-api:${{IMAGE_TAG:-{TAG}}}",
        "pull_policy": "always", "restart": "no",
        "command": "python scripts/setup_evolution.py",
        "environment": {
            "EVOLUTION_BASE_URL": "http://evolution:8080",
            "EVOLUTION_INSTANCE": "${EVOLUTION_INSTANCE:-ragmatch}",
            "EVOLUTION_API_KEY": "${EVOLUTION_API_KEY:?Defina EVOLUTION_API_KEY}",
            "EVOLUTION_WEBHOOK_SECRET": "${EVOLUTION_WEBHOOK_SECRET:?Defina EVOLUTION_WEBHOOK_SECRET}",
        },
        "depends_on": {"evolution": {"condition": "service_started"}},
        "networks": ["app-internal"],
    }
    config["volumes"].update(evolution["volumes"])
    destination = ROOT / "deploy/evolution/compose.panel.yaml"
    destination.write_text(
        "# VPS DE TESTE — branch codex/evolution-whatsapp. Somente pull; nenhum build no painel.\n"
        "# Cole este arquivo inteiro e use hostinger.env.example como referência de ambiente.\n"
        + yaml.safe_dump(config, sort_keys=False, allow_unicode=True, width=140), encoding="utf-8",
    )
    print(f"Compose independente gerado: {destination}")


if __name__ == "__main__":
    main()
