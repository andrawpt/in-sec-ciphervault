import time
from typing import Literal

from fastapi import Query

CipherName = Literal["AES-256-GCM", "DES-CBC-HMAC", "RC4-HMAC"]


def cipher_query(cipher: CipherName = Query("AES-256-GCM", description="Ciphertext version to decrypt")) -> str:
    return cipher


class Timer:
    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.ms = round((time.perf_counter() - self.t0) * 1000, 3)
