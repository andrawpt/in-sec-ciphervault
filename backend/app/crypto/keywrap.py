import os

from Crypto.Cipher import AES

from .suites import IntegrityError


def wrap(kek: bytes, dek: bytes, aad: bytes) -> bytes:
    nonce = os.urandom(12)
    c = AES.new(kek, AES.MODE_GCM, nonce=nonce)
    c.update(aad)
    ct, tag = c.encrypt_and_digest(dek)
    return nonce + ct + tag


def unwrap(kek: bytes, blob: bytes, aad: bytes) -> bytes:
    nonce, ct, tag = blob[:12], blob[12:-16], blob[-16:]
    c = AES.new(kek, AES.MODE_GCM, nonce=nonce)
    c.update(aad)
    try:
        return c.decrypt_and_verify(ct, tag)
    except ValueError as exc:
        raise IntegrityError("Wrapped key is invalid for this context") from exc
