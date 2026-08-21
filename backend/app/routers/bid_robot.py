from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.services import portal_automation
from app.services.bid_robot import (
    BidRobotStore,
    create_session,
    execute_authorized_bid,
    recommend_bid,
    register_chat_message,
    register_confirmed_bid,
    sync_portal_session,
    update_market_bid,
)


router = APIRouter(prefix="/bid-robot", tags=["robo-lances"])
store = BidRobotStore()


class BidLotPayload(BaseModel):
    number: str = Field(..., min_length=1)
    description: str = ""
    quantity: float = Field(1, gt=0)
    unit_cost: float = Field(0, ge=0)
    current_best_bid: float | None = Field(None, gt=0)
    decrement: float = Field(0.01, gt=0)
    minimum_margin_percent: float = Field(0, ge=0)
    maximum_total_bid: float | None = Field(None, gt=0)


class BidSessionPayload(BaseModel):
    portal: Literal["BLL", "BNC", "COMPRAS_GOV"]
    process_number: str = Field(..., min_length=1)
    entity: str = Field(..., min_length=1)
    dispute_at: str | None = None
    mode: Literal["assistido", "autorizado"] = "assistido"
    lots: list[BidLotPayload] = Field(..., min_length=1)


class MarketBidPayload(BaseModel):
    current_best_bid: float = Field(..., gt=0)


class ConfirmBidPayload(BaseModel):
    bid_value: float = Field(..., gt=0)
    source: Literal["manual", "authorized_adapter"] = "manual"


class AutoBidPayload(BaseModel):
    dry_run: bool = False


class ChatMessagePayload(BaseModel):
    message: str = Field(..., min_length=1)


class PortalSyncPayload(BaseModel):
    portal_session_url: str = Field(..., min_length=1)


@router.get("/sessions")
def list_bid_sessions(current_user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    return [_serialize_session(session) for session in store.list_sessions(current_user.tenant_id)]


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
def create_bid_session(
    payload: BidSessionPayload,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    session = create_session(
        tenant_id=current_user.tenant_id,
        portal=payload.portal,
        process_number=payload.process_number,
        entity=payload.entity,
        dispute_at=payload.dispute_at,
        mode=payload.mode,
        lots=[lot.dict() for lot in payload.lots],
    )
    store.save_session(session)
    return _serialize_session(session)


@router.get("/sessions/{session_id}")
def get_bid_session(session_id: str, current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    session = store.get_session(current_user.tenant_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada")
    return _serialize_session(session)


@router.post("/sessions/{session_id}/lots/{lot_id}/market-bid")
def update_bid_market(
    session_id: str,
    lot_id: str,
    payload: MarketBidPayload,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    session = store.get_session(current_user.tenant_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada")
    try:
        session = update_market_bid(session, lot_id, payload.current_best_bid)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    store.save_session(session)
    return _serialize_session(session)


@router.post("/sessions/{session_id}/lots/{lot_id}/confirm")
def confirm_bid(
    session_id: str,
    lot_id: str,
    payload: ConfirmBidPayload,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    session = store.get_session(current_user.tenant_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada")
    try:
        session = register_confirmed_bid(session, lot_id, payload.bid_value, payload.source)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    store.save_session(session)
    return _serialize_session(session)


@router.post("/sessions/{session_id}/lots/{lot_id}/auto-bid")
def auto_bid(
    session_id: str,
    lot_id: str,
    payload: AutoBidPayload,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    session = store.get_session(current_user.tenant_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada")
    try:
        session = execute_authorized_bid(session, lot_id, dry_run=payload.dry_run)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    store.save_session(session)
    return _serialize_session(session)


@router.post("/sessions/{session_id}/chat")
def add_chat_message(
    session_id: str,
    payload: ChatMessagePayload,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    session = store.get_session(current_user.tenant_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada")
    session = register_chat_message(session, payload.message, source="manual")
    store.save_session(session)
    return _serialize_session(session)


@router.post("/sessions/{session_id}/lots/{lot_id}/sync-portal")
def sync_portal(
    session_id: str,
    lot_id: str,
    payload: PortalSyncPayload,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    session = store.get_session(current_user.tenant_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada")
    try:
        session = sync_portal_session(session, lot_id, payload.portal_session_url)
    except portal_automation.PortalCredentialsMissing as exc:
        raise HTTPException(status_code=412, detail=str(exc)) from exc
    except portal_automation.PortalAutomationUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    store.save_session(session)
    return _serialize_session(session)


def _serialize_session(session) -> dict[str, Any]:
    data = {
        "id": session.id,
        "portal": session.portal,
        "process_number": session.process_number,
        "entity": session.entity,
        "dispute_at": session.dispute_at,
        "mode": session.mode,
        "status": session.status,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "lots": [],
        "events": [event.__dict__ for event in session.events[:30]],
    }
    for lot in session.lots:
        lot_data = lot.__dict__.copy()
        lot_data["recommendation"] = recommend_bid(lot)
        data["lots"].append(lot_data)
    return data
