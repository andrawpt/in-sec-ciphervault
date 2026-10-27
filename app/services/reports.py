from fastapi import HTTPException

from ..crypto import vault
from . import kyc
from ..db import new_id, now
from ..validators import CATEGORIES, mask_email, mask_name, mask_nik, mask_phone

REPORT_FIELDS = ("title", "chronology", "incident_url", "scammer_account")
PROFILE_FIELDS = ("email", "full_name", "nik", "phone")


def get_report_row(db, report_id: str, owner_id: str | None = None):
    if owner_id:
        row = db.execute("SELECT * FROM reports WHERE id=? AND owner_id=?", (report_id, owner_id)).fetchone()
    else:
        row = db.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Report not found")
    return row


def report_summary(db, row) -> dict:
    return {
        "id": row["id"],
        "category": row["category"],
        "category_label": CATEGORIES.get(row["category"], row["category"]),
        "status": row["status"],
        "incident_date": row["incident_date"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "title": vault.read_text(db, "report", row["id"], "title"),
        "attachment_count": db.execute(
            "SELECT COUNT(*) FROM attachments WHERE report_id=?", (row["id"],)).fetchone()[0],
    }


def report_fields(db, report_id: str) -> dict:
    return {f: vault.read_text(db, "report", report_id, f) for f in REPORT_FIELDS}


def list_attachments(db, report, viewer: str) -> list[dict]:
    from . import access
    rows = db.execute(
        "SELECT * FROM attachments WHERE report_id=? ORDER BY created_at, rowid", (report["id"],)).fetchall()
    out = []
    for i, r in enumerate(rows, 1):
        info = access.access_info(db, r, report, for_owner=viewer == "owner")
        item = {"id": r["id"], "no": i, "kind": r["kind"], "mime": r["mime"], "size": r["size"],
                "created_at": r["created_at"], "access": info}
        if viewer == "owner" or info["officer_can_view"]:
            item["filename"] = vault.read_text(db, "attachment", r["id"], "filename")
        out.append(item)
    return out


def attachment_no(db, att) -> int:
    ids = [r["id"] for r in db.execute(
        "SELECT id FROM attachments WHERE report_id=? ORDER BY created_at, rowid", (att["report_id"],))]
    return ids.index(att["id"]) + 1


def list_events(db, report_id: str) -> list[dict]:
    rows = db.execute(
        "SELECT * FROM report_events WHERE report_id=? ORDER BY created_at, rowid", (report_id,)).fetchall()
    return [{
        "id": r["id"], "type": r["type"], "actor_role": r["actor_role"],
        "from_status": r["from_status"], "to_status": r["to_status"], "created_at": r["created_at"],
        "note": vault.read_text(db, "event", r["id"], "note") if r["has_note"] else None,
    } for r in rows]


def add_event(db, report, actor: dict, *, type_: str, note: str | None = None,
              from_status: str | None = None, to_status: str | None = None) -> str:
    ev_id = new_id()
    has_note = bool(note and note.strip())
    if has_note:
        vault.store_text(db, note.strip(), owner_id=report["owner_id"], ref_type="event", ref_id=ev_id, field="note")
    db.execute(
        "INSERT INTO report_events (id, report_id, actor_id, actor_role, type, from_status, to_status, has_note, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (ev_id, report["id"], actor["id"], actor["role"], type_, from_status, to_status, int(has_note), now()),
    )
    db.execute("UPDATE reports SET updated_at=? WHERE id=?", (now(), report["id"]))
    return ev_id


def masked_reporter(db, owner_id: str) -> dict:
    p = {f: vault.read_text(db, "user", owner_id, f) for f in PROFILE_FIELDS}
    return {
        "name": mask_name(p["full_name"] or ""),
        "nik": mask_nik(p["nik"] or "") if p["nik"] else None,
        "phone": mask_phone(p["phone"] or "") if p["phone"] else None,
        "email": mask_email(p["email"] or ""),
        "user_id": owner_id,
        "identity": kyc.summary(db, owner_id),
    }
