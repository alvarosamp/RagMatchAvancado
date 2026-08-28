from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Literal
from uuid import uuid4


Portal = Literal["BLL", "BNC", "COMPRAS_GOV"]
SessionStatus = Literal["draft", "watching", "paused", "closed"]
BidMode = Literal["assistido", "autorizado"]


@dataclass
class BidEvent:
    id: str
    type: str
    message: str
    created_at: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class BidLot:
    id: str
    number: str
    description: str
    quantity: float
    unit_cost: float
    current_best_bid: float | None
    decrement: float
    minimum_margin_percent: float
    maximum_total_bid: float | None = None
    status: str = "monitoring"
    last_recommended_bid: float | None = None
    last_confirmed_bid: float | None = None


@dataclass
class BidSession:
    id: str
    tenant_id: int
    portal: Portal
    process_number: str
    entity: str
    dispute_at: str | None
    mode: BidMode
    status: SessionStatus
    created_at: str
    updated_at: str
    lots: list[BidLot] = field(default_factory=list)
    events: list[BidEvent] = field(default_factory=list)


class BidRobotStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("data") / "bid_robot_state.json"
        self._lock = RLock()

    def list_sessions(self, tenant_id: int) -> list[BidSession]:
        return [
            session
            for session in self._load()
            if session.tenant_id == tenant_id
        ]

    def get_session(self, tenant_id: int, session_id: str) -> BidSession | None:
        return next(
            (session for session in self.list_sessions(tenant_id) if session.id == session_id),
            None,
        )

    def save_session(self, session: BidSession) -> BidSession:
        with self._lock:
            sessions = self._load()
            now = _now()
            session.updated_at = now
            replaced = False
            for index, existing in enumerate(sessions):
                if existing.id == session.id and existing.tenant_id == session.tenant_id:
                    sessions[index] = session
                    replaced = True
                    break
            if not replaced:
                sessions.append(session)
            self._write(sessions)
            return session

    def _load(self) -> list[BidSession]:
        with self._lock:
            if not self.path.exists():
                return []
            raw = json.loads(self.path.read_text(encoding="utf-8") or "[]")
            return [_session_from_dict(item) for item in raw]

    def _write(self, sessions: list[BidSession]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(session) for session in sessions]
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def create_session(
    *,
    tenant_id: int,
    portal: Portal,
    process_number: str,
    entity: str,
    dispute_at: str | None,
    mode: BidMode,
    lots: list[dict[str, Any]],
) -> BidSession:
    now = _now()
    session = BidSession(
        id=str(uuid4()),
        tenant_id=tenant_id,
        portal=portal,
        process_number=process_number.strip(),
        entity=entity.strip(),
        dispute_at=dispute_at,
        mode=mode,
        status="watching",
        created_at=now,
        updated_at=now,
        lots=[_lot_from_payload(lot) for lot in lots],
        events=[
            BidEvent(
                id=str(uuid4()),
                type="session_created",
                message="Sessao de lances criada para acompanhamento auditavel.",
                created_at=now,
            )
        ],
    )
    return session


def recommend_bid(lot: BidLot) -> dict[str, Any]:
    cost_total = round(lot.unit_cost * lot.quantity, 2)
    floor_bid = round(cost_total * (1 + lot.minimum_margin_percent / 100), 2)
    ceiling = lot.maximum_total_bid or lot.current_best_bid
    if ceiling is None:
        suggested = floor_bid
        reason = "Sem menor lance atual; use o piso calculado como referencia inicial."
    else:
        suggested = round(max(floor_bid, ceiling - lot.decrement), 2)
        reason = "Sugestao calculada pelo menor lance atual, decremento e margem minima."
    can_bid = ceiling is None or suggested < ceiling
    if ceiling is not None and floor_bid >= ceiling:
        can_bid = False
        suggested = None
        reason = "Menor lance atual ja esta abaixo do piso de margem configurado."
    margin = None
    if suggested:
        margin = round(((suggested - cost_total) / suggested) * 100, 2) if suggested else None
    return {
        "lot_id": lot.id,
        "suggested_bid": suggested,
        "can_bid": can_bid,
        "floor_bid": floor_bid,
        "cost_total": cost_total,
        "estimated_margin_percent": margin,
        "reason": reason,
    }


def register_confirmed_bid(session: BidSession, lot_id: str, bid_value: float, source: str) -> BidSession:
    lot = _find_lot(session, lot_id)
    lot.last_confirmed_bid = round(float(bid_value), 2)
    lot.current_best_bid = round(float(bid_value), 2)
    session.events.insert(
        0,
        BidEvent(
            id=str(uuid4()),
            type="bid_confirmed",
            message=f"Lance de R$ {bid_value:,.2f} registrado no lote {lot.number}.",
            created_at=_now(),
            payload={"lot_id": lot_id, "bid_value": bid_value, "source": source},
        ),
    )
    return session


