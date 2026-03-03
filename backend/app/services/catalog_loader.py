import json
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
from app.db.models import Product


def _find_default_catalog() -> Optional[Path]:
    """Procura por data/Produtos/all_devices.json subindo a partir do diretório do arquivo atual.
    Retorna Path se encontrado, ou None caso contrário.
    """
    current = Path(__file__).resolve()
    # inclui o próprio arquivo e todos os pais
    candidates = [current] + list(current.parents)
    for p in candidates:
        candidate = p / 'data' / 'Produtos' / 'all_devices.json'
        if candidate.exists():
            return candidate
    return None


def load_switch_catalog(db: Session, json_path: Optional[str] = None) -> int:
    """
    Carrega o catálogo de produtos a partir de um arquivo JSON e salva no banco de dados.

    Comportamento:
    - Se json_path for fornecido, usa-o diretamente.
    - Se json_path for None, procura por `data/Produtos/all_devices.json` subindo a árvore de diretórios
      a partir da localização deste módulo.
    - Lê o JSON, itera pelos pares model_name -> specs e insere somente produtos não-duplicados.
    - Retorna a quantidade de produtos inseridos.
    """
    if json_path:
        path = Path(json_path)
    else:
        found = _find_default_catalog()
        if not found:
            raise FileNotFoundError(
                "Arquivo JSON não encontrado. Passe json_path ou coloque 'data/Produtos/all_devices.json' no repositório."
            )
        path = found

    if not path.exists():
        raise FileNotFoundError(f"Arquivo JSON não encontrado: {str(path)}")

    payload = json.loads(path.read_text(encoding='utf-8'))
    inserted = 0

    # espera-se um dict com model_name: specs
    if not isinstance(payload, dict):
        raise ValueError(f"Formato de JSON inesperado: esperado objeto/dicionário no arquivo {path}")

    for model_name, specs in payload.items():
        # Se já existir no banco, não insere de novo
        exists = db.query(Product).filter(Product.model == model_name).first()
        if exists:
            continue
        db.add(
            Product(
                model=model_name,
                category='switch',
                data=specs,
            )
        )
        inserted += 1

    db.commit()
    return inserted
        