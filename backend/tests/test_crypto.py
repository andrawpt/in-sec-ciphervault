import io
import os

import pytest

from app.crypto.suites import SUITES, IntegrityError

SIZES = [0, 1, 7, 8, 9, 15, 16, 17, 1024 * 1024, 1024 * 1024 + 3, 3 * 1024 * 1024 + 5]
AAD = b"ctx|owner|report|r1|content"


def _encrypt(suite, key, data, aad=AAD, chunk=1024 * 1024 - 1):
    enc = suite.encryptor(key, aad)
    out = io.BytesIO()
    for i in range(0, len(data), chunk):
        out.write(enc.update(data[i:i + chunk]))
    last, tag = enc.finalize()
    out.write(last)
    return enc.iv, tag, out.getvalue()


def _decrypt(suite, key, iv, tag, ct, aad=AAD):
    out = io.BytesIO()
    suite.decrypt_stream(key, aad, iv, tag, io.BytesIO(ct), out)
    return out.getvalue()


@pytest.mark.parametrize("name", list(SUITES))
@pytest.mark.parametrize("size", SIZES)
def test_roundtrip(name, size):
    suite = SUITES[name]
    data = os.urandom(size)
    key = suite.new_key()
    iv, tag, ct = _encrypt(suite, key, data)
    assert _decrypt(suite, key, iv, tag, ct) == data


@pytest.mark.parametrize("name", list(SUITES))
def test_same_plaintext_different_ciphertext(name):
    suite = SUITES[name]
    data = b"A" * 64
    _, _, c1 = _encrypt(suite, suite.new_key(), data)
    _, _, c2 = _encrypt(suite, suite.new_key(), data)
    assert c1 != c2
    if name == "DES-CBC-HMAC":
        assert len({c1[i:i + 8] for i in range(0, 64, 8)}) == 8


@pytest.mark.parametrize("name", list(SUITES))
@pytest.mark.parametrize("target", ["ciphertext", "tag", "iv", "aad", "key"])
def test_tamper_detected(name, target):
    suite = SUITES[name]
    data = os.urandom(5000)
    key = suite.new_key()
    iv, tag, ct = _encrypt(suite, key, data)
    aad = AAD
    if target == "ciphertext":
        ct = bytearray(ct); ct[1234] ^= 0x01; ct = bytes(ct)
    elif target == "tag":
        tag = bytes([tag[0] ^ 1]) + tag[1:]
    elif target == "iv":
        if not iv:
            pytest.skip("RC4 does not use IV")
        iv = bytes([iv[0] ^ 1]) + iv[1:]
    elif target == "aad":
        aad = AAD.replace(b"owner", b"other")
    elif target == "key":
        key = suite.new_key()
    with pytest.raises(IntegrityError):
        _decrypt(suite, key, iv, tag, ct, aad)
