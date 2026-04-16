"""
Consolida todos os JSONs de resultado em uma única tabela (CSV + XLSX).

Cada linha representa um item, com os metadados da ata (orgao, numero_ata, etc.)
propagados para facilitar análise de mercado pelo time de compras.
"""
import os
import json
import pandas as pd

SRC_DIR = os.path.join(os.path.dirname(__file__), '../resultado_modelo_menor')
DST_DIR = os.path.join(os.path.dirname(__file__), '../resultadotabela')
os.makedirs(DST_DIR, exist_ok=True)

# Campos de metadados da ata que serão adicionados a cada linha de item
META_FIELDS = ["id_pncp", "numero_ata", "orgao", "data_assinatura", "vigencia", "objeto"]

# Ordem das colunas na tabela final
COL_ORDER = [
    "id_pncp", "numero_ata", "orgao", "data_assinatura", "vigencia", "objeto",
    "numero_item", "descricao", "tipo", "marca", "modelo",
    "quantidade", "unidade", "valor_unitario", "valor_total",
    "fornecedor", "cnpj_fornecedor", "especificacoes", "observacoes",
    "arquivo_origem",
]

all_rows = []

for fname in sorted(os.listdir(SRC_DIR)):
    if not fname.endswith('.json'):
        continue

    in_path = os.path.join(SRC_DIR, fname)
    try:
        with open(in_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f'Erro ao ler {fname}: {e}')
        continue

    if not isinstance(data, dict):
        print(f'Formato inesperado em {fname}: {type(data)}')
        continue

    meta = {k: data.get(k) for k in META_FIELDS}
    itens = data.get("itens") or []

    if not isinstance(itens, list):
        print(f'Campo "itens" inválido em {fname}')
        continue

    for item in itens:
        if not isinstance(item, dict):
            continue
        row = {**meta, **item, "arquivo_origem": fname}
        # Converte lista de especificações para string legível
        if isinstance(row.get("especificacoes"), list):
            row["especificacoes"] = "; ".join(str(e) for e in row["especificacoes"])
        all_rows.append(row)

if not all_rows:
    print('Nenhum item encontrado nos JSONs.')
else:
    df = pd.DataFrame(all_rows)

    # Garante ordem de colunas, incluindo colunas extras não previstas
    cols_presentes = [c for c in COL_ORDER if c in df.columns]
    cols_extras = [c for c in df.columns if c not in COL_ORDER]
    df = df[cols_presentes + cols_extras]

    csv_path  = os.path.join(DST_DIR, 'resultado_unico.csv')
    xlsx_path = os.path.join(DST_DIR, 'resultado_unico.xlsx')
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    df.to_excel(xlsx_path, index=False)
    print(f'Salvo: {csv_path}  ({len(df)} itens de {len(set(df["arquivo_origem"]))} arquivos)')
    print(f'Salvo: {xlsx_path}')
