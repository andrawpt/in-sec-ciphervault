import io
import os
import zipfile

import pytest
from fastapi.testclient import TestClient

from conftest import make_officer, verified_pelapor, login as _login

PDF = b"%PDF-1.7\n" + os.urandom(50_000)
MP4 = b"\x00\x00\x00\x18ftypmp42" + os.urandom(200_000)
KTP = b"\xff\xd8\xff\xe0" + os.urandom(20_000)


def _docx(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml",
                   '<w:document><w:body><w:p><w:r><w:t>Account mutation</w:t></w:r></w:p>'
                   f'<w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>')
    return buf.getvalue()


@pytest.fixture(scope="module")
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def setup(client):
    o1 = make_officer(client, "andi@csirt.local", "Andi Petugas")
    o2 = make_officer(client, "sari@csirt.local", "Sari Petugas")
    owner, _ = verified_pelapor(client, o1, "citra@example.com", "3201010101010009", name="Citra Lestari")
    rid = client.post("/api/reports", headers=owner, json={
        "category": "perundungan", "title": "Phone buying scam",
        "chronology": "I transferred money but the items were never shipped by seller.",
        "consent": True}).json()["id"]

    def up(name, data, mime, kind, share):
        r = client.post(f"/api/reports/{rid}/attachments", headers=owner,
                        data={"kind": kind, "share": "true" if share else "false"},
                        files={"file": (name, data, mime)})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    ids = {
        "pdf_shared": up("evidence.pdf", PDF, "application/pdf", "dokumen", True),
        "video_private": up("recording.mp4", MP4, "video/mp4", "video", False),
        "docx_shared": up("chat.docx", _docx("Transfer $2,500 to seller"),
                          "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "dokumen", True),
    }
    return {"owner": owner, "rid": rid, "ids": ids, "o1": o1, "o2": o2}


def test_shared_at_upload_visible_to_all_officers(client, setup):
    ids = setup["ids"]
    for officer in (setup["o1"], setup["o2"]):
        r = client.get(f"/api/officer/attachments/{ids['pdf_shared']}/preview", headers=officer)
        assert r.status_code == 200 and r.content == PDF
        assert r.headers["content-disposition"].startswith("inline")
    r = client.get(f"/api/officer/attachments/{ids['docx_shared']}/preview", headers=setup["o1"])
    assert r.status_code == 200 and r.headers["x-preview"] == "text-extract"
    assert "Transfer $2,500" in r.text
    assert client.get(f"/api/attachments/{ids['pdf_shared']}/download", headers=setup["o1"]).status_code == 404


def test_case_detail_shows_filename_only_when_allowed(client, setup):
    case = client.get(f"/api/officer/reports/{setup['rid']}", headers=setup["o1"]).json()
    by_id = {a["id"]: a for a in case["attachments"]}
    assert by_id[setup["ids"]["pdf_shared"]]["filename"] == "evidence.pdf"
    assert "filename" not in by_id[setup["ids"]["video_private"]]
    assert by_id[setup["ids"]["video_private"]]["access"]["status"] == "none"
    assert len(case["attachments"]) == 3


def test_request_approve_revoke_flow(client, setup):
    vid, owner, o1, o2 = setup["ids"]["video_private"], setup["owner"], setup["o1"], setup["o2"]
    assert client.get(f"/api/officer/attachments/{vid}/preview", headers=o1).status_code == 403

    assert client.post(f"/api/officer/attachments/{vid}/request-access", headers=o1,
                       json={"reason": "short"}).status_code == 422
    r = client.post(f"/api/officer/attachments/{vid}/request-access", headers=o1,
                    json={"reason": "Need to verify seller account in video"})
    assert r.status_code == 201
    assert client.post(f"/api/officer/attachments/{vid}/request-access", headers=o2,
                       json={"reason": "Duplicate request from another officer"}).status_code == 409

    detail = client.get(f"/api/reports/{setup['rid']}", headers=owner).json()
    a = next(x for x in detail["attachments"] if x["id"] == vid)
    assert a["access"]["status"] == "requested"
    assert a["access"]["requested_by"] == "Andi Petugas"
    assert "seller account" in a["access"]["request_reason"]

    assert client.put(f"/api/attachments/{vid}/access", headers=owner, json={"action": "grant"}).status_code == 200
    assert client.get(f"/api/officer/attachments/{vid}/preview", headers=o2).content == MP4

    detail = client.get(f"/api/reports/{setup['rid']}", headers=owner).json()
    a = next(x for x in detail["attachments"] if x["id"] == vid)
    assert a["access"]["view_count"] == 1 and a["access"]["views"][0]["officer"] == "Sari Petugas"

    assert client.put(f"/api/attachments/{vid}/access", headers=owner, json={"action": "revoke"}).status_code == 200
    r = client.get(f"/api/officer/attachments/{vid}/preview", headers=o1)
    assert r.status_code == 403 and "revoked" in r.json()["detail"].lower()


def test_deny(client, setup):
    pdf, owner, o1 = setup["ids"]["pdf_shared"], setup["owner"], setup["o1"]
    assert client.put(f"/api/attachments/{pdf}/access", headers=owner, json={"action": "deny"}).status_code == 409
    client.put(f"/api/attachments/{pdf}/access", headers=owner, json={"action": "revoke"})
    client.post(f"/api/officer/attachments/{pdf}/request-access", headers=o1, json={"reason": "Verify transfer proof"})
    assert client.put(f"/api/attachments/{pdf}/access", headers=owner, json={"action": "deny"}).status_code == 200
    assert client.get(f"/api/officer/attachments/{pdf}/preview", headers=o1).json()["detail"].startswith("Reporter denied")
    client.put(f"/api/attachments/{pdf}/access", headers=owner, json={"action": "grant"})


def test_ktp_never_shared_and_others_cannot_change(client, setup):
    owner = setup["owner"]
    ktp_id = client.get("/api/me/ktp", headers=owner).json()["id"]
    assert client.put(f"/api/attachments/{ktp_id}/access", headers=owner, json={"action": "grant"}).status_code == 400
    assert client.get(f"/api/officer/attachments/{ktp_id}/preview", headers=setup["o1"]).status_code == 404
    assert client.post(f"/api/officer/attachments/{ktp_id}/request-access", headers=setup["o1"],
                       json={"reason": "Want to view reporter identity"}).status_code == 404
    client.post("/api/auth/register", json={
        "email": "dodi@example.com", "password": "rahasia-123", "full_name": "Dodi",
        "nik": "3201010101010010", "phone": "081211112222", "consent": True})
    other = _login(client, "dodi@example.com", "rahasia-123")
    vid = setup["ids"]["video_private"]
    assert client.put(f"/api/attachments/{vid}/access", headers=other, json={"action": "grant"}).status_code == 404
    assert client.put(f"/api/attachments/{vid}/access", headers=setup["o1"], json={"action": "grant"}).status_code == 403


def test_access_ends_when_report_closed(client, setup):
    pdf, o1 = setup["ids"]["pdf_shared"], setup["o1"]
    assert client.get(f"/api/officer/attachments/{pdf}/preview", headers=o1).status_code == 200
    client.patch(f"/api/officer/reports/{setup['rid']}/status", headers=o1, json={"status": "ditolak"})
    r = client.get(f"/api/officer/attachments/{pdf}/preview", headers=o1)
    assert r.status_code == 403 and "closed" in r.json()["detail"].lower()
    assert client.get(f"/api/attachments/{pdf}/download", headers=setup["owner"]).content == PDF
