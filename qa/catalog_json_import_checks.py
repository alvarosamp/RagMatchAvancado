"""Exercise the real ORM importer in an isolated tenant database."""
import asyncio
import hashlib
import io
import json
import tempfile
from pathlib import Path
import app.main
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.models import Base
from app.auth.models import Tenant, User
from app.crm.models import CrmCatalogProduct, CrmCatalogProductDatasheet
from app.routers.catalog_import import import_product_json
from app.services import catalog_datasheets

engine = create_engine('sqlite://')
Base.metadata.create_all(engine)
raw = b'%PDF-1.4\nimporter test document\n%%EOF'
sha = hashlib.sha256(raw).hexdigest()
source = {'codigos_tor': ['QA-JSON-123'], 'marca': 'TOR', 'descricoes_lpu': ['Switch 24 portas'],
          'especificacoes_tecnicas': [{'nome': 'portas_rj45', 'valor': 24, 'validacao': 'informado_na_lpu'}],
          'datasheets': [{'sha256': sha, 'pdf_local': '/etc/passwd'}]}


def uploads(data=source, document=True):
    result = [UploadFile(filename='product.json', file=io.BytesIO(json.dumps(data).encode()))]
    if document:
        result.append(UploadFile(filename='datasheet.pdf', file=io.BytesIO(raw)))
    return result

with tempfile.TemporaryDirectory() as folder, Session(engine) as db:
    catalog_datasheets.ROOT = Path(folder)
    tenants = [Tenant(slug='import-a', name='A'), Tenant(slug='import-b', name='B')]
    db.add_all(tenants); db.flush()
    user = User(tenant_id=tenants[0].id, email='import@example.invalid', hashed_password='unused', role='editor')
    foreign = CrmCatalogProduct(tenant_id=tenants[1].id, sku='QA-JSON-123', name='Foreign', specification='untouched')
    db.add_all([user, foreign]); db.commit()
    report = asyncio.run(import_product_json(uploads(), db, user))
    assert report['resultados'][0]['status'] == 'criado'
    assert report['resultados'][0]['documentos_anexados'] == 1
    own = db.query(CrmCatalogProduct).filter_by(tenant_id=user.tenant_id).one()
    assert foreign.specification == 'untouched' and own.id != foreign.id
    own.cost = 500
    spec = json.loads(own.specification)
    spec['atributos']['portas_rj45'].update(valor=48, revisado=True)
    own.specification = json.dumps(spec); db.commit()
    again = asyncio.run(import_product_json(uploads(), db, user))
    assert again['resultados'][0]['status'] == 'atualizado'
    assert again['resultados'][0]['documentos_anexados'] == 0
    assert db.query(CrmCatalogProductDatasheet).count() == 1
    assert own.cost == 500 and json.loads(own.specification)['atributos']['portas_rj45']['valor'] == 48
    wrong = dict(source, codigos_tor=['NEW-1', 'NEW-2'])
    conflict = asyncio.run(import_product_json(uploads(wrong, False), db, user))
    assert conflict['resultados'][0]['status'] == 'conflito'
    assert db.query(CrmCatalogProduct).count() == 2
    invalid = [*uploads(document=False), UploadFile(filename='inventory.json', file=io.BytesIO(b'{}'))]
    try:
        asyncio.run(import_product_json(invalid, db, user))
        raise AssertionError('Invalid inventory accepted')
    except HTTPException as exc:
        assert exc.status_code == 400
print('PASS: exact tenant match, create/update, PDF hash association, deduplication, preserved prices/review, conflict and invalid batch.')
