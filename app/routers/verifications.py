from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from .. import audit
from ..crypto import vault
from ..db import get_db
from ..security import require_petugas
from ..services import kyc
from ..services import reports as svc

router = APIRouter(prefix="/api/officer/verifications", tags=["verifications"])

ORDER = {"menunggu": 0, "verifikasi_ulang": 1, "ditolak": 2, "terverifikasi": 3, "belum": 4}


class DecisionIn(BaseModel):
    decision: Literal["terverifikasi", "ditolak"]
    note: str | None = Field(None, max_length=1000)


class FlagIn(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)


def _pelapor(db, user_id: str):
    row = db.execute("SELECT id, created_at FROM users WHERE id=? AND role='pelapor'", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Reporter not found")
    return row


def _last(db, user_id, action):
    r = db.execute("SELECT created_at FROM ktp_events WHERE user_id=? AND action=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
                   (user_id, action)).fetchone()
    return r["created_at"] if r else None


@router.get("")
def queue(status: str | None = Query(None), user=Depends(require_petugas), db=Depends(get_db)):
    out = []
    for u in db.execute("SELECT id, created_at FROM users WHERE role='pelapor'").fetchall():
        st = kyc.status_of(db, u["id"])
        if status and st != status:
            continue
        out.append({
            "user_id": u["id"],
            "name": svc.masked_reporter(db, u["id"])["name"],
            "status": st,
            "label": kyc.STATUS_LABEL[st],
            "submitted_at": _last(db, u["id"], "diajukan"),
            "is_resubmission": _last(db, u["id"], "verifikasi_ulang") is not None
            or _last(db, u["id"], "ditolak") is not None,
            "report_count": db.execute("SELECT COUNT(*) FROM reports WHERE owner_id=?", (u["id"],)).fetchone()[0],
        })
    out.sort(key=lambda x: (ORDER[x["status"]], x["submitted_at"] or ""))
    return out


@router.get("/{user_id}")
def detail(user_id: str, user=Depends(require_petugas), db=Depends(get_db)):
    _pelapor(db, user_id)
    can_view = kyc.officer_can_view(db, user_id)
    out = {
        "user_id": user_id,
        "verification": kyc.summary(db, user_id),
        "reporter": svc.masked_reporter(db, user_id),
        "can_view_ktp": can_view,
        "history": kyc.history(db, user_id),
        "views": kyc.views(db, user_id),
    }
    if can_view:
        att = kyc.ktp_attachment(db, user_id)
        out["registered"] = {"full_name": vault.read_text(db, "user", user_id, "full_name"),
                             "nik": vault.read_text(db, "user", user_id, "nik")}
        out["ktp"] = {"mime": att["mime"], "size": att["size"], "uploaded_at": att["created_at"]}
        audit.log(db, user, "officer.open_verification", "user", user_id)
        db.commit()
    return out


@router.get("/{user_id}/ktp")
def preview_ktp(user_id: str, user=Depends(require_petugas), db=Depends(get_db)):
    _pelapor(db, user_id)
    if not kyc.officer_can_view(db, user_id):
        audit.log(db, user, "officer.view_ktp_denied", "user", user_id)
        db.commit()
        raise HTTPException(403, "Access to ID card is closed. ID card can only be opened while awaiting verification.")
    att = kyc.ktp_attachment(db, user_id)
    path, ms = vault.decrypt_to_tempfile(db, "attachment", att["id"], "content")
    audit.log(db, user, kyc.VIEW_ACTION, "user", user_id, f"attachment={att['id'][:8]}")
    db.commit()
    return FileResponse(
        path, media_type=att["mime"],
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote('id-card-preview')}",
                 "Cache-Control": "no-store", "X-Integrity": "verified", "X-Preview": "original",
                 "Content-Security-Policy": "sandbox; default-src 'none'"},
        background=BackgroundTask(path.unlink, missing_ok=True),
    )


@router.post("/{user_id}/decision")
def decision(user_id: str, body: DecisionIn, user=Depends(require_petugas), db=Depends(get_db)):
    _pelapor(db, user_id)
    kyc.decide(db, user, user_id, body.decision, body.note)
    audit.log(db, user, f"officer.ktp_{body.decision}", "user", user_id)
    db.commit()
    return kyc.summary(db, user_id)


@router.post("/{user_id}/flag")
def flag(user_id: str, body: FlagIn, user=Depends(require_petugas), db=Depends(get_db)):
    _pelapor(db, user_id)
    kyc.flag(db, user, user_id, body.reason)
    audit.log(db, user, "officer.ktp_flag", "user", user_id)
    db.commit()
    return kyc.summary(db, user_id)
