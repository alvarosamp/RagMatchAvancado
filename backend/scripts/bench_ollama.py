"""Benchmark simples de modelos Ollama.

Roda uma chamada curta para cada modelo listado e imprime o tempo gasto e um
preview da resposta. Use PYTHONPATH=. e execute com o venv ativo.
"""

from __future__ import annotations

import time
from ollama import Client


def main() -> None:
    client = Client()

    models = [
        "llama3.2:1b",
        "phi3:mini",
        "llama3:8b",
        "mistral:7b-instruct-q4_0",
    ]

    prompt = "Responda em uma palavra: ok"

    for m in models:
        print("\n---\nModel:", m)
        try:
            t0 = time.time()
            resp = client.chat(
                model=m,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.0, "num_predict": 64},
            )
            dt = time.time() - t0
            content = resp.get("message", {}).get("content", "")
            preview = content.replace("\n", " ")[:200]
            print(f"time: {dt:.2f}s | preview: {preview!r}")
        except Exception as e:
            print(f"error: {e}")


if __name__ == "__main__":
    main()