def execute_authorized_bid(session: BidSession, lot_id: str, *, dry_run: bool = False) -> BidSession:
    if session.mode != "autorizado":
        raise ValueError("Sessao precisa estar em modo autorizado para envio automatico")
    lot = _find_lot(session, lot_id)
    recommendation = recommend_bid(lot)
    bid_value = recommendation["suggested_bid"]
    if not recommendation["can_bid"] or not bid_value:
        raise ValueError("Nao ha lance seguro para envio automatico")

    adapter_result = _send_to_authorized_adapter(session, lot, recommendation, dry_run=dry_run)
    lot.last_recommended_bid = bid_value
    if not dry_run:
        lot.last_confirmed_bid = bid_value
        lot.current_best_bid = bid_value

    event_type = "auto_bid_dry_run" if dry_run else "auto_bid_sent"
    message = (
        f"Simulacao automatica preparada para o lote {lot.number}."
        if dry_run
        else f"Lance automatico de R$ {bid_value:,.2f} enviado ao lote {lot.number}."
    )
    session.events.insert(
        0,
        BidEvent(
            id=str(uuid4()),
            type=event_type,
            message=message,
            created_at=_now(),
            payload={
                "lot_id": lot_id,
                "bid_value": bid_value,
                "portal": session.portal,
                "adapter_result": adapter_result,
            },
        ),
    )
    return session


def update_market_bid(session: BidSession, lot_id: str, current_best_bid: float) -> BidSession:
    lot = _find_lot(session, lot_id)
    lot.current_best_bid = round(float(current_best_bid), 2)
    recommendation = recommend_bid(lot)
    lot.last_recommended_bid = recommendation["suggested_bid"]
    session.events.insert(
        0,
        BidEvent(
            id=str(uuid4()),
            type="market_update",
            message=f"Menor lance atualizado no lote {lot.number}.",
            created_at=_now(),
            payload={"lot_id": lot_id, "recommendation": recommendation},
        ),
    )
    return session


def register_chat_message(session: BidSession, message: str, source: str = "manual") -> BidSession:
    session.events.insert(
        0,
        BidEvent(
            id=str(uuid4()),
            type="chat_message",
            message=message,
            created_at=_now(),
            payload={"source": source},
        ),
    )
    return session


def sync_portal_session(session: BidSession, lot_id: str, portal_session_url: str) -> BidSession:
    """Loga no portal (BLL/BNC) com credenciais locais, le o menor lance e o chat
    da sessao, e atualiza o lote e a auditoria. Compras.gov.br nao e suportado aqui
    de proposito -- veja portal_automation.py.
    """
    from app.services import portal_automation

    result = portal_automation.sync_session(session.portal, portal_session_url)

    if result.current_best_bid is not None:
        session = update_market_bid(session, lot_id, result.current_best_bid)

    for message in result.chat_messages:
        session = register_chat_message(session, message, source="portal_sync")

    return session


def _send_to_authorized_adapter(
    session: BidSession,
    lot: BidLot,
    recommendation: dict[str, Any],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    url = _adapter_url(session.portal)
    if not url:
        raise RuntimeError(
            "Adaptador automatico nao configurado para este portal. "
            "Configure COMPRAS_GOV_BID_ADAPTER_URL para habilitar envio real."
        )
    payload = {
        "portal": session.portal,
        "process_number": session.process_number,
        "entity": session.entity,
        "session_id": session.id,
        "lot": asdict(lot),
        "recommendation": recommendation,
        "dry_run": dry_run,
        "created_at": _now(),
    }
    if url == "mock://success":
        return {"status": "accepted", "adapter": "mock", "dry_run": dry_run}

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers=_adapter_headers(),
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response_body = response.read().decode("utf-8") or "{}"
            try:
                data = json.loads(response_body)
            except json.JSONDecodeError:
                data = {"raw": response_body}
            return {"status": "accepted", "http_status": response.status, "response": data}
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Falha ao acionar adaptador automatico: {exc}") from exc


def _adapter_url(portal: Portal) -> str | None:
    if portal == "COMPRAS_GOV":
        return os.getenv("COMPRAS_GOV_BID_ADAPTER_URL")
    return os.getenv(f"{portal}_BID_ADAPTER_URL")


def _adapter_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = os.getenv("BID_ADAPTER_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _find_lot(session: BidSession, lot_id: str) -> BidLot:
    for lot in session.lots:
        if lot.id == lot_id:
            return lot
    raise ValueError("Lote nao encontrado")


def _lot_from_payload(payload: dict[str, Any]) -> BidLot:
    return BidLot(
        id=str(uuid4()),
        number=str(payload.get("number") or "1"),
        description=str(payload.get("description") or "").strip(),
        quantity=float(payload.get("quantity") or 1),
        unit_cost=float(payload.get("unit_cost") or 0),
        current_best_bid=_optional_float(payload.get("current_best_bid")),
        decrement=float(payload.get("decrement") or 0.01),
        minimum_margin_percent=float(payload.get("minimum_margin_percent") or 0),
        maximum_total_bid=_optional_float(payload.get("maximum_total_bid")),
    )


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _session_from_dict(data: dict[str, Any]) -> BidSession:
    return BidSession(
        id=data["id"],
        tenant_id=int(data["tenant_id"]),
        portal=data["portal"],
        process_number=data["process_number"],
        entity=data["entity"],
        dispute_at=data.get("dispute_at"),
        mode=data.get("mode", "assistido"),
        status=data.get("status", "watching"),
        created_at=data["created_at"],
        updated_at=data["updated_at"],
        lots=[BidLot(**lot) for lot in data.get("lots", [])],
        events=[BidEvent(**event) for event in data.get("events", [])],
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
