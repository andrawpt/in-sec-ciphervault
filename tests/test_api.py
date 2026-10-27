import glob
import os
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from conftest import make_officer, verified_pelapor

CIPHERS = ["AES-256-GCM", "DES-CBC-HMAC", "RC4-HMAC"]
PDF = b"%PDF-1.7\n" + os.urandom(300_000)
MP4 = b"\x00\x00\x00\x18ftypmp42" + os.urandom(3 * 1024 * 1024 + 11)
KTP = b"\xff\xd8\xff\xe0" + os.urandom(80_000)


@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


def _officer(client):
    return make_officer(client, "petugas@csirt.local", "Petugas Satu")


def test_full_flow(client):
    officer = _officer(client)
    alice, _ = verified_pelapor(client, officer, "alice@example.com", "3201010101010001")
    bob, _ = verified_pelapor(client, officer, "bob@example.com", "3201010101010002")

    r = client.post("/api/reports", headers=alice, json={
        "category": "perundungan_siber", "title": "Fake banking site",
        "chronology": "I received an SMS link to a fake bank site and logged in.",
        "incident_url": "http://bank-x-login.example", "scammer_account": "BCA 1234567890",
        "consent": True})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    r = client.post(f"/api/reports/{rid}/attachments", headers=alice, data={"kind": "dokumen"},
                    files={"file": ("mutasi.pdf", PDF, "application/pdf")})
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]
    r = client.post(f"/api/reports/{rid}/attachments", headers=alice, data={"kind": "video"},
                    files={"file": ("rekaman.mp4", MP4, "video/mp4")})
    assert r.status_code == 201, r.text
    vid_id = r.json()["id"]

    r = client.post(f"/api/reports/{rid}/attachments", headers=alice, data={"kind": "dokumen"},
                    files={"file": ("bukti.pdf", b"MZ\x90\x00 bukan pdf", "application/pdf")})
    assert r.status_code == 415

    for att, original in ((doc_id, PDF), (vid_id, MP4)):
        for c in CIPHERS:
            r = client.get(f"/api/attachments/{att}/download", params={"cipher": c}, headers=alice)
            assert r.status_code == 200
            assert r.content == original
            assert r.headers["x-integrity"] == "verified"
        v = client.get(f"/api/attachments/{att}/verify", headers=alice).json()
        assert v["all_ok"]
    p = client.get("/api/me/profile", params={"cipher": "RC4-HMAC"}, headers=alice).json()
    assert p["data"]["nik"] == "3201010101010001"

    assert client.get(f"/api/attachments/{doc_id}/download", headers=bob).status_code == 404
    assert client.get(f"/api/reports/{rid}", headers=bob).status_code == 404
    assert client.get(f"/api/attachments/{doc_id}/download", headers=officer).status_code == 404
    assert client.get("/api/me/profile", headers=officer).status_code == 403
    assert client.get("/api/officer/reports", headers=alice).status_code == 403
    assert client.get(f"/api/attachments/{doc_id}/download").status_code == 401

    case = client.get(f"/api/officer/reports/{rid}", headers=officer).json()
    assert case["reporter"]["nik"] == "3201**********01"
    assert case["reporter"]["identity"]["status"] == "terverifikasi"
    assert "filename" not in case["attachments"][0]
    r = client.patch(f"/api/officer/reports/{rid}/status", headers=officer,
                     json={"status": "diverifikasi", "note": "Site reported to registrar."})
    assert r.status_code == 200
    r = client.patch(f"/api/officer/reports/{rid}/status", headers=officer, json={"status": "selesai"})
    assert r.status_code == 409
    detail = client.get(f"/api/reports/{rid}", headers=alice).json()
    assert detail["status"] == "diverifikasi"
    assert any(e["note"] == "Site reported to registrar." for e in detail["events"])

    raw = b"".join(open(p, "rb").read() for p in glob.glob(str(get_settings().db_path) + "*"))
    for secret in (b"3201010101010001", b"alice@example.com", b"Budi Santoso", b"bank-x-login", b"081234567890"):
        assert secret not in raw

    s = get_settings()
    path = s.storage_dir / "aes" / f"{doc_id}_content.bin"
    data = bytearray(path.read_bytes()); data[100] ^= 1; path.write_bytes(bytes(data))
    r = client.get(f"/api/attachments/{doc_id}/download", params={"cipher": "AES-256-GCM"}, headers=alice)
    assert r.status_code == 500 and "integrity" in r.json()["detail"].lower()
    assert client.get(f"/api/attachments/{doc_id}/download", params={"cipher": "DES-CBC-HMAC"},
                      headers=alice).content == PDF

    assert client.request("DELETE", "/api/me", headers=alice, json={"password": "wrong-password"}).status_code == 403
    assert client.request("DELETE", "/api/me", headers=alice, json={"password": "rahasia-123"}).status_code == 204
    con = sqlite3.connect(s.db_path)
    n = con.execute("SELECT COUNT(*) FROM encrypted_items WHERE ref_id IN (?,?)", (doc_id, vid_id)).fetchone()[0]
    assert n == 0
    assert not (s.storage_dir / "des" / f"{vid_id}_content.bin").exists()
