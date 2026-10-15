import hashlib
import io
import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from app.auth.dependencies import require_role
from app.auth.models import User
from app.db.session import get_db
from app.crm.models import CrmCatalogProduct, CrmCatalogProductDatasheet
from app.services.catalog_datasheets import store_catalog_datasheet
from app.services.catalog_json_import import validate_product, merge_specification

router = APIRouter(prefix='/crm/imports', tags=['catálogo'])


@router.post('/product-json')
async def import_product_json(files: list[UploadFile] = File(...), db: Session = Depends(get_db),
                              user: User = Depends(require_role('admin', 'editor'))):
    if len(files) > 600:
        raise HTTPException(400, 'Envie no máximo 600 arquivos por lote.')
    products, documents, total = [], {}, 0
    for upload in files:
        suffix = Path(upload.filename or '').suffix.lower()
        limit = 8 * 1024 * 1024 if suffix == '.json' else 50 * 1024 * 1024
        raw = await upload.read(limit + 1)
        total += len(raw)
        if len(raw) > limit or total > 300 * 1024 * 1024:
            raise HTTPException(413, 'Limite: JSON 8 MB, PDF/DOCX 50 MB e lote 300 MB.')
        if suffix == '.json':
            try:
                data = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Número inválido')))
                codes = validate_product(data)
                products.append((upload.filename, data, codes))
            except (ValueError, UnicodeError, RecursionError) as exc:
                raise HTTPException(400, f'{upload.filename}: JSON de produto inválido. {str(exc)[:180]}') from exc
        elif suffix in {'.pdf', '.docx'}:
            if (suffix == '.pdf' and not raw.startswith(b'%PDF-')) or (suffix == '.docx' and not raw.startswith(b'PK')):
                raise HTTPException(400, f'{upload.filename}: conteúdo incompatível com o documento.')
            documents[hashlib.sha256(raw).hexdigest()] = (upload.filename, raw, upload.content_type)
        else:
            raise HTTPException(400, 'Selecione apenas JSONs de produtos e datasheets PDF/DOCX.')
    if not products:
        raise HTTPException(400, 'Inclua pelo menos um JSON da pasta produtos. Para um PDF avulso, abra o produto e use Datasheets.')
    rows = db.query(CrmCatalogProduct).filter_by(tenant_id=user.tenant_id).with_for_update().all()
    report, used, written = [], set(), []
    try:
        for filename, data, codes in products:
            matches = [p for p in rows if p.sku in codes]
            if not matches and data.get('part_number_fabricante') and data.get('marca'):
                matches = [p for p in rows if p.manufacturer_part_number == data['part_number_fabricante'] and p.brand == data['marca']]
            if len(matches) > 1 or (not matches and len(codes) != 1):
                report.append({'arquivo': filename, 'status': 'conflito', 'mensagem': 'Mais de um código/produto possível. Confira os códigos do cadastro e do JSON antes de reenviar.'})
                continue
            created = not matches
            product = matches[0] if matches else CrmCatalogProduct(tenant_id=user.tenant_id, sku=codes[0], name=codes[0],
                brand=data.get('marca'), model=data.get('part_number_fabricante') or codes[0],
                manufacturer_part_number=data.get('part_number_fabricante'),
                description='; '.join(str(x) for x in data.get('descricoes_lpu', [])), created_by=user.id)
            product.specification = merge_specification(product.specification, data)
            if created:
                db.add(product)
                db.flush()
                rows.append(product)
            attached, missing = 0, 0
            for document in data.get('datasheets', []):
                sha = document.get('sha256') if isinstance(document, dict) else None
                if not isinstance(sha, str):
                    continue
                if sha not in documents:
                    missing += 1
                    continue
                used.add(sha)
                old = db.query(CrmCatalogProductDatasheet).filter_by(tenant_id=user.tenant_id, catalog_product_id=product.id).all()
                if any(Path(d.storage_path).is_file() and hashlib.sha256(Path(d.storage_path).read_bytes()).hexdigest() == sha for d in old):
                    continue
                name, raw, content_type = documents[sha]
                stored = store_catalog_datasheet(db, tenant_id=user.tenant_id, user_id=user.id, product_id=product.id,
                    fileobj=io.BytesIO(raw), filename=name, content_type=content_type)
                written.append(Path(stored.storage_path))
                attached += 1
            report.append({'arquivo': filename, 'produto': product.name, 'sku': product.sku, 'id': product.id,
                           'status': 'criado' if created else 'atualizado', 'documentos_anexados': attached, 'documentos_nao_enviados': missing})
        db.commit()
    except Exception:
        db.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        raise
    return {'resultados': report, 'documentos_sem_vinculo': len(documents.keys() - used),
            'aviso': 'Dados da LPU disponíveis para filtros. Extrações de datasheet preservadas para revisão técnica; a importação não confirma evidências.'}
