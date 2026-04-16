"""
Converte um único JSON de resultado em tabela (CSV + XLSX).

Cada linha é um item da ata, com os metadados da ata propagados para contexto.
"""
import os
import json
import pandas as pd

SRC_DIR = os.path.join(os.path.dirname(__file__), '../resultado_modelo_menor')
DST_DIR = os.path.join(os.path.dirname(__file__), '../resultadotabela')
os.makedirs(DST_DIR, exist_ok=True)

META_FIELDS = ["id_pncp", "numero_ata", "orgao", "data_assinatura", "vigencia", "objeto"]

COL_ORDER = [
    "id_pncp", "numero_ata", "orgao", "data_assinatura", "vigencia", "objeto",
    "numero_item", "descricao", "tipo", "marca", "modelo",
    "quantidade", "unidade", "valor_unitario", "valor_total",
    "fornecedor", "cnpj_fornecedor", "especificacoes", "observacoes",
]


def json_to_table(json_path: str, out_base: str) -> None:
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f'Esperado dict, recebido {type(data)}: {json_path}')

    meta = {k: data.get(k) for k in META_FIELDS}
    itens = data.get("itens") or []

    rows = []
    for item in itens:
        if not isinstance(item, dict):
            continue
        row = {**meta, **item}
        if isinstance(row.get("especificacoes"), list):
            row["especificacoes"] = "; ".join(str(e) for e in row["especificacoes"])
        rows.append(row)

    if not rows:
        print(f'Nenhum item em: {json_path}')
        return

    df = pd.DataFrame(rows)
    cols_presentes = [c for c in COL_ORDER if c in df.columns]
    cols_extras = [c for c in df.columns if c not in COL_ORDER]
    df = df[cols_presentes + cols_extras]

    csv_path  = os.path.join(DST_DIR, out_base + '.csv')
    xlsx_path = os.path.join(DST_DIR, out_base + '.xlsx')
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    df.to_excel(xlsx_path, index=False)
    print(f'Salvo: {csv_path}  ({len(df)} itens)')
    print(f'Salvo: {xlsx_path}')


def main() -> None:
    for fname in sorted(os.listdir(SRC_DIR)):
        if not fname.endswith('.json'):
            continue
        in_path  = os.path.join(SRC_DIR, fname)
        out_base = os.path.splitext(fname)[0]
        try:
            json_to_table(in_path, out_base)
        except Exception as e:
            print(f'Erro em {fname}: {e}')


if __name__ == '__main__':
    main()
