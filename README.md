# Safe Report — Phishing & Cyber Incident Reporting Portal

Portal for a **Campus/Institutional CSIRT (Computer Security Incident Response Team)**. Victims or witnesses of phishing, online fraud, and account takeovers submit incident reports along with supporting evidence. CSIRT officers verify and respond to these reports.

Report evidence almost always contains sensitive victim data: bank statements, photos of identity cards already sent to scammers, chat screen recordings. If breached, this data could be weaponized for secondary fraud. Therefore, all user data is encrypted prior to storage, and only the data owner can retrieve the original files.

- **Frontend:** React + Tailwind CSS (Vite)
- **Backend:** FastAPI + Uvicorn, pycryptodome
- **Database:** SQLite (built-in Python `sqlite3` module)
- Runs locally

---

## Running the Application

Prerequisites: Python 3.11+ and Node.js 20+.

**1. Backend** (first terminal)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python -m scripts.init_env
python -m scripts.create_officer --email officer@csirt.local --name "Officer One"
uvicorn app.main:app --reload --port 8000
```

Interactive API documentation: http://localhost:8000/docs

**2. Frontend** (second terminal)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Register as a reporter via the *Register* page. Officer accounts can only be created via the CLI script above and cannot register via the web UI.

> `.env` contains the MASTER_KEY. If this key is lost, all encrypted data cannot be decrypted.
> Do not commit `.env` (it is ignored in `.gitignore`).

**3. Tests & benchmarks**

```bash
cd backend
python -m pytest -q
python -m benchmark.run_benchmark --pin
python -m benchmark.run_benchmark --quick
```

---

## Project Structure

```
lapor-siber/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application, CORS, integrity error handling
│   │   ├── config.py            # Environment configuration (keys, paths)
│   │   ├── db.py, schema.sql    # SQLite: metadata + encrypted_items table
│   │   ├── security.py          # bcrypt, JWT, email blind index, role checks
│   │   ├── validators.py        # National ID, phone, categories, magic bytes validation, masking
│   │   ├── audit.py             # Data access audit logging
│   │   ├── crypto/
│   │   │   ├── suites.py        # AES-256-GCM, DES-CBC-HMAC, RC4-HMAC (streaming)
│   │   │   ├── keywrap.py       # Envelope encryption using MASTER_KEY
│   │   │   └── vault.py         # Multi-cipher storage, decryption + verification, crypto-shredding
│   │   ├── services/            # Attachments, reports, access grants, preview, KYC verification
│   │   └── routers/
│   │       ├── auth.py          # Register, login, /me
│   │       ├── me.py            # Profile, ID card, data export, account deletion
│   │       ├── reports.py       # Reporter report management
│   │       ├── attachments.py   # Secure downloads, 3-cipher verification, access control
│   │       ├── officer.py       # Queue, case management, status, request access, preview, stats, audit
│   │       └── verifications.py # ID verification by officers
│   ├── scripts/                 # init_env, create_officer
│   ├── benchmark/
│   │   ├── run_benchmark.py     # Evaluation of AES vs DES vs RC4
│   │   └── results/             # summary.md, CSV, JSON, charts
│   └── tests/
└── frontend/
    ├── vite.config.js           # Proxy /api → localhost:8000
    └── src/
        ├── api/client.js        # fetch + token, upload with progress, blob download
        ├── context/             # AuthContext, ThemeContext (Light/Dark/System)
        ├── components/          # Layout, FilePicker, SecureViewer, ThemeToggle, access, ui, etc.
        └── pages/
            ├── Login.jsx, Register.jsx
            ├── pelapor/         # Dashboard, NewReport, ReportDetail, Verification, Profile
            └── petugas/         # Queue, CaseDetail, VerifyQueue, VerifyDetail, Stats, AuditLog
