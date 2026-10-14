from datetime import datetime, timezone
import hashlib
from pathlib import Path
import copy

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_role
from app.auth.models import User
from app.db.session import get_db
from app.crm.models import (CrmNotice, CrmNoticeProduct, CrmCatalogProduct, CrmCatalogProductDatasheet, CrmNoticeHistory,
                            CrmNoticeProductMatch, CrmNoticeProductMatchStatus, CrmNoticeProductMatchLevel)
from app.services import manual_match as manual
from app.services.match_item_export import build_crm_match_item_export
from app.services.crm_notice_list import invalidate_notice_list_cache

router = APIRouter(prefix='/crm/notices/{notice_id}/products/{item_id}/manual-match', tags=['match manual'])


class ImportRequest(BaseModel):
    json_text: str = Field(max_length=1_000_000)
    filename: str = Field(default='JSON do item', max_length=200)


class MatchDraft(BaseModel):
    state: dict
    base_revision: str
    catalog_product_id: str | None = None
    catalog_hash: str | None = None
    confirm: bool = False


def load_item(db, user, notice_id, item_id, *, lock=False):
    query = db.query(CrmNoticeProduct).filter_by(id=item_id, notice_id=notice_id, tenant_id=user.tenant_id)
    item = (query.with_for_update() if lock else query).first()
    notice = db.query(CrmNotice).filter_by(id=notice_id, tenant_id=user.tenant_id).first()
    if item is None or notice is None:
        raise HTTPException(404, 'Item do edital não encontrado.')
    return notice, item


def catalog_rows(db, user):
    return db.query(CrmCatalogProduct).filter_by(tenant_id=user.tenant_id, is_active=True).all()


def current_state(notice, item):
    saved = (item.raw_payload or {}).get('_manual_match')
    if isinstance(saved, dict):
        return manual.validate_state(saved)
    return manual.import_item(build_crm_match_item_export(notice, item), item, 'JSON atual do item')


def verify_documents(db, user, catalog, result):
    """Recheck source ownership and bytes at the moment of confirmation."""
    cache = {}
    for detail in result['detalhes']:
        if detail.get('atributo') == 'categoria' or detail.get('status') != 'ATENDE':
            continue
        for source in detail.get('fontes', []):
            value = source.get('valor')
            evidences = value.get('evidencias', []) if isinstance(value, dict) else []
            bound = False
            for evidence in evidences:
                if not isinstance(evidence, dict) or evidence.get('revisado') is not True:
                    continue
                document_id = evidence.get('documento_id')
                if not isinstance(document_id, str) or type(evidence.get('versao_documento')) is not int:
                    continue
                if document_id not in cache:
                    document = db.query(CrmCatalogProductDatasheet).filter_by(id=document_id,
                        catalog_product_id=catalog.id, tenant_id=user.tenant_id).first()
                    try:
                        cache[document_id] = (document.version, hashlib.sha256(Path(document.storage_path).read_bytes()).hexdigest()) if document else None
                    except OSError:
                        cache[document_id] = None
                actual = cache[document_id]
                if actual and actual == (evidence.get('versao_documento'), evidence.get('hash_documento')):
                    bound = True
            if not bound:
                raise HTTPException(409, 'Evidência ausente, alterada ou vinculada a outro produto. Revise a ficha técnica.')


@router.get('')
def get_manual_match(notice_id: str, item_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    notice, item = load_item(db, user, notice_id, item_id)
    try:
        state = current_state(notice, item)
        result = manual.preview(state, catalog_rows(db, user), state.get('selected_catalog_id'))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, 'base_revision': manual.revision(item),
            'item': {'id': item.id, 'numero': item.item_number, 'descricao': item.description},
            'selecionado': state.get('selected_catalog_id'), 'selecionado_status': state.get('selected_status')}


@router.post('/suggest')
def suggest_manual_match(notice_id: str, item_id: str,
                         db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    notice, item = load_item(db, user, notice_id, item_id)
    draft_item = copy.copy(item)
    draft_item.raw_payload = {k: v for k, v in (item.raw_payload or {}).items() if k != '_manual_match'}
    try:
        payload = build_crm_match_item_export(notice, draft_item)
        state = manual.import_item(payload, item, 'JSON atual do item — requisitos sugeridos')
        result = manual.preview(state, catalog_rows(db, user))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, 'base_revision': manual.revision(item)}


@router.post('/import')
def import_manual_match(notice_id: str, item_id: str, body: ImportRequest,
                        db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, item = load_item(db, user, notice_id, item_id)
    try:
        state = manual.import_item(manual.parse_json(body.json_text), item, body.filename)
        result = manual.preview(state, catalog_rows(db, user))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**result, 'base_revision': manual.revision(item)}


