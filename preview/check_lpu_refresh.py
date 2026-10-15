"""Exercise real catalogue imports inside a rolled-back preview DB transaction."""
import json
import os
import tempfile
import uuid
from pathlib import Path
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.main import app  # load all ORM mappings
from app.auth.models import Tenant
from app.crm.models import CrmCatalogProduct
from app.crm.lpu_importer import import_lpu_catalog

url = os.environ['QA_ADMIN_DATABASE_URL']
if url.rsplit('/', 1)[-1] != 'ragmatch_quality':
    raise RuntimeError('Somente banco da prévia.')
slug = 'demo-lpu-check-' + uuid.uuid4().hex
engine = create_engine(url)
with tempfile.TemporaryDirectory() as folder, engine.connect() as connection:
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        tenant = Tenant(slug=slug, name='Teste temporário de atualização LPU')
        session.add(tenant)
        session.flush()
        path = Path(folder) / 'demo.xlsx'
        def upload(description):
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = 'Switches'
            sheet.append(['Marca', 'PN TOR', 'Description', 'Disponibilidade', 'Part No'])
            sheet.append(['DEMO', 'REFRESH-CHECK', description, 'Estoque', 'MODEL-CHECK'])
            workbook.save(path)
            return import_lpu_catalog(path, db=session, tenant_id=tenant.id, user_id=None,
                                      lpu_drive_url='https://drive.google.com/DEMO-LOCAL')
        first = upload('24x10/100/1000M RJ45 PoE')
        product = session.query(CrmCatalogProduct).filter_by(tenant_id=tenant.id, sku='REFRESH-CHECK').one()
        before = json.loads(product.specification)
        assert before['atributos']['portas_rj45']['valor'] == 24
        assert before['atributos']['poe']['valor'] is True
        second = upload('48x10/100/1000M RJ45')
        after = json.loads(product.specification)
        assert after['atributos']['portas_rj45']['valor'] == 48
        assert 'poe' not in after['atributos']
        assert after['dados_lpu']['descricao_original'] == '48x10/100/1000M RJ45'
        assert first['created'] == 1 and second['updated'] == 1
        assert transaction.is_active
    finally:
        session.close()
        transaction.rollback()
with Session(engine) as session:
    assert session.query(Tenant).filter_by(slug=slug).first() is None
result = {'primeira_importacao_portas': 24, 'reimportacao_portas': 48,
          'poe_nao_informado_removido': True, 'teste_revertido_sem_alterar_catalogo': True}
Path('/reports/lpu-refresh-check.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result))
