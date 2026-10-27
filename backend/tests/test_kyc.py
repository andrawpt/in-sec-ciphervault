import os

import pytest
from fastapi.testclient import TestClient

from conftest import login, make_officer

KTP1 = b"\xff\xd8\xff\xe0" + os.urandom(40_000)
KTP2 = b"\x89PNG\r\n\x1a\n" + os.urandom(40_000)
REPORT = {"category": "pelecehan_seksual", "title": "Fake email from bank",
          "chronology": "I received an email requesting me to re-login to internet banking.", "consent": True}


@pytest.fixture(scope="module")
def ctx():
    from app.main import app
    with TestClient(app) as c:
        officer = make_officer(c, "verif@csirt.local", "Vera Verifikator")
        c.post("/api/auth/register", json={"email": "eka@example.com", "password": "rahasia-123",
                                           "full_name": "Eka Putri", "nik": "3301010101010001",
                                           "phone": "081377788899", "consent": True})
        owner = login(c, "eka@example.com", "rahasia-123")
        uid = c.get("/api/auth/me", headers=owner).json()["id"]
        yield c, officer, owner, uid


def _status(c, owner):
    return c.get("/api/me/ktp", headers=owner).json()["verification"]["status"]


def test_flow(ctx):
    c, officer, owner, uid = ctx
    base = f"/api/officer/verifications/{uid}"

    assert _status(c, owner) == "belum"
    r = c.post("/api/reports", headers=owner, json=REPORT)
    assert r.status_code == 403 and "ID" in r.json()["detail"]
    assert c.get(f"{base}/ktp", headers=officer).status_code == 403

    c.post("/api/me/ktp", headers=owner, files={"file": ("ktp.jpg", KTP1, "image/jpeg")})
    assert _status(c, owner) == "menunggu"
    assert c.post("/api/reports", headers=owner, json=REPORT).status_code == 403
    queue = c.get("/api/officer/verifications?status=menunggu", headers=officer).json()
    assert [q["user_id"] for q in queue] == [uid]
    d = c.get(base, headers=officer).json()
    assert d["can_view_ktp"] and d["registered"] == {"full_name": "Eka Putri", "nik": "3301010101010001"}
    r = c.get(f"{base}/ktp", headers=officer)
    assert r.status_code == 200 and r.content == KTP1 and r.headers["content-disposition"].startswith("inline")

    assert c.post(f"{base}/decision", headers=officer, json={"decision": "ditolak"}).status_code == 422
    c.post(f"{base}/decision", headers=officer, json={"decision": "ditolak", "note": "ID photo is blurry, ID number illegible"})
    info = c.get("/api/me/ktp", headers=owner).json()
    assert info["verification"]["status"] == "ditolak"
    assert info["verification"]["officer_note"] == "ID photo is blurry, ID number illegible"
    assert c.get(f"{base}/ktp", headers=officer).status_code == 403

    c.post("/api/me/ktp", headers=owner, files={"file": ("ktp.png", KTP2, "image/png")})
    assert c.get(f"{base}/ktp", headers=officer).content == KTP2
    assert c.post(f"{base}/decision", headers=officer, json={"decision": "terverifikasi"}).status_code == 200
    assert c.get(f"{base}/ktp", headers=officer).status_code == 403
    d = c.get(base, headers=officer).json()
    assert not d["can_view_ktp"] and "registered" not in d
    assert c.post(f"{base}/decision", headers=officer, json={"decision": "terverifikasi"}).status_code == 409
    assert c.post("/api/reports", headers=owner, json=REPORT).status_code == 201

    assert c.post(f"{base}/flag", headers=officer, json={"reason": "short"}).status_code == 422
    r = c.post(f"{base}/flag", headers=officer, json={"reason": "Name on ID card differs from bank account holder in evidence"})
    assert r.status_code == 200 and r.json()["status"] == "verifikasi_ulang"
    r = c.post("/api/reports", headers=owner, json=REPORT)
    assert r.status_code == 403 and "re-verification" in r.json()["detail"].lower()
    assert c.get(f"{base}/ktp", headers=officer).status_code == 403
    info = c.get("/api/me/ktp", headers=owner).json()
    assert "Name on ID card differs" in info["verification"]["officer_note"]

    c.post("/api/me/ktp", headers=owner, files={"file": ("ktp-baru.jpg", KTP1, "image/jpeg")})
    assert _status(c, owner) == "menunggu"
    assert c.get(f"{base}/ktp", headers=officer).status_code == 200
    c.post(f"{base}/decision", headers=officer, json={"decision": "terverifikasi"})
    assert c.post("/api/reports", headers=owner, json=REPORT).status_code == 201

    info = c.get("/api/me/ktp", headers=owner).json()
    assert [h["action"] for h in info["history"]] == [
        "diajukan", "ditolak", "diajukan", "terverifikasi", "verifikasi_ulang", "diajukan", "terverifikasi"]
    assert len(info["views"]) == 3 and info["views"][0]["officer"] == "Vera Verifikator"
    assert c.get(f"/api/attachments/{info['id']}/download", headers=owner).content == KTP1


def test_only_officer_and_only_pelapor_targets(ctx):
    c, officer, owner, uid = ctx
    assert c.get("/api/officer/verifications", headers=owner).status_code == 403
    assert c.post(f"/api/officer/verifications/{uid}/flag", headers=owner,
                  json={"reason": "attempting to flag self"}).status_code == 403
    officer_id = c.get("/api/auth/me", headers=officer).json()["id"]
    assert c.get(f"/api/officer/verifications/{officer_id}", headers=officer).status_code == 404
