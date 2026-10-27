from pathlib import Path

from fastapi import HTTPException, UploadFile

from ..config import get_settings
from ..crypto import vault
from ..crypto.suites import CHUNK_SIZE
from ..db import new_id, now
from ..validators import KIND_RULES, content_matches_extension
from . import access

MB = 1024 * 1024


def save_upload(db, upload: UploadFile, *, owner_id: str, kind: str, report_id: str | None,
                share: bool = False) -> dict:
    rules = KIND_RULES[kind]
    filename = Path(upload.filename or "").name[:200]
    ext = Path(filename).suffix.lower()
    if ext not in rules["exts"]:
        allowed = ", ".join(sorted(rules["exts"]))
        raise HTTPException(415, f"Format {ext or '(without extension)'} is not supported for {kind}. Use: {allowed}")

    max_bytes = min(rules["max_mb"], get_settings().max_upload_mb) * MB
    first = upload.file.read(CHUNK_SIZE)
    if not first:
        raise HTTPException(400, "File is empty")
    if not content_matches_extension(ext, first):
        raise HTTPException(415, "File content does not match its extension")

    def chunks():
        total, chunk = 0, first
        while chunk:
            total += len(chunk)
            if total > max_bytes:
                raise HTTPException(413, f"Maximum size for {kind} is {max_bytes // MB} MB")
            yield chunk
            chunk = upload.file.read(CHUNK_SIZE)

    att_id = new_id()
    size = vault.store_stream(db, chunks(), owner_id=owner_id, ref_type="attachment",
                              ref_id=att_id, field="content", to_disk=True)
    vault.store_text(db, filename, owner_id=owner_id, ref_type="attachment", ref_id=att_id, field="filename")
    mime = rules["exts"][ext]
    created = now()
    db.execute(
        "INSERT INTO attachments (id, owner_id, report_id, kind, mime, size, created_at) VALUES (?,?,?,?,?,?,?)",
        (att_id, owner_id, report_id, kind, mime, size, created),
    )
    if share and kind != "ktp":
        access.set_grant(db, {"id": att_id, "kind": kind, "owner_id": owner_id}, "granted", source="submission")
    return {"id": att_id, "kind": kind, "mime": mime, "size": size, "filename": filename, "created_at": created,
            "shared": bool(share and kind != "ktp")}


def delete_attachment(db, att_id: str) -> None:
    vault.delete_ref(db, "attachment", att_id)
    vault.delete_ref(db, "grant", att_id)
    db.execute("DELETE FROM attachments WHERE id=?", (att_id,))
