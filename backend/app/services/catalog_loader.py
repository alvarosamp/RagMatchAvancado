from sqlalchemy.orm import Session
from app.db.models import Product
import json
from pathlib import Path
from app.logs.config import logger

def _find_switch_catalog_path() -> Path:
    """Resolve o caminho do catálogo de switches."""
    docker_candidates = [
        Path("/data/Produtos/all_devices.json"),
        Path("/data/all_devices.json"),
    ]
    for candidate in docker_candidates:
        if candidate.exists():
            return candidate

    repo_root = Path(__file__).resolve().parents[3]
    local_candidates = [
        repo_root / "data" / "Produtos" / "all_devices.json",
        repo_root / "data" / "all_devices.json",
    ]
    for candidate in local_candidates:
        if candidate.exists():
            return candidate

    searched = docker_candidates + local_candidates
    raise FileNotFoundError(
        "Não encontrei o catálogo de switches. Procurei em: "
        + ", ".join(str(p) for p in searched)
    )

def load_switch_catalog(db: Session) -> int:
    """
    Carrega o catálogo de switches no banco de dados a partir de um arquivo JSON.
    """
    catalog_path = _find_switch_catalog_path()
    with catalog_path.open("r", encoding="utf-8") as file:
        catalog = json.load(file)

    inserted_count = 0

    # Verifica duplicados de maneira otimizada
    existing_switches = {switch.model: switch for switch in db.query(Product).filter(Product.category == "switch").all()}

    # Carrega novos switches
    for model, specs in catalog.items():
        if model in existing_switches:
            continue

        new_switch = Product(model=model, category="switch", data=specs)
        db.add(new_switch)
        db.commit()
        inserted_count += 1

    logger.info(f"{inserted_count} switches inseridos.")
    return inserted_count