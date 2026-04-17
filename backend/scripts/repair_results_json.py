"""Repair invalid JSON files in Pncp/results_llm by asking the Ollama model to correct them.

Behavior:
- Iterate over all JSON files in Pncp/results_llm
- For each file, attempt json.loads(); if valid, skip
- If invalid, read raw text, call Ollama /api/chat with a strict prompt (temperature=0) asking to output only valid JSON following the same schema
- If the model returns valid JSON, back up the original file into Pncp/results_llm/backup/ and overwrite the original with the repaired JSON
- If repair fails, write the model response into a .repair.txt for manual inspection

Note: this script expects the Ollama host and model to be available via environment vars OLLAMA_HOST and OLLAMA_MODEL (defaults match pipelinellm).
"""

import os
import json
import glob
import shutil
import logging
import time
from pathlib import Path

import requests

# The results folder lives at the repository root `Pncp/results_llm` (two levels up from this script)
RESULTS_DIR = Path(__file__).resolve().parents[2] / "Pncp" / "results_llm"
BACKUP_DIR = RESULTS_DIR / "backup"
REPAIRS_DIR = RESULTS_DIR / "repairs"

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

SYSTEM_PROMPT = (
    "You are a meticulous JSON-fixer. You will receive the text that was produced by a model which should be a valid JSON object following a specific schema for procurement 'ata' analysis. "
    "Your job is to output only valid JSON (no commentary, no markdown, no trailing commas) that follows the structure present in the provided sample. If you cannot recover some field, set it to null. Use double quotes for property names and strings. Escape any inner quotes correctly."
)

# A minimal example of the expected top-level schema to help the model
SCHEMA_HINT = {
    "id_pncp": "string",
    "numero_ata": "string",
    "orgao": "string",
    "data_assinatura": "string",
    "vigencia": "string|null",
    "objeto": "string",
    "itens": [
        {
            "numero_item": "string",
            "descricao": "string",
            "tipo": "string|null",
            "marca": "string|null",
            "modelo": "string|null",
            "quantidade": "string|null",
            "unidade": "string|null",
            "valor_unitario": "string|null",
            "valor_total": "string|null",
            "fornecedor": "string|null",
            "cnpj_fornecedor": "string|null",
            "especificacoes": ["string"],
            "observacoes": "string|null"
        }
    ]
}

REPAIR_INSTRUCTION = (
    "Below is the exact text captured from the model's output for one document. It may be malformed JSON (missing quotes, unescaped quotes, trailing commas, truncated strings, etc.). "
    "Produce and return ONLY a single JSON object that follows the schema example I provided (keys may be null if unknown). Do not add any explanation or extra characters. If some array or object is truncated, try to reconstruct it conservatively; if unsure set fields to null."
)


def call_ollama_fix(raw_text: str, model: str = OLLAMA_MODEL, host: str = OLLAMA_HOST):
    url = f"{host.rstrip('/')}/api/chat"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Schema hint:\n" + json.dumps(SCHEMA_HINT, ensure_ascii=False)},
        {"role": "user", "content": REPAIR_INSTRUCTION},
        {"role": "user", "content": "---BEGIN MODEL OUTPUT---\n" + raw_text + "\n---END MODEL OUTPUT---"},
    ]

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 20000,
    }

    logging.info("Calling Ollama to repair JSON (model=%s) ...", model)
    resp = requests.post(url, json=payload, timeout=1200)
    resp.raise_for_status()
    data = resp.json()

    # Ollama response shape: choices -> list -> message/content/parts (varies by version)
    try:
        # new-ish style
        parts = data["choices"][0]["message"]["content"]["parts"]
        text = "\n".join(parts)
    except Exception:
        try:
            # older style
            parts = data["choices"][0]["content"]["parts"]
            text = "\n".join(parts)
        except Exception:
            # fallback: try to stringify whole response
            text = json.dumps(data, ensure_ascii=False)

    return text


def is_json_valid(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except Exception:
        return False


def main():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    REPAIRS_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(RESULTS_DIR.glob("*.json"))
    logging.info("Found %d JSON files in %s", len(files), RESULTS_DIR)

    for f in files:
        logging.info("Checking: %s", f.name)
        text = f.read_text(encoding="utf-8")
        if is_json_valid(text):
            logging.info("Valid JSON — skipping: %s", f.name)
            continue

        logging.warning("Invalid JSON detected in %s — attempting repair", f.name)

        # Send raw text to model for repair
        try:
            repaired_text = call_ollama_fix(text)
        except Exception as e:
            logging.exception("Ollama call failed for %s: %s", f.name, e)
            # Save the failing response placeholder
            (REPAIRS_DIR / (f.name + ".error.txt")).write_text(str(e), encoding="utf-8")
            continue

        # Try to parse repaired output as JSON
        if is_json_valid(repaired_text):
            # Backup original
            ts = int(time.time())
            backup_name = BACKUP_DIR / f"{f.name}.{ts}.bak"
            shutil.copy2(f, backup_name)
            logging.info("Backed up original to %s", backup_name)

            # Write repaired content
            f.write_text(repaired_text, encoding="utf-8")
            logging.info("Wrote repaired JSON to %s", f.name)

            # Save a copy of the repair text for traceability
            (REPAIRS_DIR / (f.name + ".repaired.txt")).write_text(repaired_text, encoding="utf-8")
        else:
            logging.warning("Repaired text is still invalid JSON for %s — saving repair attempt for manual review", f.name)
            (REPAIRS_DIR / (f.name + ".attempt.txt")).write_text(repaired_text, encoding="utf-8")


if __name__ == "__main__":
    main()
