from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .. import audit
from ..crypto import vault
from ..db import get_db, now
from ..security import require_pelapor, verify_password
from ..services import kyc
from ..services import reports as svc
from ..services.attachments import delete_attachment, save_upload
from .common import Timer, cipher_query

router = APIRouter(prefix="/api/me", tags=["me"])


def _ktp_row(db, user_id):
    return db.execute("SELECT * FROM attachments WHERE owner_id=? AND kind='ktp'", (user_id,)).fetchone()


@router.get("/profile")
def profile(cipher: str = Depends(cipher_query), user=Depends(require_pelapor), db=Depends(get_db)):
    with Timer() as t:
        data = {f: vault.read_text(db, "user", user["id"], f, cipher) for f in svc.PROFILE_FIELDS}
    audit.log(db, user, "me.view_profile", "user", user["id"], f"cipher={cipher}")
    db.commit()
    return {"cipher": cipher, "verified": True, "decrypt_ms": t.ms, "data": data}


@router.get("/ktp")
def ktp_info(user=Depends(require_pelapor), db=Depends(get_db)):
    row = _ktp_row(db, user["id"])
    out = {"exists": row is not None, "verification": kyc.summary(db, user["id"]),
           "history": kyc.history(db, user["id"]), "views": kyc.views(db, user["id"])}
    if row:
        out.update(id=row["id"], mime=row["mime"], size=row["size"], created_at=row["created_at"],
                   filename=vault.read_text(db, "attachment", row["id"], "filename"))
    return out


@router.post("/ktp", status_code=201)
def upload_ktp(file: UploadFile = File(...), user=Depends(require_pelapor), db=Depends(get_db)):
    old = _ktp_row(db, user["id"])
    info = save_upload(db, file, owner_id=user["id"], kind="ktp", report_id=None)
    if old:
        delete_attachment(db, old["id"])
    kyc.submitted(db, user, info["id"])
    audit.log(db, user, "me.upload_ktp", "attachment", info["id"])
    db.commit()
    return {**info, "verification": kyc.summary(db, user["id"])}


@router.get("/export")
def export(user=Depends(require_pelapor), db=Depends(get_db)):
    uid = user["id"]
    reports = []
    for row in db.execute("SELECT * FROM reports WHERE owner_id=? ORDER BY created_at", (uid,)).fetchall():
        reports.append({
            "id": row["id"], "category": row["category"], "status": row["status"],
            "incident_date": row["incident_date"], "created_at": row["created_at"],
            **svc.report_fields(db, row["id"]),
            "attachments": svc.list_attachments(db, row, viewer="owner"),
            "events": svc.list_events(db, row["id"]),
        })
    payload = {
        "exported_at": now(),
        "profile": {f: vault.read_text(db, "user", uid, f) for f in svc.PROFILE_FIELDS},
        "ktp": ktp_info(user, db),
        "reports": reports,
        "note": "Attachment file contents can be downloaded individually from the report page.",
    }
    audit.log(db, user, "me.export", "user", uid)
    db.commit()
    return JSONResponse(payload, headers={"Content-Disposition": 'attachment; filename="my-data-safe-report.json"'})


class DeleteIn(BaseModel):
    password: str = Field(max_length=64)


@router.delete("", status_code=204)
def delete_account(body: DeleteIn, user=Depends(require_pelapor), db=Depends(get_db)):
    row = db.execute("SELECT password_hash FROM users WHERE id=?", (user["id"],)).fetchone()
    if not verify_password(body.password, row["password_hash"]):
        raise HTTPException(403, "Incorrect password")
    vault.delete_owner(db, user["id"])
    db.execute("DELETE FROM users WHERE id=?", (user["id"],))
    audit.log(db, user, "me.delete_account", "user", user["id"])
    db.commit()
