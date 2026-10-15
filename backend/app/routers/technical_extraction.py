"""Document-based preview. No writes to CRM or catalog, no external requests."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
from fastapi.responses import Response

from app.auth.dependencies import require_role
from app.auth.models import User
from app.crm.models import CrmNoticeProduct, CrmCatalogProduct
from app.db.session import get_db
from app.services.technical_matching.extraction import read_pdf, extract_document, compare_extractions

router = APIRouter(prefix='/technical-extraction', tags=['technical-extraction'])


@router.get('/example/{kind}')
def example_pdf(kind: str, current_user: User = Depends(require_role('admin','editor'))):
    from io import BytesIO
    from reportlab.pdfgen import canvas
    examples = {
        'edital':['EXEMPLO SIMULADO - item de demonstracao', 'mínimo 24 portas RJ45', 'mínimo 4 portas SFP', 'orçamento de PoE mínimo 370 W'],
        'produto':['EXEMPLO SIMULADO - produto de demonstracao', 'RJ45 ports: 24', 'SFP ports: 4', 'PoE budget: 384 W'],
        'insuficiente':['EXEMPLO SIMULADO - produto de demonstracao', 'RJ45 ports: 24', 'SFP ports: 4', 'PoE budget: 180 W'],
    }
    if kind not in examples: raise HTTPException(404, 'Exemplo não encontrado.')
    output=BytesIO();pdf=canvas.Canvas(output)
    for i,line in enumerate(examples[kind]): pdf.drawString(50,780-i*28,line)
    pdf.save()
    return Response(output.getvalue(),media_type='application/pdf',headers={'Cache-Control':'no-store'})


async def _read(file: UploadFile | None, start: int, end: int | None):
    if file is None: return None
    try:
        raw = await file.read(50 * 1024 * 1024 + 1)
        if len(raw) > 50 * 1024 * 1024: raise ValueError('PDF maior que 50 MB.')
        return await run_in_threadpool(read_pdf, raw, Path(file.filename or 'documento.pdf').name, start, end)
    finally:
        await file.close()


@router.post('/preview')
async def preview(
    datasheet: UploadFile = File(...),
    edital: UploadFile | None = File(default=None),
    item_id: str | None = Form(default=None),
    catalog_id: str | None = Form(default=None),
    hardware: str = Form(default=''),
    categoria: str = Form(default='switch'),
    edital_inicio: int = Form(default=1), edital_fim: int | None = Form(default=None),
    datasheet_inicio: int = Form(default=1), datasheet_fim: int | None = Form(default=None),
    revisao: str = Form(default='{}'),
    current_user: User = Depends(require_role('admin', 'editor')),
    db: Session = Depends(get_db),
):
    try:
        review = json.loads(revisao)
        if not isinstance(review, dict) or any(not isinstance(review.get(k, []), list) for k in ('requisitos','atributos')):
            raise ValueError('Revisão inválida.')
        for k in ('escolhas','descartes'):
            if not isinstance(review.get(k, {}), dict): raise ValueError('Revisão inválida.')
        context = None
        product_context = None
        if catalog_id:
            catalog = db.query(CrmCatalogProduct).filter(CrmCatalogProduct.id == catalog_id,
                      CrmCatalogProduct.tenant_id == current_user.tenant_id).first()
            if catalog is None: raise HTTPException(404, 'Produto não encontrado.')
            product_context = {'id':catalog.id, 'sku':catalog.sku, 'modelo':catalog.model,
                               'pn_fabricante':catalog.manufacturer_part_number, 'hardware':hardware}
        if item_id:
            item = db.query(CrmNoticeProduct).filter(CrmNoticeProduct.id == item_id,
                         CrmNoticeProduct.tenant_id == current_user.tenant_id).first()
            if item is None: raise HTTPException(404, 'Item não encontrado.')
            context = {'id':item.id, 'notice_id':item.notice_id, 'descricao':item.description}
        source = await _read(edital, edital_inicio, edital_fim)
        if source is None:
            if not context: raise ValueError('Envie o PDF do item ou selecione um item da triagem.')
            import hashlib
            text = context['descricao'] or ''
            source = {'arquivo':'Descrição cadastrada na triagem', 'hash':hashlib.sha256(text.encode()).hexdigest(),
                      'documento_id':item_id, 'versao_documento':1, 'total_paginas':None,
                      'paginas':[{'pagina':None,'texto':text}]}
        supplied = await _read(datasheet, datasheet_inicio, datasheet_fim)
        required = await run_in_threadpool(extract_document, source)
        offered = await run_in_threadpool(extract_document, supplied, offered=True)
        if product_context and not hardware.strip():
            offered['pendencias'].append({'id':'hardware-nao-confirmado','pagina':None,
                                         'trecho':'Revisão de hardware não informada para o produto selecionado.',
                                         'motivo':'Confira a versão física do produto e a versão do datasheet.', 'bloqueante':True})
        if product_context:
            import re
            model=product_context['pn_fabricante']
            if not model or model in ('-','N/C'): model=product_context['modelo']
            token=re.sub(r'[^a-z0-9]','',str(model or '').lower())
            pattern=r'(?<![a-z0-9])'+r'[\s\-_/]*'.join(re.escape(c) for c in token)+r'(?![a-z0-9])'
            body='\n'.join(p['texto'] for p in supplied['paginas']).lower()
            if not token or not re.search(pattern,body):
                offered['pendencias'].append({'id':'modelo-nao-identificado','pagina':None,
                                             'trecho':str(model or 'PN do fabricante não disponível'),
                                             'motivo':'O modelo selecionado não foi identificado nas páginas do datasheet. Confira a fonte.',
                                             'bloqueante':True})
        result = compare_extractions(required, offered, review, category=categoria)
        from datetime import datetime, timezone
        result['revisao'] = {**review, 'usuario_id':current_user.id,
                            'registrada_em':datetime.now(timezone.utc).isoformat()}
        return {'requisitos':required, 'produto':offered, 'comparacao':result,
                'item_triagem':context, 'produto_catalogo':product_context}
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
