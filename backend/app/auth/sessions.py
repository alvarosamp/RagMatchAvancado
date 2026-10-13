"""Revocable browser sessions with rotating, purpose-bound refresh tokens."""
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, Response
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.auth.models import AuthSession, User
from app.auth.security import ALGORITHM, SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token

ACCESS_COOKIE = os.getenv('AUTH_COOKIE_NAME', 'access_token')
REFRESH_COOKIE = os.getenv('AUTH_REFRESH_COOKIE_NAME', ACCESS_COOKIE + '_refresh')
SESSION_HOURS = int(os.getenv('AUTH_SESSION_HOURS', '12'))
REMEMBER_DAYS = int(os.getenv('AUTH_REMEMBER_DAYS', '30'))
if SESSION_HOURS <= 0 or REMEMBER_DAYS <= 0:
    raise ValueError("Os prazos de sessão devem ser positivos")
ROTATION_GRACE_SECONDS = 15


def now():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def cookie_options():
    production = os.getenv('APP_ENV', '').lower() in {'production', 'prod'}
    return dict(path='/', httponly=True,
                secure=os.getenv('AUTH_COOKIE_SECURE', '1' if production else '0').lower() in {'1', 'true', 'yes'},
                samesite=os.getenv('AUTH_COOKIE_SAMESITE', 'lax').lower())


def clear_cookies(response: Response):
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.delete_cookie(name, **cookie_options())
    response.headers['Cache-Control'] = 'no-store'


def refresh_claims(token):
    claims = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    if claims.get('type') != 'refresh' or not isinstance(claims.get('sid'), str):
        raise JWTError('Wrong token purpose')
    if type(claims.get('generation')) is not int:
        raise JWTError('Invalid generation')
    return claims


def issue_cookies(response, user, session):
    token = create_access_token(user.email, user.tenant.slug, user.role, user.id,
                                auth_version=user.auth_version or 0, session_id=session.id)
    refresh = jwt.encode({'type': 'refresh', 'sid': session.id, 'generation': session.generation,
                          'exp': int(aware(session.expires_at).timestamp())}, SECRET_KEY, algorithm=ALGORITHM)
    options = cookie_options()
    access_age = min(ACCESS_TOKEN_EXPIRE_MINUTES * 60, max(0, int((aware(session.expires_at) - now()).total_seconds())))
    persistent_access = dict(max_age=access_age, expires=access_age) if session.remember_me else {}
    persistent_refresh = dict(max_age=max(0, int((aware(session.expires_at) - now()).total_seconds())),
                              expires=aware(session.expires_at)) if session.remember_me else {}
    response.set_cookie(ACCESS_COOKIE, token, **options, **persistent_access)
    response.set_cookie(REFRESH_COOKIE, refresh, **options, **persistent_refresh)
    response.headers['Cache-Control'] = 'no-store'
    return token


def start_session(db, user, response, remember_me=False):
    session = AuthSession(id=secrets.token_urlsafe(32), user_id=user.id,
                          auth_version=user.auth_version or 0, generation=0, remember_me=remember_me,
                          expires_at=now() + (timedelta(days=REMEMBER_DAYS) if remember_me else timedelta(hours=SESSION_HOURS)))
    db.add(session)
    db.commit()
    return issue_cookies(response, user, session)


def require_refresh_header(request):
    # A cross-origin HTML form cannot add this header. Origin validation is
    # also performed by the existing middleware; CORS must not allow strangers.
    if request.headers.get('x-session-refresh') != '1':
        raise HTTPException(403, 'Renovação exige uma requisição do aplicativo.')


def renew_session(db: Session, request: Request, response: Response):
    require_refresh_header(request)
    invalid = HTTPException(401, 'Sessão encerrada ou expirada. Faça login novamente.')
    try:
        claims = refresh_claims(request.cookies.get(REFRESH_COOKIE, ''))
    except JWTError:
        raise invalid
    session = db.query(AuthSession).filter_by(id=claims['sid']).with_for_update().first()
    current = now()
    if not session or session.revoked_at or aware(session.expires_at) <= current:
        raise invalid
    user = db.query(User).filter_by(id=session.user_id).first()
    if not user or not user.is_active or not user.tenant or not user.tenant.is_active:
        raise invalid
    if (user.auth_version or 0) != session.auth_version:
        raise invalid
    generation = claims['generation']
    if generation == session.generation:
        session.generation += 1
        session.rotated_at = current
    elif generation == session.generation - 1 and session.rotated_at and (
            current - aware(session.rotated_at)).total_seconds() <= ROTATION_GRACE_SECONDS:
        # Concurrent tabs receive the same current token, without extending
        # the original session deadline or racing cookie generations.
        pass
    else:
        session.revoked_at = current
        db.commit()
        raise invalid
    db.commit()
    token = issue_cookies(response, user, session)
    return user, token


def revoke_session(db, request):
    sid = None
    try:
        sid = refresh_claims(request.cookies.get(REFRESH_COOKIE, '')).get('sid')
    except JWTError:
        # Logout still works if the refresh token has expired.
        from app.auth.security import decode_access_token
        try:
            sid = decode_access_token(request.cookies.get(ACCESS_COOKIE, '')).get('sid')
        except JWTError:
            pass
    if sid:
        session = db.query(AuthSession).filter_by(id=sid).with_for_update().first()
        if session:
            session.revoked_at = now()
            db.commit()
