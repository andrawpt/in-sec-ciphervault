from fastapi import HTTPException

from ..crypto import vault
from ..db import now

CLOSED = ("selesai", "ditolak")
VIEW_ACTION = "officer.view_attachment"


def get_grant(db, att_id: str):
    return db.execute("SELECT * FROM access_grants WHERE attachment_id=?", (att_id,)).fetchone()


def status_of(db, att_id: str) -> str:
    g = get_grant(db, att_id)
    return g["status"] if g else "none"


def set_grant(db, att, status: str, *, source: str, requested_by: str | None = None,
              reason: str | None = None) -> None:
    if att["kind"] == "ktp":
        raise HTTPException(400, "ID card scan cannot be shared with officers")
    ts = now()
    requested = status == "requested"
    db.execute(
        """INSERT INTO access_grants (attachment_id, status, source, requested_by, requested_at, decided_at, updated_at)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(attachment_id) DO UPDATE SET
             status=excluded.status, source=excluded.source,
             requested_by=COALESCE(excluded.requested_by, access_grants.requested_by),
             requested_at=COALESCE(excluded.requested_at, access_grants.requested_at),
             decided_at=excluded.decided_at, updated_at=excluded.updated_at""",
        (att["id"], status, source, requested_by, ts if requested else None,
         None if requested else ts, ts),
    )
    if requested:
        vault.delete_ref(db, "grant", att["id"])
        vault.store_text(db, reason, owner_id=att["owner_id"], ref_type="grant", ref_id=att["id"], field="reason")


def can_officer_view(db, att, report) -> tuple[bool, str]:
    if att["kind"] == "ktp" or report is None:
        return False, "ID card scan cannot be viewed by officers"
    if report["status"] in CLOSED:
        return False, "Report is closed, officer access has expired"
    st = status_of(db, att["id"])
    if st != "granted":
        return False, {"none": "Reporter has not permitted this file",
                       "requested": "Awaiting reporter approval",
                       "denied": "Reporter denied access request",
                       "revoked": "Reporter revoked access"}.get(st, "Not permitted")
    return True, ""


def _officer_name(db, officer_id: str | None) -> str:
    if not officer_id:
        return "Officer"
    try:
        return vault.read_text(db, "user", officer_id, "full_name") or "Officer"
    except Exception:
        return "Officer (account deleted)"


def access_info(db, att, report, *, for_owner: bool) -> dict:
    g = get_grant(db, att["id"])
    ok, why = can_officer_view(db, att, report)
    info = {
        "status": g["status"] if g else "none",
        "source": g["source"] if g else None,
        "officer_can_view": ok,
        "reason_blocked": None if ok else why,
        "requested_at": g["requested_at"] if g else None,
        "requested_by": _officer_name(db, g["requested_by"]) if g and g["requested_by"] else None,
        "request_reason": vault.read_text(db, "grant", att["id"], "reason") if g and g["requested_by"] else None,
    }
    views = db.execute(
        "SELECT actor_id, created_at FROM audit_logs WHERE action=? AND target_id=? ORDER BY id DESC",
        (VIEW_ACTION, att["id"]),
    ).fetchall()
    info["view_count"] = len(views)
    if for_owner:
        info["views"] = [{"officer": _officer_name(db, v["actor_id"]), "at": v["created_at"]} for v in views[:20]]
    return info
