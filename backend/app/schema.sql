CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email_bidx    TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('pelapor', 'petugas')),
    consent_at    TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id            TEXT PRIMARY KEY,
    owner_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category      TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'diterima',
    incident_date TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_owner  ON reports(owner_id);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);

CREATE TABLE IF NOT EXISTS attachments (
    id         TEXT PRIMARY KEY,
    owner_id   TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    report_id  TEXT REFERENCES reports(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL CHECK (kind IN ('ktp', 'dokumen', 'video')),
    mime       TEXT NOT NULL,
    size       INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attachments_report ON attachments(report_id);

CREATE TABLE IF NOT EXISTS report_events (
    id          TEXT PRIMARY KEY,
    report_id   TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    actor_id    TEXT,
    actor_role  TEXT NOT NULL,
    type        TEXT NOT NULL CHECK (type IN ('status', 'note')),
    from_status TEXT,
    to_status   TEXT,
    has_note    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_report ON report_events(report_id);

CREATE TABLE IF NOT EXISTS encrypted_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    TEXT NOT NULL,
    ref_type    TEXT NOT NULL,
    ref_id      TEXT NOT NULL,
    field       TEXT NOT NULL,
    cipher      TEXT NOT NULL,
    iv          BLOB NOT NULL,
    tag         BLOB NOT NULL,
    wrapped_key BLOB NOT NULL,
    ciphertext  BLOB,
    path        TEXT,
    plain_hmac  BLOB NOT NULL,
    plain_size  INTEGER NOT NULL,
    cipher_size INTEGER NOT NULL,
    enc_ms      REAL NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE (ref_type, ref_id, field, cipher)
);
CREATE INDEX IF NOT EXISTS idx_items_owner ON encrypted_items(owner_id);

CREATE TABLE IF NOT EXISTS access_grants (
    attachment_id TEXT PRIMARY KEY REFERENCES attachments(id) ON DELETE CASCADE,
    status        TEXT NOT NULL CHECK (status IN ('granted', 'requested', 'denied', 'revoked')),
    source        TEXT NOT NULL CHECK (source IN ('submission', 'owner', 'request')),
    requested_by  TEXT,
    requested_at  TEXT,
    decided_at    TEXT,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ktp_verifications (
    user_id       TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    status        TEXT NOT NULL CHECK (status IN ('menunggu', 'terverifikasi', 'ditolak', 'verifikasi_ulang')),
    attachment_id TEXT,
    file_hmac     TEXT,
    decided_by    TEXT,
    decided_at    TEXT,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ktp_events (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    attachment_id TEXT,
    action        TEXT NOT NULL CHECK (action IN ('diajukan', 'terverifikasi', 'ditolak', 'verifikasi_ulang')),
    actor_id      TEXT,
    actor_role    TEXT NOT NULL,
    file_hmac     TEXT,
    has_note      INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ktp_events_user ON ktp_events(user_id);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id    TEXT,
    actor_role  TEXT,
    action      TEXT NOT NULL,
    target_type TEXT,
    target_id   TEXT,
    detail      TEXT,
    created_at  TEXT NOT NULL
);
