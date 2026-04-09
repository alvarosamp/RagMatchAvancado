import os
import json
import pandas as pd

SRC_DIR = os.path.join(os.path.dirname(__file__), '../resultado_modelo_menor')
DST_DIR = os.path.join(os.path.dirname(__file__), '../resultadotabela')
os.makedirs(DST_DIR, exist_ok=True)

def json_to_table(json_path, out_base):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # Tenta converter para DataFrame
    if isinstance(data, dict):
        # Se for dict, tenta pegar uma lista dentro
        for v in data.values():
            if isinstance(v, list):
                df = pd.DataFrame(v)
                break
        else:
            df = pd.DataFrame([data])
    elif isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        raise ValueError(f'Formato não suportado: {json_path}')
    # Salva CSV e XLSX
    csv_path = os.path.join(DST_DIR, out_base + '.csv')
    xlsx_path = os.path.join(DST_DIR, out_base + '.xlsx')
    df.to_csv(csv_path, index=False)
    df.to_excel(xlsx_path, index=False)
    print(f'Salvo: {csv_path} e {xlsx_path}')

def main():
    for fname in os.listdir(SRC_DIR):
        if fname.endswith('.json'):
            in_path = os.path.join(SRC_DIR, fname)
            out_base = os.path.splitext(fname)[0]
            try:
                json_to_table(in_path, out_base)
            except Exception as e:
                print(f'Erro em {fname}: {e}')

if __name__ == '__main__':
    main()