```

---

## Data Classification and Storage Treatment

Based on personal data protection regulations (e.g. GDPR):

| Data | Example | Category | Treatment |
|---|---|---|---|
| Name, National ID, Phone number, Email | Reporter identity | General personal data | Encrypted. Officers only view masked format |
| ID Card scan | Photo, ID number, address, DOB | Sensitive personal data vulnerable to identity theft | Encrypted, only owner can download. Used once for identity verification |
| Incident documents | Account statements, fake invoices, email (.eml) | Specific / financial personal data | Encrypted, only owner can download |
| Video evidence | Chat screen recordings, scammer video call | Biometric / victim voice and face | Encrypted, only owner can download |
| Title, chronology, URL, perpetrator handle | Report contents | May contain victim personal data | Encrypted; read by officers upon reporter consent, every access logged |
| Attachment file name, messages | `bank-statement.pdf` | May contain personal data | Encrypted |
| ID, status, category, timestamp, file size | System metadata | Non-personal data | Plaintext (required for queue management and aggregate metrics) |

---

## Cryptographic Design

Each item is stored **three times**, encrypted with three different ciphers:

| Scheme | Cipher | Mode / Construction | Integrity | Rationale |
|---|---|---|---|---|
| `AES-256-GCM` | AES, 256-bit key | GCM, 96-bit random nonce | 128-bit GCM tag | AEAD: native confidentiality + integrity, hardware accelerated (AES-NI) |
| `DES-CBC-HMAC` | DES, 56-bit key | CBC, random IV, PKCS#7 padding | HMAC-SHA256 (Encrypt-then-MAC) | CBC does not guarantee integrity; augmented with MAC |
| `RC4-HMAC` | RC4, 128-bit key | Stream cipher, drop 3072 keystream bytes | HMAC-SHA256 (Encrypt-then-MAC) | RC4 is malleable and initial keystream is biased |

**ECB is not used**: identical plaintext blocks produce identical ciphertext blocks, leaking data patterns. Tests verify that identical inputs yield distinct ciphertexts.

**Key management (envelope encryption):** Every item × cipher receives a unique random Data Encryption Key (DEK). This DEK is wrapped under the `MASTER_KEY` (Key Encryption Key) using AES-256-GCM and stored adjacent to the ciphertext. Nonce/IV/RC4 keys are never reused. Account deletion is executed via crypto-shredding (deleting the wrapped DEK and ciphertext).

**Context binding:** Owner ID, object type, ref ID, field name, and cipher name are bound as Additional Authenticated Data (AAD) and MAC inputs. Ciphertexts or keys moved across rows or users fail authentication.

**Full integrity verification:** During storage, an HMAC of the original plaintext is computed with `INTEGRITY_KEY`. During retrieval: unwrap key → verify ciphertext tag/HMAC → decrypt → verify plaintext HMAC. If any check fails, decryption aborts without releasing plaintext. The **Check 3 ciphers** tool decrypts all three copies and verifies bitwise equality with the original.

---

## Access Control

| | Reporter (Owner) | Other Reporters | Officers | Unauthenticated |
|---|---|---|---|---|
| Full Profile (Name, ID, Phone, Email) | ✓ | – | Masked | – |
| Report Content (Chronology, Link, Handle) | ✓ | – | ✓ (Audit logged) | – |
| Download Original Files (ID card, docs, video) | ✓ | – | – | – |
| View Evidence (Docs & Video) | ✓ | – | Preview only, **if granted by reporter** | – |
| ID Card Scan | ✓ | – | Preview **only while pending verification** | – |
| Update Case Status | – | – | ✓ | – |

Unauthorized access attempts return 404 to avoid leaking resource existence.

### ID Card Verification

Reporters must pass identity verification **once** before filing reports. This prevents fraudulent submissions and ensures victim identity integrity. Subsequent reports do not require identity re-upload.

- Verification is performed by officers via the *ID Verification* dashboard. While status is `menunggu` (pending), officers can view a watermarked preview of the ID card alongside unmasked registration data for cross-checking. Once a decision is finalized, access is immediately revoked.
- If irregularities arise, officers can request re-verification, which temporarily pauses new report creation until a new ID card is verified.

### Evidence Access Delegation

By default, only the reporter can access their files. Officers obtain viewing access exclusively through **explicit owner delegation**:

1. **During submission**, documents and videos have an *"Allow officers to view this file"* option (enabled by default, can be toggled off). ID card scans cannot be shared this way.
2. **Scope:** Permission applies to **all officers**, valid only while the report is open. Closing the report automatically revokes viewing permissions.
3. **Owner control:** Reporters can grant or revoke officer access at any time from the report details page, with a complete access audit log.
4. **Access requests:** For unshared files, officers can submit an access request with a mandatory reason. Reporters can approve or deny the request.
5. **Secure viewer:** Files are previewed inside the browser without download options, overlaid with a dynamic watermark containing the officer's name, timestamp, and confidentiality notice. Modern Office documents are converted to plain text on the server so raw files are never exposed.
