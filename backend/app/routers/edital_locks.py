from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.auth.models import User


router = APIRouter(prefix="/editais/{edital_id}/lock", tags=["editais"])

LOCK_TTL = timedelta(seconds=45)
_LOCKS: dict[str, dict] = {}
_LOCKS_GUARD = Lock()


class LockHeartbeat(BaseModel):
    tab_id: str


def _key(user: User, edital_id: int) -> str:
    tenant = user.tenant.slug if user.tenant else str(user.tenant_id)
    return f"{tenant}:{edital_id}"


def _serialize(lock: dict | None, current_user: User, tab_id: str | None = None) -> dict:
    if not lock:
        return {"active": False, "owned_by_me": False, "blocked": False, "lock": None}

    owned_by_me = lock.get("user_id") == current_user.id and (tab_id is None or lock.get("tab_id") == tab_id)
    return {
        "active": True,
        "owned_by_me": owned_by_me,
        "blocked": not owned_by_me,
        "lock": {
            "user_id": lock.get("user_id"),
            "owner_name": lock.get("owner_name"),
            "owner_email": lock.get("owner_email"),
            "role": lock.get("role"),
            "tab_id": lock.get("tab_id"),
            "updated_at": lock.get("updated_at").isoformat(),
            "expires_at": lock.get("expires_at").isoformat(),
        },
    }


def _active(lock: dict | None, now: datetime) -> bool:
    return bool(lock and lock.get("expires_at") and lock["expires_at"] > now)


@router.get("")
def get_lock(
    edital_id: int,
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    key = _key(current_user, edital_id)
    with _LOCKS_GUARD:
      lock = _LOCKS.get(key)
      if not _active(lock, now):
          _LOCKS.pop(key, None)
          lock = None
      return _serialize(lock, current_user)


@router.post("")
def heartbeat_lock(
    edital_id: int,
    payload: LockHeartbeat,
    current_user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    key = _key(current_user, edital_id)
    with _LOCKS_GUARD:
        current = _LOCKS.get(key)
        if _active(current, now) and (
            current.get("user_id") != current_user.id or current.get("tab_id") != payload.tab_id
        ):
            return _serialize(current, current_user, payload.tab_id)

        lock = {
            "user_id": current_user.id,
            "owner_name": current_user.full_name or current_user.email,
            "owner_email": current_user.email,
            "role": current_user.role,
            "tab_id": payload.tab_id,
            "updated_at": now,
            "expires_at": now + LOCK_TTL,
        }
        _LOCKS[key] = lock
        return _serialize(lock, current_user, payload.tab_id)


@router.delete("")
def release_lock(
    edital_id: int,
    payload: LockHeartbeat,
    current_user: User = Depends(get_current_user),
):
    key = _key(current_user, edital_id)
    with _LOCKS_GUARD:
        current = _LOCKS.get(key)
        if current and current.get("user_id") == current_user.id and current.get("tab_id") == payload.tab_id:
            _LOCKS.pop(key, None)
        return {"released": True}

