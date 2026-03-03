from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Product

router = APIRouter(tags=["switches"])

@router.get("/switches")
def list_switches(db: Session = Depends(get_db)):
    """
    Retorna todos os switches do banco.
    """
    items = db.query(Product).filter(Product.category == "switch").all()
    return [{"model": p.model, "data": p.data} for p in items]