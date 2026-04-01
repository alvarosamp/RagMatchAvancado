import os
import sys
import json
from pathlib import Path
from typing import Optional

# Importa o pipeline principal
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from Pncp.AnaliseAtaGPT.pipelinegpt import analisar_ata, resultado_para_json

# Configurações
ENTRADA_DIR = os.environ.get("GPT_BATCH_INPUT", "Pncp/Base de teste do analisador de atas")
SAIDA_DIR = os.environ.get("GPT_BATCH_OUTPUT", "Pncp/AnaliseAtaGPT/resultado_modelo_menor")
EXTENSOES = (".txt", ".md")  # ajuste se necessário

entrada_path = Path(ENTRADA_DIR)
saida_path = Path(SAIDA_DIR)
saida_path.mkdir(parents=True, exist_ok=True)

arquivos = sorted([f for f in entrada_path.iterdir() if f.is_file() and f.suffix.lower() in EXTENSOES])
if not arquivos:
    print(f"Nenhum arquivo de texto encontrado em {entrada_path}")
    sys.exit(1)

print(f"Processando {len(arquivos)} arquivos com modelo GPT: {os.environ.get('OPENAI_MODEL', 'gpt-5.4')}")

for arq in arquivos:
    nome_base = arq.stem
    saida_json = saida_path / f"{nome_base}.json"
    try:
        texto = arq.read_text(encoding="utf-8")
        resultado = analisar_ata(texto, id_pncp=nome_base)
        json_str = resultado_para_json(resultado, indent=2)
        saida_json.write_text(json_str, encoding="utf-8")
        print(f"[OK] {arq.name} → {saida_json.name}")
    except Exception as e:
        print(f"[ERRO] {arq.name}: {e}")
