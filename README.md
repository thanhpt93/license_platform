# NOVA License Management System (Phase 1)

**NOVA License Management** is an independent enterprise administration application used to manage customers, configure products and commercial license plans, issue digitally signed software licenses (`.novalic.json`), manage license lifecycles (renewal, replacement, suspension, revocation), and maintain an immutable administrative audit trail for **NOVA Machine Vision Platform**.

---

## 1. Architecture & Technology Stack

- **Backend (`backend/`)**:
  - **Python 3.11+ & FastAPI**: REST API with OpenAPI documentation (`/docs`).
  - **SQLAlchemy 2.0 & Alembic**: Normalized relational schema supporting **PostgreSQL** in production and **SQLite** for local development/testing.
  - **Cryptography (`cryptography`)**: **Ed25519** digital signatures over **RFC 8785 / JCS canonical UTF-8 JSON payloads**.
  - **Authentication & RBAC (`PyJWT` + `bcrypt`)**: Role-based access control supporting `SUPER_ADMIN`, `LICENSE_ADMIN`, and `AUDITOR` (read-only).
- **Frontend (`frontend/`)**:
  - **React 18 + TypeScript + Vite + Tailwind CSS + Lucide Icons**: Desktop-first enterprise administration UI (`1440×900` and `1280×720` responsive viewports).
- **Artifact Specification (`docs/LICENSE_SPECIFICATION.md`)**:
  - Complete specification of the `NOVA-LICENSE-ENVELOPE-V1` format, payload schema `1.0`, canonical serialization rules, limit semantics (`-1` = unlimited, `0` = disabled/unavailable, `>0` = exact cap), and verification procedure for future integration with the **NOVA License Validator**.

---

## 2. Repository Structure

```text
license_platform/
├── .env.example                        # Sample environment configuration (no real secrets)
├── .gitignore                          # Excludes keys, .env, databases, node_modules, dist
├── README.md                           # Setup, key initialization, and operational guide
├── run_backend.py                      # Launcher script for backend server (port 8080)
├── docs/
│   └── LICENSE_SPECIFICATION.md        # Formal license artifact & verification specification
├── backend/
│   ├── alembic.ini                     # Alembic migration configuration
│   ├── requirements.txt                # Backend Python dependencies
│   ├── alembic/                        # Database migration environment & version scripts
│   │   └── versions/
│   │       └── 0001_initial_schema.py  # Initial normalized database migration
│   ├── app/
│   │   ├── main.py                     # FastAPI application entrypoint
│   │   ├── config.py                   # Externalized environment settings
│   │   ├── database.py                 # SQLAlchemy engine & session management
│   │   ├── models.py                   # ORM models (users, customers, products, license_plans, signing_keys, licenses, license_relationships, audit_logs)
│   │   ├── schemas.py                  # Pydantic v2 request/response validation schemas
│   │   ├── crypto.py                   # Canonical JSON serializer, Ed25519 signer & verifier
│   │   ├── auth.py                     # bcrypt password hashing, JWT tokens, RBAC dependencies
│   │   ├── audit.py                    # Sanitized append-only administrative audit logger
│   │   ├── services/
│   │   │   └── license_service.py      # Transactional issuance, renewal, replacement & status logic
│   │   └── routers/
│   │       ├── auth_router.py          # /api/auth/*
│   │       ├── dashboard_router.py     # /api/dashboard
│   │       ├── customers_router.py     # /api/customers/*
│   │       ├── products_router.py      # /api/products & /api/license-plans
│   │       ├── licenses_router.py      # /api/licenses/*
│   │       └── audit_keys_router.py    # /api/audit-logs & /api/signing-keys/*
│   ├── scripts/
│   │   └── bootstrap_dev.py            # Local development keypair & seed initialization CLI
│   └── tests/
│       └── test_nova_license_backend.py# Automated pytest suite
└── frontend/
    ├── package.json
    ├── vite.config.ts                  # Vite config with /api proxy to backend (127.0.0.1:8080)
    └── src/
        ├── api.ts                      # Typed REST API client
        ├── App.tsx                     # Enterprise navigation shell & authentication gate
        ├── components/
        │   └── StatusBadge.tsx         # Status badges & limit/UTC formatters
        └── views/
            ├── DashboardView.tsx       # Real-time database metrics & quick actions
            ├── CustomersView.tsx       # Customer CRUD, search, filter, deactivation
            ├── ProductsPlansView.tsx   # Product & Commercial License Plan configuration
            ├── LicensesView.tsx        # 3-step issuance wizard, detail page, renew/replace/suspend/revoke, artifact verifier
            ├── AuditLogsView.tsx       # Searchable append-only audit log viewer
            └── SystemSettingsView.tsx  # Ed25519 key rotation & RBAC user management
```

---

## 3. Local Development Setup & Startup Procedure

### Step 1: Install Backend Dependencies
```powershell
cd backend
python -m pip install -r requirements.txt
```

### Step 2: Run Database Migrations (Alembic)
```powershell
cd backend
python -m alembic upgrade head
```

### Step 3: Initialize Development Signing Keys & Bootstrap Data
The backend **never** auto-generates signing keys on startup or falls back to insecure defaults. To initialize a local development Ed25519 key pair (`backend/keys/`), local `backend/.env`, the initial `NOVA-MVP` product, commercial plans, and administrator account, run:

```powershell
cd backend
python scripts/bootstrap_dev.py --admin-password "<CHOOSE_DEV_ADMIN_PASSWORD>"
```
*(If `--admin-password` is omitted, a secure random password is generated and printed once to the terminal).*

### Step 4: Start the Backend API Server (Port 8080)
> **Note:** Port `8080` is used so the License Management Server can run alongside the NOVA Machine Vision Platform (which uses port `8000`) without port conflicts.

```powershell
cd C:\project\license_platform\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```
*(Or from the root directory `C:\project\license_platform`: `python run_backend.py`)*

- API Health Check: `http://127.0.0.1:8080/api/health`
- Interactive OpenAPI Docs: `http://127.0.0.1:8080/docs`

### Step 5: Install & Start the Frontend Administration UI
In a second terminal:
```powershell
cd C:\project\license_platform\frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser and sign in with the administrator credentials configured in Step 3.

---

## 4. Production Deployment & Key Security Guidelines

1. **Database**:
   - Set `NOVA_DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/<dbname>` in your environment.
   - Run `python -m alembic upgrade head` before starting the service.
2. **Ed25519 Private Key Protection**:
   - Generate the production Ed25519 key pair offline or inside a restricted host directory (`chmod 0400` / restricted ACLs).
   - Provide the private key via `NOVA_SIGNING_PRIVATE_KEY_PATH` (or `NOVA_SIGNING_PRIVATE_KEY_PEM` injected from a secret manager) and optional `NOVA_SIGNING_KEY_PASSPHRASE`.
   - Set `NOVA_ACTIVE_KEY_ID` to match the registered `SigningKey.key_id` in the database.
   - **Never** store private keys in database tables, version control, frontend bundles, or client installations.
3. **Key Rotation**:
   - Register the new Ed25519 public key via `POST /api/signing-keys` (or the **System Settings** UI) with `set_active=true`.
   - Previous public keys automatically transition to `RETIRED` status for signing, while remaining active for verifying all previously issued licenses.

---

## 5. Running Automated Tests

```powershell
cd C:\project\license_platform\backend
python -m pytest -v
```
