"""Generate new test-only credentials; never read or reuse production .env files."""

import secrets
from pathlib import Path


def main():
    path = Path(__file__).with_name("hostinger.env")
    if path.exists():
        raise SystemExit("hostinger.env já existe; preservado sem alterações.")
    settings = {
        "HTTP_PORT": "8088", "POSTGRES_PASSWORD": secrets.token_hex(24),
        "APP_DB_PASSWORD": secrets.token_hex(24), "SECRET_KEY": secrets.token_hex(48),
        "ADMIN_EMAIL": "admin@ragmatch-teste.com", "ADMIN_PASSWORD": "Rm!8" + secrets.token_urlsafe(20),
        "SEED_DEMO": "0", "IMAGE_TAG": "sha-7870582618eea5515ce3ca0dea906b7e91226b5c",
        "PUBLIC_ORIGIN": "http://IP_DO_SERVIDOR:8088", "AUTH_COOKIE_SECURE": "0",
        "MINIO_ROOT_USER": "ragmatch-products-storage", "MINIO_ROOT_PASSWORD": secrets.token_hex(24),
        "S3_BUCKET": "ragmatch-products-test", "ALLOW_EMPTY_DATABASE_BOOTSTRAP": "1",
        "OLLAMA_PULL_MODELS": "1", "PNCP_RADAR_AUTO_REFRESH": "0",
    }
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("# Credenciais exclusivas do servidor de teste. Não enviar ao GitHub.\n")
        stream.write("\n".join(f"{key}={value}" for key, value in settings.items()) + "\n")
    print(f"Arquivo de ambiente gerado: {path}")


if __name__ == "__main__":
    main()
