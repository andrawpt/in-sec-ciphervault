from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from .. import audit
from ..crypto import vault
from ..db import get_db, new_id, now
from ..security import blind_index, create_token, get_current_user, hash_password, verify_password
from ..validators import EMAIL_RE, NIK_RE, PHONE_RE

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=10, max_length=64)
    full_name: str = Field(min_length=3, max_length=100)
    nik: str
    phone: str
    consent: bool

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Invalid email format")
        return v

    @field_validator("full_name")
    @classmethod
    def _name(cls, v: str) -> str:
        return " ".join(v.split())

    @field_validator("nik")
    @classmethod
    def _nik(cls, v: str) -> str:
        v = v.strip()
        if not NIK_RE.match(v):
            raise ValueError("National ID (NIK) must be 16 digits")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        v = v.replace(" ", "").replace("-", "")
        if not PHONE_RE.match(v):
            raise ValueError("Invalid phone number (example: 081234567890)")
        return v


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=64)


@router.post("/register", status_code=201)
def register(body: RegisterIn, db=Depends(get_db)):
    if not body.consent:
        raise HTTPException(400, "Consent to personal data processing is required")
    bidx = blind_index(body.email)
    if db.execute("SELECT 1 FROM users WHERE email_bidx=?", (bidx,)).fetchone():
        raise HTTPException(409, "Email is already registered")
    uid = new_id()
    db.execute(
        "INSERT INTO users (id, email_bidx, password_hash, role, consent_at, created_at) VALUES (?,?,?,?,?,?)",
        (uid, bidx, hash_password(body.password), "pelapor", now(), now()),
    )
    for field in ("email", "full_name", "nik", "phone"):
        vault.store_text(db, getattr(body, field), owner_id=uid, ref_type="user", ref_id=uid, field=field)
    audit.log(db, {"id": uid, "role": "pelapor"}, "auth.register", "user", uid)
    db.commit()
    return {"id": uid}


@router.post("/login")
def login(body: LoginIn, db=Depends(get_db)):
    row = db.execute("SELECT * FROM users WHERE email_bidx=?", (blind_index(body.email),)).fetchone()
    if not verify_password(body.password, row["password_hash"] if row else None):
        audit.log(db, None, "auth.login_failed")
        db.commit()
        raise HTTPException(401, "Incorrect email or password")
    audit.log(db, {"id": row["id"], "role": row["role"]}, "auth.login", "user", row["id"])
    db.commit()
    return {"access_token": create_token(row["id"], row["role"]), "token_type": "bearer", "role": row["role"]}


@router.get("/me")
def me(user=Depends(get_current_user), db=Depends(get_db)):
    return {
        "id": user["id"],
        "role": user["role"],
        "email": vault.read_text(db, "user", user["id"], "email"),
        "full_name": vault.read_text(db, "user", user["id"], "full_name"),
    }
