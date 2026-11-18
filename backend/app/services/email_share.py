import hashlib
import hmac
import os
import smtplib
from email.message import EmailMessage

from ..config import get_settings
from ..crypto import asymmetric, keywrap, vault
from ..crypto.suites import IntegrityError
from ..db import new_id, now


def _send_smtp(to_email: str, subject: str, body: str) -> str:
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        return "local_outbox"
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASS", "").strip()
    sender = os.getenv("SMTP_FROM", user or "noreply@safereport.local").strip()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to_email
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.ehlo()
            if port in (587, 25):
                try:
                    smtp.starttls()
                except smtplib.SMTPException:
                    pass
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
        return "smtp"
    except Exception:
        return "local_outbox"


def create_and_email_share_key(db, *, att, recipient_id: str) -> dict:
    sym_key = os.urandom(32)
    key_hash = hashlib.sha256(sym_key).hexdigest()
    aad = vault.context(att["owner_id"], "share_key", att["id"], recipient_id)
    wrapped = keywrap.wrap(get_settings().master_key, sym_key, aad)

    recipient_pub = asymmetric.ensure_user_keypair(db, recipient_id)
    encrypted_key_b64 = asymmetric.encrypt_key_for_recipient(recipient_pub, sym_key)

    recipient_email = vault.read_text(db, "user", recipient_id, "email") or "officer@csirt.local"
    ts = now()
    db.execute(
        """INSERT INTO share_keys (attachment_id, owner_id, recipient_id, key_hash, wrapped_share_key, encrypted_key_b64, created_at)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(attachment_id) DO UPDATE SET
             owner_id=excluded.owner_id,
             recipient_id=excluded.recipient_id,
             key_hash=excluded.key_hash,
             wrapped_share_key=excluded.wrapped_share_key,
             encrypted_key_b64=excluded.encrypted_key_b64,
             created_at=excluded.created_at""",
        (att["id"], att["owner_id"], recipient_id, key_hash, wrapped, encrypted_key_b64, ts),
    )

    subject = f"[Safe Report] Encrypted Share Key for Attachment {att['id'][:8]}"
    body = (
        f"Hello Officer,\n\n"
        f"The reporter has approved your access request for attachment {att['id']}.\n"
        f"Below is the 256-bit symmetric share key encrypted with your RSA-2048 public key (OAEP-SHA256):\n\n"
        f"{encrypted_key_b64}\n\n"
        f"Paste this encrypted key in the Case Detail viewer to verify with your RSA private key and unlock preview.\n"
    )
    mode = _send_smtp(recipient_email, subject, body)
    email_id = new_id()
    db.execute(
        """INSERT INTO email_outbox (id, recipient_id, recipient_email, subject, body, attachment_id, delivery_mode, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (email_id, recipient_id, recipient_email, subject, body, att["id"], mode, ts),
    )
    return {
        "email_id": email_id,
        "recipient_email": recipient_email,
        "delivery_mode": mode,
        "encrypted_key_b64": encrypted_key_b64,
    }


def revoke_share_key(db, attachment_id: str) -> None:
    db.execute("DELETE FROM share_keys WHERE attachment_id=?", (attachment_id,))


def verify_emailed_key(db, *, attachment_id: str, officer_id: str, encrypted_key_b64: str) -> bool:
    row = db.execute("SELECT * FROM share_keys WHERE attachment_id=?", (attachment_id,)).fetchone()
    if row is None:
        raise IntegrityError("No active share key found for this attachment")
    priv_pem = asymmetric.get_user_private_key(db, officer_id)
    sym_key = asymmetric.decrypt_key_with_private(priv_pem, encrypted_key_b64)
    digest = hashlib.sha256(sym_key).hexdigest()
    if not hmac.compare_digest(digest, row["key_hash"]):
        raise IntegrityError("Decrypted symmetric key does not match stored key hash")
    return True
