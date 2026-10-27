import hashlib
import hmac
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings
from .db import get_db

_bearer = HTTPBearer(auto_error=False)
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt(12))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()


def verify_password(password: str, hashed: str | None) -> bool:
    if hashed is None:
        bcrypt.checkpw(password.encode(), _DUMMY_HASH)
        return False
    return bcrypt.checkpw(password.encode(), hashed.encode())


def blind_index(email: str) -> str:
    norm = email.strip().lower().encode()
    return hmac.new(get_settings().blind_index_key, norm, hashlib.sha256).hexdigest()


def create_token(user_id: str, role: str) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.jwt_exp_minutes)
    return jwt.encode({"sub": user_id, "role": role, "exp": exp}, s.jwt_secret, algorithm="HS256")


def get_current_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer), db=Depends(get_db)) -> dict:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session, please sign in again",
                                 headers={"WWW-Authenticate": "Bearer"})
    if cred is None:
        raise unauthorized
    try:
        payload = jwt.decode(cred.credentials, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise unauthorized
    row = db.execute("SELECT id, role FROM users WHERE id=?", (payload.get("sub"),)).fetchone()
    if row is None:
        raise unauthorized
    return {"id": row["id"], "role": row["role"]}


def require_role(role: str):
    def dep(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] != role:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied for this role")
        return user
    return dep


require_pelapor = require_role("pelapor")
require_petugas = require_role("petugas")
