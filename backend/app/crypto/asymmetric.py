import base64

from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA

from ..db import now
from . import vault
from .suites import IntegrityError


def generate_keypair() -> tuple[str, str]:
    key = RSA.generate(2048)
    return key.publickey().export_key().decode("utf-8"), key.export_key().decode("utf-8")


def encrypt_key_for_recipient(public_pem: str, sym_key: bytes) -> str:
    pub = RSA.import_key(public_pem)
    cipher = PKCS1_OAEP.new(pub, hashAlgo=SHA256)
    return base64.b64encode(cipher.encrypt(sym_key)).decode("ascii")


def decrypt_key_with_private(private_pem: str, encrypted_b64: str) -> bytes:
    priv = RSA.import_key(private_pem)
    cipher = PKCS1_OAEP.new(priv, hashAlgo=SHA256)
    try:
        raw = base64.b64decode(encrypted_b64.strip(), validate=True)
        return cipher.decrypt(raw)
    except Exception as exc:
        raise IntegrityError("Failed to decrypt asymmetric key with recipient private key") from exc


def ensure_user_keypair(db, user_id: str) -> str:
    row = db.execute("SELECT public_key FROM user_keys WHERE user_id=?", (user_id,)).fetchone()
    if row is not None:
        return row["public_key"]
    pub_pem, priv_pem = generate_keypair()
    db.execute(
        "INSERT INTO user_keys (user_id, public_key, created_at) VALUES (?,?,?)",
        (user_id, pub_pem, now()),
    )
    vault.store_text(db, priv_pem, owner_id=user_id, ref_type="user", ref_id=user_id, field="rsa_private_key")
    return pub_pem


def get_user_private_key(db, user_id: str) -> str:
    ensure_user_keypair(db, user_id)
    priv = vault.read_text(db, "user", user_id, "rsa_private_key")
    if not priv:
        raise IntegrityError("Recipient RSA private key not found")
    return priv