@router.post('/preview')
def preview_manual_match(notice_id: str, item_id: str, body: MatchDraft,
                         db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _, item = load_item(db, user, notice_id, item_id)
    if body.base_revision != manual.revision(item):
        raise HTTPException(409, 'O item mudou. Feche e abra o match novamente para conferir a versão atual.')
    try:
        return manual.preview(body.state, catalog_rows(db, user), body.catalog_product_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.put('')
def save_manual_match(notice_id: str, item_id: str, body: MatchDraft,
                      db: Session = Depends(get_db), user: User = Depends(require_role('admin', 'editor'))):
    _, item = load_item(db, user, notice_id, item_id, lock=True)
    if body.base_revision != manual.revision(item):
        raise HTTPException(409, 'O item mudou. Reabra o match antes de salvar.')
    try:
        state = manual.validate_state(body.state)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    # Saving mapped criteria cannot substitute a JSON belonging to another item.
    source = state.get('fonte_json')
    if source:
        try:
            manual.import_item(source['payload'], item, source.get('arquivo', 'JSON'))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    prior = (item.raw_payload or {}).get('_manual_match')
    result = None
    if body.confirm and not body.catalog_product_id:
        raise HTTPException(422, 'Escolha um produto antes de confirmar.')
    if body.catalog_product_id:
        if not state['categoria']:
            raise HTTPException(422, 'Escolha a categoria antes de selecionar um produto.')
        catalog = db.query(CrmCatalogProduct).filter_by(id=body.catalog_product_id, tenant_id=user.tenant_id,
                                                       is_active=True).with_for_update().first()
        if catalog is None:
            raise HTTPException(404, 'Produto ativo do catálogo não encontrado.')
        if body.catalog_hash != manual._hash(manual.catalog_payload(catalog)):
            raise HTTPException(409, 'A ficha do produto mudou. Atualize a comparação antes de salvar.')
        result = manual.comparison(state, manual.catalog_payload(catalog))
        if result['status'] == 'NAO_ATENDE':
            raise HTTPException(409, 'O produto não atende aos requisitos. Corrija a seleção antes de salvar.')
        if body.confirm and result['status'] != 'ATENDE':
            raise HTTPException(409, 'Há pontos ou evidências pendentes. Salve o candidato para revisão.')
        if body.confirm:
            verify_documents(db, user, catalog, result)
        match = db.query(CrmNoticeProductMatch).filter_by(notice_product_id=item.id, catalog_product_id=catalog.id,
                                                        tenant_id=user.tenant_id).first()
        if match is None:
            match = CrmNoticeProductMatch(tenant_id=user.tenant_id, notice_id=notice_id, notice_product_id=item.id,
                                          catalog_product_id=catalog.id, created_by=user.id)
            db.add(match)
        match.source_method = 'manual_progressive'
        match.status = CrmNoticeProductMatchStatus.CONFIRMED if body.confirm else CrmNoticeProductMatchStatus.SUGGESTED
        match.match_level = CrmNoticeProductMatchLevel.STRONG if body.confirm else CrmNoticeProductMatchLevel.POSSIBLE
        match.overall_score = result['score']
        match.technical_result = result
        match.rationale = 'Seleção humana por requisitos e filtros; sem IA.'
        state['selected_catalog_id'] = catalog.id
        state['selected_status'] = 'confirmado' if body.confirm else 'para_revisao'
        if body.confirm:
            item.catalog_product_id = catalog.id
            item.catalog_match_source = 'match_confirmed'
            item.catalog_match_confirmed_by = user.id
            item.catalog_match_confirmed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            item.catalog_match_model_version = 'manual_progressive'
            item.catalog_match_notes = 'Confirmado após comparação manual ponto a ponto.'
            item.catalog_lpu_version = catalog.lpu_version
            # Confirmation must not overwrite negotiated quantities or prices.
            db.query(CrmNoticeProductMatch).filter(CrmNoticeProductMatch.notice_product_id == item.id,
                CrmNoticeProductMatch.catalog_product_id != catalog.id, CrmNoticeProductMatch.tenant_id == user.tenant_id,
                CrmNoticeProductMatch.status == CrmNoticeProductMatchStatus.CONFIRMED).update(
                    {CrmNoticeProductMatch.status: CrmNoticeProductMatchStatus.REJECTED}, synchronize_session=False)
    else:
        # Edited requirements invalidate a previous draft selection. Existing
        # commercial attachments remain explicit; no silent relinking occurs.
        state.pop('selected_catalog_id', None)
        state.pop('selected_status', None)
    state['salvo_por'] = user.id
    state['salvo_em'] = datetime.now(timezone.utc).isoformat()
    item.raw_payload = {**(item.raw_payload or {}), '_manual_match': state}
    db.add(CrmNoticeHistory(tenant_id=user.tenant_id, notice_id=notice_id, user_id=user.id,
                          action='Match manual salvo', details={'notice_product_id': item.id,
                              'anterior': prior, 'atual': state, 'catalog_product_id': body.catalog_product_id,
                              'confirmado': body.confirm, 'technical_result': result}))
    db.commit()
    invalidate_notice_list_cache(user.tenant_id)
    return {'state': state, 'base_revision': manual.revision(item), 'comparacao': result,
            'mensagem': 'Match confirmado.' if body.confirm else ('Candidato salvo para revisão.' if body.catalog_product_id else 'Requisitos e filtros salvos.')}
