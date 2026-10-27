import hashlib
import hmac
import io
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Iterable

from ..config import get_settings
from ..db import now
from . import keywrap
from .suites import SUITES, IntegrityError

DEFAULT_CIPHER = "AES-256-GCM"
CIPHER_DIRS = {"AES-256-GCM": "aes", "DES-CBC-HMAC": "des", "RC4-HMAC": "rc4"}


def context(owner_id: str, ref_type: str, ref_id: str, field: str) -> bytes:
    return f"lapor-siber/v1|{owner_id}|{ref_type}|{ref_id}|{field}".encode()


def _aad(ctx: bytes, cipher: str) -> bytes:
    return ctx + b"|" + cipher.encode()


class _HmacWriter:
    def __init__(self, dst, ctx: bytes):
        self.dst = dst
        self.mac = hmac.new(get_settings().integrity_key, ctx, hashlib.sha256)
        self.size = 0

    def write(self, data: bytes) -> None:
        self.mac.update(data)
        self.size += len(data)
        self.dst.write(data)


def store_stream(
    db: sqlite3.Connection,
    chunks: Iterable[bytes],
    *,
    owner_id: str,
    ref_type: str,
    ref_id: str,
    field: str,
    to_disk: bool,
) -> int:
    s = get_settings()
    ctx = context(owner_id, ref_type, ref_id, field)
    plain_mac = hmac.new(s.integrity_key, ctx, hashlib.sha256)
    sinks, paths = [], []

    try:
        for name, suite in SUITES.items():
            t0 = time.perf_counter_ns()
            key = suite.new_key()
            enc = suite.encryptor(key, _aad(ctx, name))
            ns = time.perf_counter_ns() - t0
            if to_disk:
                rel = Path(CIPHER_DIRS[name]) / f"{ref_id}_{field}.bin"
                full = s.storage_dir / rel
                full.parent.mkdir(parents=True, exist_ok=True)
                out = open(full, "wb")
                paths.append(full)
            else:
                rel, out = None, io.BytesIO()
            sinks.append({"name": name, "key": key, "enc": enc, "ns": ns, "out": out, "rel": rel, "size": 0})

        plain_size = 0
        for chunk in chunks:
            plain_mac.update(chunk)
            plain_size += len(chunk)
            for sk in sinks:
                t0 = time.perf_counter_ns()
                ct = sk["enc"].update(chunk)
                sk["ns"] += time.perf_counter_ns() - t0
                sk["out"].write(ct)
                sk["size"] += len(ct)

        digest = plain_mac.digest()
        for sk in sinks:
            t0 = time.perf_counter_ns()
            last, tag = sk["enc"].finalize()
            wrapped = keywrap.wrap(s.master_key, sk["key"], _aad(ctx, sk["name"]))
            sk["ns"] += time.perf_counter_ns() - t0
            sk["out"].write(last)
            sk["size"] += len(last)
            blob = None if to_disk else sk["out"].getvalue()
            sk["out"].close()
            db.execute(
                """INSERT INTO encrypted_items
                   (owner_id, ref_type, ref_id, field, cipher, iv, tag, wrapped_key, ciphertext, path,
                    plain_hmac, plain_size, cipher_size, enc_ms, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (owner_id, ref_type, ref_id, field, sk["name"], sk["enc"].iv, tag, wrapped, blob,
                 str(sk["rel"]) if sk["rel"] else None, digest, plain_size, sk["size"],
                 sk["ns"] / 1e6, now()),
            )
        return plain_size
    except BaseException:
        for sk in sinks:
            sk["out"].close()
        for p in paths:
            p.unlink(missing_ok=True)
        raise


def store_text(db, text: str | None, *, owner_id, ref_type, ref_id, field) -> None:
    if text is None or text == "":
        return
    store_stream(db, [text.encode("utf-8")], owner_id=owner_id, ref_type=ref_type,
                 ref_id=ref_id, field=field, to_disk=False)


def _row(db, ref_type, ref_id, field, cipher):
    if cipher not in SUITES:
        raise ValueError(f"Unknown cipher: {cipher}")
    return db.execute(
        "SELECT * FROM encrypted_items WHERE ref_type=? AND ref_id=? AND field=? AND cipher=?",
        (ref_type, ref_id, field, cipher),
    ).fetchone()


def _decrypt_row(row, dst) -> float:
    s = get_settings()
    ctx = context(row["owner_id"], row["ref_type"], row["ref_id"], row["field"])
    aad = _aad(ctx, row["cipher"])
    suite = SUITES[row["cipher"]]
    writer = _HmacWriter(dst, ctx)
    t0 = time.perf_counter_ns()
    key = keywrap.unwrap(s.master_key, row["wrapped_key"], aad)
    if row["path"]:
        with open(s.storage_dir / row["path"], "rb") as src:
            suite.decrypt_stream(key, aad, row["iv"], row["tag"], src, writer)
    else:
        suite.decrypt_stream(key, aad, row["iv"], row["tag"], io.BytesIO(row["ciphertext"]), writer)
    ms = (time.perf_counter_ns() - t0) / 1e6
    if writer.size != row["plain_size"] or not hmac.compare_digest(writer.mac.digest(), row["plain_hmac"]):
        raise IntegrityError("Decrypted plaintext is not identical to original")
    return ms


def read_bytes(db, ref_type, ref_id, field, cipher=DEFAULT_CIPHER) -> bytes | None:
    row = _row(db, ref_type, ref_id, field, cipher)
    if row is None:
        return None
    buf = io.BytesIO()
    _decrypt_row(row, buf)
    return buf.getvalue()


def read_text(db, ref_type, ref_id, field, cipher=DEFAULT_CIPHER) -> str | None:
    data = read_bytes(db, ref_type, ref_id, field, cipher)
    return None if data is None else data.decode("utf-8")


def decrypt_to_tempfile(db, ref_type, ref_id, field, cipher=DEFAULT_CIPHER) -> tuple[Path, float]:
    row = _row(db, ref_type, ref_id, field, cipher)
    if row is None:
        raise FileNotFoundError
    tmp_dir = get_settings().storage_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=tmp_dir, suffix=".part")
    path = Path(name)
    try:
        with os.fdopen(fd, "wb") as out:
            ms = _decrypt_row(row, out)
        return path, ms
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def verify_all(db, ref_type, ref_id, field) -> list[dict]:
    results = []
    for name in SUITES:
        row = _row(db, ref_type, ref_id, field, name)
        if row is None:
            results.append({"cipher": name, "ok": False, "error": "not found"})
            continue
        sink = _NullSink()
        try:
            ms = _decrypt_row(row, sink)
            results.append({"cipher": name, "ok": True, "decrypt_ms": round(ms, 3)})
        except (IntegrityError, OSError) as exc:
            results.append({"cipher": name, "ok": False, "error": str(exc)})
        results[-1].update(
            enc_ms=round(row["enc_ms"], 3),
            plain_size=row["plain_size"],
            cipher_size=row["cipher_size"],
            overhead_bytes=row["cipher_size"] + len(row["iv"]) + len(row["tag"]) + len(row["wrapped_key"]) - row["plain_size"],
        )
    return results


class _NullSink:
    def write(self, data: bytes) -> None:
        pass


def delete_ref(db, ref_type: str, ref_id: str) -> None:
    _delete_rows(db, db.execute(
        "SELECT id, path FROM encrypted_items WHERE ref_type=? AND ref_id=?", (ref_type, ref_id)).fetchall())


def delete_owner(db, owner_id: str) -> None:
    _delete_rows(db, db.execute(
        "SELECT id, path FROM encrypted_items WHERE owner_id=?", (owner_id,)).fetchall())


def _delete_rows(db, rows) -> None:
    storage = get_settings().storage_dir
    for r in rows:
        if r["path"]:
            (storage / r["path"]).unlink(missing_ok=True)
        db.execute("DELETE FROM encrypted_items WHERE id=?", (r["id"],))
