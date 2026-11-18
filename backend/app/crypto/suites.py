import hashlib
import hmac
import os
from typing import BinaryIO, Iterator

from Crypto.Cipher import ARC4, DES
from Crypto.Util.Padding import pad, unpad
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

CHUNK_SIZE = 1024 * 1024


class IntegrityError(Exception):
    pass


def read_chunks(src: BinaryIO) -> Iterator[bytes]:
    while chunk := src.read(CHUNK_SIZE):
        yield chunk


class _GCMEncryptor:
    def __init__(self, key: bytes, aad: bytes):
        self.iv = os.urandom(12)
        self._c = Cipher(algorithms.AES(key), modes.GCM(self.iv)).encryptor()
        self._c.authenticate_additional_data(aad)

    def update(self, data: bytes) -> bytes:
        return self._c.update(data)

    def finalize(self) -> tuple[bytes, bytes]:
        return self._c.finalize(), self._c.tag


class AESGCMSuite:
    name = "AES-256-GCM"
    key_len = 32

    def new_key(self) -> bytes:
        return os.urandom(self.key_len)

    def encryptor(self, key: bytes, aad: bytes) -> _GCMEncryptor:
        return _GCMEncryptor(key, aad)

    def decrypt_stream(self, key, aad, iv, tag, src: BinaryIO, dst) -> None:
        c = Cipher(algorithms.AES(key), modes.GCM(iv, tag)).decryptor()
        c.authenticate_additional_data(aad)
        for chunk in read_chunks(src):
            dst.write(c.update(chunk))
        try:
            dst.write(c.finalize())
        except InvalidTag as exc:
            raise IntegrityError("AES-GCM tag mismatch") from exc


def _new_mac(mac_key: bytes, aad: bytes, iv: bytes):
    m = hmac.new(mac_key, digestmod=hashlib.sha256)
    m.update(len(aad).to_bytes(8, "big") + aad + iv)
    return m


class _EtMSuite:
    enc_key_len = 0
    mac_key_len = 32

    @property
    def key_len(self) -> int:
        return self.enc_key_len + self.mac_key_len

    def new_key(self) -> bytes:
        return os.urandom(self.key_len)

    def _split(self, key: bytes) -> tuple[bytes, bytes]:
        return key[: self.enc_key_len], key[self.enc_key_len :]

    def _verify_mac(self, mac_key, aad, iv, tag, src: BinaryIO) -> None:
        m = _new_mac(mac_key, aad, iv)
        for chunk in read_chunks(src):
            m.update(chunk)
        if not hmac.compare_digest(m.digest(), tag):
            raise IntegrityError(f"{self.name} HMAC mismatch")
        src.seek(0)


class _CBCEncryptor:
    def __init__(self, cipher, mac, iv: bytes, block: int):
        self.iv = iv
        self._c, self._mac, self._bs = cipher, mac, block
        self._buf = b""

    def update(self, data: bytes) -> bytes:
        if not self._buf and len(data) % self._bs == 0:
            buf, self._buf = data, b""
        else:
            buf = self._buf + data
            cut = len(buf) - len(buf) % self._bs
            buf, self._buf = buf[:cut], buf[cut:]
        out = self._c.encrypt(buf) if buf else b""
        self._mac.update(out)
        return out

    def finalize(self) -> tuple[bytes, bytes]:
        out = self._c.encrypt(pad(self._buf, self._bs))
        self._mac.update(out)
        return out, self._mac.digest()


class DESCBCHMACSuite(_EtMSuite):
    name = "DES-CBC-HMAC"
    enc_key_len = 8
    block = 8

    def encryptor(self, key: bytes, aad: bytes) -> _CBCEncryptor:
        ek, mk = self._split(key)
        iv = os.urandom(self.block)
        return _CBCEncryptor(DES.new(ek, DES.MODE_CBC, iv=iv), _new_mac(mk, aad, iv), iv, self.block)

    def decrypt_stream(self, key, aad, iv, tag, src: BinaryIO, dst) -> None:
        ek, mk = self._split(key)
        self._verify_mac(mk, aad, iv, tag, src)
        c = DES.new(ek, DES.MODE_CBC, iv=iv)
        held = b""
        for chunk in read_chunks(src):
            if len(chunk) % self.block:
                raise IntegrityError("Invalid DES ciphertext length")
            pt = held + c.decrypt(chunk)
            dst.write(pt[: -self.block])
            held = pt[-self.block :]
        if not held:
            raise IntegrityError("Empty DES ciphertext")
        try:
            dst.write(unpad(held, self.block))
        except ValueError as exc:
            raise IntegrityError("Invalid DES padding") from exc


class _StreamEncryptor:
    def __init__(self, cipher, mac):
        self.iv = b""
        self._c, self._mac = cipher, mac

    def update(self, data: bytes) -> bytes:
        out = self._c.encrypt(data)
        self._mac.update(out)
        return out

    def finalize(self) -> tuple[bytes, bytes]:
        return b"", self._mac.digest()


class RC4HMACSuite(_EtMSuite):
    name = "RC4-HMAC"
    enc_key_len = 16
    DROP = 3072

    def encryptor(self, key: bytes, aad: bytes) -> _StreamEncryptor:
        ek, mk = self._split(key)
        return _StreamEncryptor(ARC4.new(ek, drop=self.DROP), _new_mac(mk, aad, b""))

    def decrypt_stream(self, key, aad, iv, tag, src: BinaryIO, dst) -> None:
        ek, mk = self._split(key)
        self._verify_mac(mk, aad, b"", tag, src)
        c = ARC4.new(ek, drop=self.DROP)
        for chunk in read_chunks(src):
            dst.write(c.decrypt(chunk))


SUITES = {s.name: s for s in (AESGCMSuite(), DESCBCHMACSuite(), RC4HMACSuite())}
