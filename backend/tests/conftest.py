import base64
import os
import subprocess
import sys

import pytest


@pytest.fixture(scope="session", autouse=True)
def _env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("lapor")
    for k in ("MASTER_KEY", "INTEGRITY_KEY", "BLIND_INDEX_KEY"):
        os.environ[k] = base64.b64encode(os.urandom(32)).decode()
    os.environ["JWT_SECRET"] = "x" * 48
    os.environ["DB_PATH"] = str(tmp / "test.db")
    os.environ["STORAGE_DIR"] = str(tmp / "storage")
    from app.config import get_settings
    get_settings.cache_clear()
    yield


def login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def make_officer(client, email, name, password="petugas-123"):
    subprocess.run([sys.executable, "-m", "scripts.create_officer", "--email", email, "--name", name,
                    "--password", password], check=True, env=dict(os.environ))
    return login(client, email, password)


KTP_JPG = b"\xff\xd8\xff\xe0" + os.urandom(30_000)


def verified_pelapor(client, officer, email, nik, phone="081234567890", name="Budi Santoso"):
    r = client.post("/api/auth/register", json={"email": email, "password": "rahasia-123", "full_name": name,
                                                "nik": nik, "phone": phone, "consent": True})
    assert r.status_code == 201, r.text
    h = login(client, email, "rahasia-123")
    assert client.post("/api/me/ktp", headers=h, files={"file": ("ktp.jpg", KTP_JPG, "image/jpeg")}).status_code == 201
    uid = client.get("/api/auth/me", headers=h).json()["id"]
    r = client.post(f"/api/officer/verifications/{uid}/decision", headers=officer, json={"decision": "terverifikasi"})
    assert r.status_code == 200, r.text
    return h, uid
