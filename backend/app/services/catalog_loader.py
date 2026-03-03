import json
from pathlib import Path
from sqlachemy.orm import Session
from app.db.models import Product

def load_switch_catalog(db: Session, json_path :str = r'C:\Users\vish8\OneDrive\Documentos\RagMatchAvan-ado\data\Produtos\all_devices.json') -> int:
    '''
    Carrega o catálogo de produtos a partir de um arquivo JSON e salva no banco de dados
    -Lê o arquivo JSON
    -Para cada produto, cria um objeto Product e salva no banco de dados
    -Retorna quantos foram inseridos (ignorando duplicados)
    '''
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo JSON não encontrado: {json_path}")
    payload = json.loads(path.read_text(encoding='utf-8'))
    inserted = 0
    
    for model_name, specs in payload.items():
        #Se ja existir no banco, nao insere denovo
        exists = db.query(Product).filter(Product.model == model_name).first()
        if exists:
            continue
        db.add(
            Product(
            model = model_name, 
            category = 'switch',
            data = specs,
            )
        )
        inserted += 1
        
    db.commit()
    return inserted
        