"""Publish the locally tested release; never replace a tag with a different image."""
import json
from pathlib import Path
import subprocess

TAG = "evolution-hostinger-20261028-v1"
ROOT = Path(__file__).resolve().parents[2]
IMAGES = {
    "api": (f"ragmatch-evolution-api:{TAG}", "ragmatch-api"),
    "frontend": (f"ragmatch-evolution-frontend:{TAG}", "ragmatch-frontend"),
    "mlflow": ("alvarocareli/ragmatch-mlflow:products-hostinger-20261028-v4", "ragmatch-mlflow"),
}
SOURCE_COMMIT = "a976bb22a67543ef6832402e3ead447b0ae72878"


def output(*args):
    return subprocess.check_output(args, text=True).strip()


def remote_manifest(reference):
    result = subprocess.run(["docker", "buildx", "imagetools", "inspect", reference,
                             "--format", "{{json .Manifest}}"], capture_output=True, text=True)
    if result.returncode:
        if "not found" in result.stderr.lower() or "manifest unknown" in result.stderr.lower():
            return None
        raise RuntimeError(f"Não foi possível verificar a tag remota {reference}: {result.stderr[-1000:]}")
    return json.loads(result.stdout)["digest"]


def main():
    manifest = {"tag": TAG, "branch": "codex/evolution-whatsapp", "source_commit": SOURCE_COMMIT,
                "platform": "linux/amd64", "vps_deployed": False, "images": {},
                "validation": {"whatsapp_backend_tests": 13, "whatsapp_frontend_tests": 4,
                    "fresh_postgres_bootstrap": "passed", "restricted_role_and_rls": "passed",
                    "proxy_login_crm_persistence": "passed", "whatsapp_link_cancel": "passed",
                    "evolution_setup_idempotence": "passed", "webhook_secret_persistence": "passed",
                    "real_whatsapp_messages": "requires operator QR connection"}}
    for name, (local, repository) in IMAGES.items():
        reference = f"alvarocareli/{repository}:{TAG}"
        expected = json.loads(output("docker", "image", "inspect", local,
                                     "--format", "{{json .Descriptor}}"))["digest"]
        assert output("docker", "image", "inspect", local, "--format", "{{.Os}}/{{.Architecture}}") == "linux/amd64"
        existing = remote_manifest(reference)
        if existing and existing != expected:
            raise RuntimeError(f"A tag {reference} já existe com outro digest; escolha uma nova versão.")
        if not existing:
            subprocess.run(["docker", "tag", local, reference], check=True)
            print(f"Publicando {reference}", flush=True)
            result = subprocess.run(["docker", "push", reference], capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(result.stderr[-2000:])
        actual = remote_manifest(reference)
        if actual != expected:
            raise RuntimeError(f"Digest publicado difere da imagem testada: {reference}")
        manifest["images"][name] = {"reference": reference, "digest": actual, "remote_verified": True}
        print(f"Verificado {reference}: {actual}", flush=True)
    destination = ROOT / "docs/releases" / f"{TAG}.json"
    destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"Manifesto gravado em {destination}")


if __name__ == "__main__":
    main()
