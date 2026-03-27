"""Test runner: execute pipelinellm_prompt_ajustado on the first 10 files in
`Pncp/Base de teste do analisador de atas` using a Fake Ollama client.

This avoids contacting a real Ollama server and returns deterministic JSON so
we can validate the pipeline wiring.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_BASE = ROOT / "Pncp" / "Base de teste do analisador de atas"
RESULTS_DIR = TEST_BASE / "results_test"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Ensure repo root on sys.path so we can import the module
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pipelinellm_prompt_ajustado as plc

# Create a FakeClient to avoid network calls to Ollama
class FakeResponse(dict):
    pass

class FakeClient:
    def chat(self, model, format, messages, options=None):
        # Inspect the last user message to determine if it's item-mode or full doc
        user_msg = None
        for m in messages:
            if m.get("role") == "user":
                user_msg = m.get("content")
                break

        # If the prompt asks for a single item, return a single-item JSON object
        if user_msg and "retorne APENAS um OBJETO JSON representando UM ITEM" in user_msg:
            # Attempt to extract the raw block from the prompt for realism
            block = user_msg.split("Bloco:\n", 1)[-1] if "Bloco:\n" in user_msg else ""
            item_obj = {
                "numero_item": None,
                "descricao": None,
                "raw_descricao": block[:200],
                "tipo": None,
                "marca": None,
                "modelo": None,
                "quantidade": None,
                "unidade": None,
                "valor_unitario": None,
                "valor_total": None,
                "fornecedor": None,
                "cnpj_fornecedor": None,
                "especificacoes": [],
                "observacoes": None,
            }
            content = json.dumps(item_obj, ensure_ascii=False)
            return {"message": {"content": content}, "eval_count": 0, "prompt_eval_count": 0}

        # Otherwise return a full-document JSON with empty items
        doc_obj = {
            "numero_ata": None,
            "orgao": None,
            "data_assinatura": None,
            "vigencia": None,
            "objeto": None,
            "itens": [],
        }
        content = json.dumps(doc_obj, ensure_ascii=False)
        return {"message": {"content": content}, "eval_count": 0, "prompt_eval_count": 0}


def main():
    files = [p for p in sorted(TEST_BASE.iterdir()) if p.is_file()]
    if not files:
        print("No files found in", TEST_BASE)
        return

    selected = files[:10]
    print(f"Found {len(files)} files, processing {len(selected)} (first 10)")

    # Patch the module's _get_client to return our fake client
    plc._client = FakeClient()

    summary = []
    for f in selected:
        try:
            print(f"\nProcessing: {f.name}")
            resultado = plc.run_arquivo(f, id_pncp=f.stem)
            out_path = RESULTS_DIR / f"{f.stem}_result.json"
            out_path.write_text(plc.resultado_para_json(resultado, indent=2), encoding="utf-8")
            n_itens = len(resultado.itens or [])
            print(f" -> OK: {n_itens} items, saved to {out_path}")
            summary.append((f.name, "ok", n_itens))
        except Exception as e:
            print(f" -> ERROR processing {f.name}: {e}")
            summary.append((f.name, "error", str(e)))

    print("\nSummary:")
    for name, status, info in summary:
        print(f" - {name}: {status} ({info})")


if __name__ == "__main__":
    main()
