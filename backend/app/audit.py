from .db import now


def log(db, user: dict | None, action: str, target_type: str | None = None,
        target_id: str | None = None, detail: str | None = None) -> None:
    db.execute(
        "INSERT INTO audit_logs (actor_id, actor_role, action, target_type, target_id, detail, created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (user["id"] if user else None, user["role"] if user else None, action,
         target_type, target_id, detail, now()),
    )
