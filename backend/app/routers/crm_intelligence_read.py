from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.db.session import get_db
from app.services.crm_intelligence_read import demand_notices

router = APIRouter(prefix='/crm/intelligence', tags=['inteligência CRM'])


@router.get('/notices')
def get_notices(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {'data': demand_notices(db, user.tenant_id), 'source': 'crm_current'}
