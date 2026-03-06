from app.services.requirements_checker import check_requirements
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Product, MatchingResult
from app.services.catalog_loader import load_switch_catalog
from app.logs.config import logger


router = APIRouter(tags=["switches"])

@router.get("/switches")
def list_switches(db: Session = Depends(get_db)):
    """Retorna todos os switches do banco."""
    switches = db.query(Product).filter(Product.category == "switch").all()
    logger.info(f"Switches encontrados: {len(switches)}")
    return [{"model": p.model, "data": p.data} for p in switches]

@router.get("/verify-switches")
def verify_all_switches(db: Session = Depends(get_db)):
    """Verifica todos os switches e seus requisitos"""
    switches = db.query(Product).filter(Product.category == "switch").all()
    
    result = []
    for switch in switches:
        switch_data = switch.data
        verification_result = check_requirements(switch_data)
        result.append({
            "model": switch.model,
            "verification": verification_result
        })
        logger.info(f"Resultado da verificação para {switch.model}: {verification_result}")

    return {"message": "Verificação completa", "switches_verified": len(switches), "results": result}

@router.get("/matching-results")
def get_matching_results(db: Session = Depends(get_db)):
    """
    Exibe os resultados de matching de requisitos para os switches no banco de dados.
    """
    results = db.query(MatchingResult).all()
    return results