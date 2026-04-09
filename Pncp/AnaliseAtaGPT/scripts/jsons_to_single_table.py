import os
import json
import pandas as pd

SRC_DIR = os.path.join(os.path.dirname(__file__), '../resultado_modelo_menor')
DST_DIR = os.path.join(os.path.dirname(__file__), '../resultadotabela')
os.makedirs(DST_DIR, exist_ok=True)

all_rows = []
for fname in os.listdir(SRC_DIR):
    if fname.endswith('.json'):
        in_path = os.path.join(SRC_DIR, fname)
        with open(in_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Normaliza para lista de dicts
        if isinstance(data, dict):
            found = False
            for v in data.values():
                if isinstance(v, list):
                    for row in v:
                        row['arquivo_origem'] = fname
                        all_rows.append(row)
                    found = True
                    break
            if not found:
                data['arquivo_origem'] = fname
                all_rows.append(data)
        elif isinstance(data, list):
            for row in data:
                row['arquivo_origem'] = fname
                all_rows.append(row)
        else:
            all_rows.append({'arquivo_origem': fname, 'conteudo': str(data)})

if all_rows:
    df = pd.DataFrame(all_rows)
    csv_path = os.path.join(DST_DIR, 'resultado_unico.csv')
    xlsx_path = os.path.join(DST_DIR, 'resultado_unico.xlsx')
    df.to_csv(csv_path, index=False)
    df.to_excel(xlsx_path, index=False)
    print(f'Salvo: {csv_path} e {xlsx_path}')
else:
    print('Nenhum dado encontrado nos JSONs.')
