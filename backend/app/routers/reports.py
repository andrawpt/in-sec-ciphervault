from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator

from .. import audit
from ..crypto import vault
from ..db import get_db, new_id, now
from ..security import require_pelapor
from ..services import kyc
from ..services import reports as svc
from ..services.attachments import save_upload
from ..validators import CATEGORIES

router = APIRouter(prefix="/api/reports", tags=["reports"])


class ReportIn(BaseModel):
    category: str
    title: str = Field(min_length=5, max_length=120)
    chronology: str = Field(min_length=20, max_length=5000)
    incident_url: str | None = Field(None, max_length=2048)
    scammer_account: str | None = Field(None, max_length=200)
    incident_date: date | None = None
    consent: bool

    @field_validator("category")
    @classmethod
    def _cat(cls, v):
        if v not in CATEGORIES:
            raise ValueError("Unknown category")
        return v

    @field_validator("incident_date")
    @classmethod
    def _date(cls, v):
        if v and v > date.today():
            raise ValueError("Incident date cannot be in the future")
        return v


class NoteIn(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


@router.get("/categories")
def categories():
    return [{"value": k, "label": v} for k, v in CATEGORIES.items()]


@router.post("", status_code=201)
def create_report(body: ReportIn, user=Depends(require_pelapor), db=Depends(get_db)):
    kyc.require_verified(db, user["id"])
    if not body.consent:
        raise HTTPException(400, "Consent to data processing is required")
    rid, ts = new_id(), now()
    db.execute(
        "INSERT INTO reports (id, owner_id, category, status, incident_date, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (rid, user["id"], body.category, "diterima", body.incident_date.isoformat() if body.incident_date else None, ts, ts),
    )
    for f in svc.REPORT_FIELDS:
        value = getattr(body, f)
        vault.store_text(db, value.strip() if value else None, owner_id=user["id"], ref_type="report", ref_id=rid, field=f)
    report = svc.get_report_row(db, rid)
    svc.add_event(db, report, user, type_="status", to_status="diterima")
    audit.log(db, user, "report.create", "report", rid)
    db.commit()
    return {"id": rid}


@router.get("")
def my_reports(user=Depends(require_pelapor), db=Depends(get_db)):
    rows = db.execute("SELECT * FROM reports WHERE owner_id=? ORDER BY created_at DESC", (user["id"],)).fetchall()
    return [svc.report_summary(db, r) for r in rows]


@router.get("/{report_id}")
def report_detail(report_id: str, user=Depends(require_pelapor), db=Depends(get_db)):
    row = svc.get_report_row(db, report_id, owner_id=user["id"])
    return {
        **svc.report_summary(db, row),
        **svc.report_fields(db, report_id),
        "attachments": svc.list_attachments(db, row, viewer="owner"),
        "events": svc.list_events(db, report_id),
    }


@router.post("/{report_id}/attachments", status_code=201)
def add_attachment(
    report_id: str,
    kind: Literal["dokumen", "video"] = Form(...),
    file: UploadFile = File(...),
    share: bool = Form(False, description="Allow all officers to view this file while report is open"),
    user=Depends(require_pelapor),
    db=Depends(get_db),
):
    row = svc.get_report_row(db, report_id, owner_id=user["id"])
    if row["status"] in ("selesai", "ditolak"):
        raise HTTPException(409, "Report is closed")
    info = save_upload(db, file, owner_id=user["id"], kind=kind, report_id=report_id, share=share)
    db.execute("UPDATE reports SET updated_at=? WHERE id=?", (now(), report_id))
    audit.log(db, user, "attachment.upload", "attachment", info["id"], f"kind={kind} shared={info['shared']}")
    db.commit()
    return info


@router.post("/{report_id}/notes", status_code=201)
def add_note(report_id: str, body: NoteIn, user=Depends(require_pelapor), db=Depends(get_db)):
    row = svc.get_report_row(db, report_id, owner_id=user["id"])
    svc.add_event(db, row, user, type_="note", note=body.note)
    db.commit()
    return {"ok": True}
