from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

from .. import audit
from ..crypto import vault
from ..db import get_db
from ..security import require_petugas
from ..services import access
from ..services import reports as svc
from ..services.preview import INLINE_MIMES, TEXT_EXTRACT_MIMES, PreviewUnavailable, extract_text
from ..validators import CATEGORIES, STATUSES, TRANSITIONS

router = APIRouter(prefix="/api/officer", tags=["officer"])


class StatusIn(BaseModel):
    status: str
    note: str | None = Field(None, max_length=2000)


class NoteIn(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


class AccessRequestIn(BaseModel):
    reason: str = Field(min_length=10, max_length=500)


@router.get("/reports")
def queue(status: str | None = Query(None), category: str | None = Query(None),
          user=Depends(require_petugas), db=Depends(get_db)):
    sql, args = "SELECT * FROM reports WHERE 1=1", []
    if status:
        sql += " AND status=?"
        args.append(status)
    if category:
        sql += " AND category=?"
        args.append(category)
    sql += " ORDER BY CASE status WHEN 'diterima' THEN 0 WHEN 'diverifikasi' THEN 1 WHEN 'ditindaklanjuti' THEN 2 ELSE 3 END, created_at DESC"
    out = []
    for r in db.execute(sql, args).fetchall():
        item = svc.report_summary(db, r)
        item["reporter_name"] = svc.masked_reporter(db, r["owner_id"])["name"]
        out.append(item)
    return out


@router.get("/reports/{report_id}")
def case_detail(report_id: str, user=Depends(require_petugas), db=Depends(get_db)):
    row = svc.get_report_row(db, report_id)
    audit.log(db, user, "officer.view_report", "report", report_id)
    db.commit()
    return {
        **svc.report_summary(db, row),
        **svc.report_fields(db, report_id),
        "reporter": svc.masked_reporter(db, row["owner_id"]),
        "attachments": svc.list_attachments(db, row, viewer="officer"),
        "events": svc.list_events(db, report_id),
        "allowed_transitions": TRANSITIONS[row["status"]],
    }


@router.patch("/reports/{report_id}/status")
def change_status(report_id: str, body: StatusIn, user=Depends(require_petugas), db=Depends(get_db)):
    row = svc.get_report_row(db, report_id)
    if body.status not in TRANSITIONS[row["status"]]:
        raise HTTPException(409, f"Status cannot be changed from '{row['status']}' to '{body.status}'")
    db.execute("UPDATE reports SET status=? WHERE id=?", (body.status, report_id))
    svc.add_event(db, row, user, type_="status", note=body.note, from_status=row["status"], to_status=body.status)
    audit.log(db, user, "officer.change_status", "report", report_id, f"{row['status']}->{body.status}")
    db.commit()
    return {"status": body.status}


@router.post("/reports/{report_id}/notes", status_code=201)
def add_note(report_id: str, body: NoteIn, user=Depends(require_petugas), db=Depends(get_db)):
    row = svc.get_report_row(db, report_id)
    svc.add_event(db, row, user, type_="note", note=body.note)
    audit.log(db, user, "officer.add_note", "report", report_id)
    db.commit()
    return {"ok": True}


def _report_attachment(db, att_id: str):
    att = db.execute("SELECT * FROM attachments WHERE id=?", (att_id,)).fetchone()
    if att is None or att["report_id"] is None:
        raise HTTPException(404, "Attachment not found")
    return att, svc.get_report_row(db, att["report_id"])


@router.post("/attachments/{att_id}/request-access", status_code=201)
def request_access(att_id: str, body: AccessRequestIn, user=Depends(require_petugas), db=Depends(get_db)):
    att, report = _report_attachment(db, att_id)
    if report["status"] in access.CLOSED:
        raise HTTPException(409, "Report is closed")
    current = access.status_of(db, att_id)
    if current in ("granted", "requested"):
        raise HTTPException(409, "This file is already permitted" if current == "granted" else "Request has already been submitted")
    access.set_grant(db, att, "requested", source="request", requested_by=user["id"], reason=body.reason.strip())
    no = svc.attachment_no(db, att)
    svc.add_event(db, report, user, type_="note",
                  note=f"Requested access to attachment {no} ({att['kind']}). Reason: {body.reason.strip()}")
    audit.log(db, user, "officer.request_access", "attachment", att_id)
    db.commit()
    return {"status": "requested"}


@router.get("/attachments/{att_id}/preview")
def preview(att_id: str, user=Depends(require_petugas), db=Depends(get_db)):
    att, report = _report_attachment(db, att_id)
    ok, why = access.can_officer_view(db, att, report)
    if not ok:
        audit.log(db, user, "officer.view_denied", "attachment", att_id, why)
        db.commit()
        raise HTTPException(403, why)
    if att["mime"] not in INLINE_MIMES | TEXT_EXTRACT_MIMES:
        raise HTTPException(415, "Preview is unavailable for legacy format (.doc/.xls/.ppt). "
                                 "Request the reporter to re-upload in PDF or modern Office format.")
    filename = vault.read_text(db, "attachment", att_id, "filename") or f"attachment-{att_id[:8]}"
    path, ms = vault.decrypt_to_tempfile(db, "attachment", att_id, "content")
    headers = {"Cache-Control": "no-store", "X-Integrity": "verified", "X-Decrypt-Ms": f"{ms:.3f}",
               "Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}",
               "Content-Security-Policy": "sandbox; default-src 'none'"}
    try:
        if att["mime"] in TEXT_EXTRACT_MIMES:
            try:
                text = extract_text(path, att["mime"])
            except PreviewUnavailable as exc:
                raise HTTPException(422, str(exc))
            finally:
                path.unlink(missing_ok=True)
            response = PlainTextResponse(text, headers={**headers, "X-Preview": "text-extract"})
        else:
            response = FileResponse(path, media_type=att["mime"], headers={**headers, "X-Preview": "original"},
                                    background=BackgroundTask(path.unlink, missing_ok=True))
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    audit.log(db, user, access.VIEW_ACTION, "attachment", att_id)
    db.commit()
    return response


@router.get("/stats")
def stats(user=Depends(require_petugas), db=Depends(get_db)):
    by_status = {s: 0 for s in STATUSES}
    for r in db.execute("SELECT status, COUNT(*) n FROM reports GROUP BY status"):
        by_status[r["status"]] = r["n"]
    by_category = [
        {"category": k, "label": v,
         "count": db.execute("SELECT COUNT(*) FROM reports WHERE category=?", (k,)).fetchone()[0]}
        for k, v in CATEGORIES.items()
    ]
    crypto = [dict(r) for r in db.execute(
        """SELECT cipher,
                  COUNT(*) AS files,
                  ROUND(SUM(plain_size) / 1048576.0, 2) AS total_mb,
                  ROUND(SUM(enc_ms), 1) AS total_enc_ms,
                  ROUND((SUM(plain_size) / 1048576.0) / (SUM(enc_ms) / 1000.0), 1) AS mb_per_s,
                  SUM(cipher_size + LENGTH(iv) + LENGTH(tag) + LENGTH(wrapped_key) - plain_size) AS overhead_bytes
           FROM encrypted_items
           WHERE path IS NOT NULL AND enc_ms > 0
           GROUP BY cipher ORDER BY cipher""")]
    return {"total": sum(by_status.values()), "by_status": by_status,
        "by_category": by_category, "encryption": crypto}


@router.get("/audit")
def audit_logs(limit: int = Query(100, ge=1, le=500), user=Depends(require_petugas), db=Depends(get_db)):
    return [dict(r) for r in db.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,))]
