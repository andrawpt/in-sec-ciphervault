from fastapi import HTTPException

from ..crypto import vault
from ..db import new_id, now

STATUS_LABEL = {
    "belum": "ID card not yet uploaded",
    "menunggu": "Pending officer verification",
    "terverifikasi": "Identity verified",
    "ditolak": "Verification rejected, please re-upload ID card",
    "verifikasi_ulang": "Re-verification required",
}
EVENT_LABEL = {
    "diajukan": "ID card submitted for verification",
    "terverifikasi": "Identity verified",
    "ditolak": "Verification rejected",
    "verifikasi_ulang": "Flagged as requiring re-verification",
}
VIEW_ACTION = "officer.view_ktp"


def ktp_attachment(db, user_id: str):
    return db.execute("SELECT * FROM attachments WHERE owner_id=? AND kind='ktp'", (user_id,)).fetchone()


def get_state(db, user_id: str):
    return db.execute("SELECT * FROM ktp_verifications WHERE user_id=?", (user_id,)).fetchone()


def status_of(db, user_id: str) -> str:
    st = get_state(db, user_id)
    if st:
        return st["status"]
    return "menunggu" if ktp_attachment(db, user_id) else "belum"


def _file_hmac(db, att_id: str) -> str | None:
    row = db.execute(
        "SELECT plain_hmac FROM encrypted_items WHERE ref_type='attachment' AND ref_id=? AND field='content' "
        "AND cipher='AES-256-GCM'", (att_id,)).fetchone()
    return row["plain_hmac"].hex() if row else None


def _event(db, user_id, action, actor, att_id=None, note=None) -> None:
    ev = new_id()
    has_note = bool(note and note.strip())
    if has_note:
        vault.store_text(db, note.strip(), owner_id=user_id, ref_type="ktp_event", ref_id=ev, field="note")
    db.execute(
        "INSERT INTO ktp_events (id, user_id, attachment_id, action, actor_id, actor_role, file_hmac, has_note, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (ev, user_id, att_id, action, actor["id"], actor["role"], _file_hmac(db, att_id) if att_id else None,
         int(has_note), now()),
    )


def _set(db, user_id, status, att_id=None, decided_by=None) -> None:
    ts = now()
    db.execute(
        """INSERT INTO ktp_verifications (user_id, status, attachment_id, file_hmac, decided_by, decided_at, updated_at)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET status=excluded.status,
             attachment_id=COALESCE(excluded.attachment_id, ktp_verifications.attachment_id),
             file_hmac=COALESCE(excluded.file_hmac, ktp_verifications.file_hmac),
             decided_by=excluded.decided_by, decided_at=excluded.decided_at, updated_at=excluded.updated_at""",
        (user_id, status, att_id, _file_hmac(db, att_id) if att_id else None,
         decided_by, ts if decided_by else None, ts),
    )


def submitted(db, user, att_id: str) -> None:
    _set(db, user["id"], "menunggu", att_id=att_id)
    _event(db, user["id"], "diajukan", user, att_id)


def decide(db, officer, user_id: str, decision: str, note: str | None) -> None:
    if status_of(db, user_id) != "menunggu":
        raise HTTPException(409, "This ID card is not awaiting verification")
    att = ktp_attachment(db, user_id)
    if att is None:
        raise HTTPException(409, "Reporter has not uploaded an ID card")
    if decision == "ditolak" and not (note and len(note.strip()) >= 5):
        raise HTTPException(422, "Rejection reason is required")
    _set(db, user_id, decision, att_id=att["id"], decided_by=officer["id"])
    _event(db, user_id, decision, officer, att["id"], note)


def flag(db, officer, user_id: str, reason: str) -> None:
    if status_of(db, user_id) != "terverifikasi":
        raise HTTPException(409, "Only verified identities can be flagged as having issues")
    _set(db, user_id, "verifikasi_ulang", decided_by=officer["id"])
    att = ktp_attachment(db, user_id)
    _event(db, user_id, "verifikasi_ulang", officer, att["id"] if att else None, reason)


def require_verified(db, user_id: str) -> None:
    st = status_of(db, user_id)
    if st != "terverifikasi":
        raise HTTPException(403, {
            "belum": "Please upload and verify your ID card before submitting reports.",
            "menunggu": "Your ID card is being verified by officers. Reports can be submitted once verified.",
            "ditolak": "ID verification was rejected. Please re-upload your ID card to be re-verified.",
            "verifikasi_ulang": "Officers requested ID re-verification. Report submission is temporarily disabled.",
        }[st])


def officer_can_view(db, user_id: str) -> bool:
    return status_of(db, user_id) == "menunggu" and ktp_attachment(db, user_id) is not None


def _name(db, uid):
    try:
        return vault.read_text(db, "user", uid, "full_name") or "Officer"
    except Exception:
        return "Officer"


def history(db, user_id: str) -> list[dict]:
    rows = db.execute("SELECT * FROM ktp_events WHERE user_id=? ORDER BY created_at, rowid", (user_id,)).fetchall()
    return [{
        "action": r["action"], "label": EVENT_LABEL[r["action"]],
        "actor_role": r["actor_role"], "actor": _name(db, r["actor_id"]) if r["actor_role"] == "petugas" else "Reporter",
        "note": vault.read_text(db, "ktp_event", r["id"], "note") if r["has_note"] else None,
        "created_at": r["created_at"],
    } for r in rows]


def views(db, user_id: str) -> list[dict]:
    rows = db.execute("SELECT actor_id, created_at FROM audit_logs WHERE action=? AND target_id=? ORDER BY id DESC",
                      (VIEW_ACTION, user_id)).fetchall()
    return [{"officer": _name(db, r["actor_id"]), "at": r["created_at"]} for r in rows]


def summary(db, user_id: str) -> dict:
    st = status_of(db, user_id)
    state = get_state(db, user_id)
    last_note = db.execute(
        "SELECT id FROM ktp_events WHERE user_id=? AND has_note=1 AND action IN ('ditolak','verifikasi_ulang') "
        "ORDER BY created_at DESC, rowid DESC LIMIT 1", (user_id,)).fetchone()
    return {
        "status": st,
        "label": STATUS_LABEL[st],
        "can_create_report": st == "terverifikasi",
        "decided_at": state["decided_at"] if state else None,
        "updated_at": state["updated_at"] if state else None,
        "officer_note": vault.read_text(db, "ktp_event", last_note["id"], "note")
        if last_note and st in ("ditolak", "verifikasi_ulang") else None,
    }
