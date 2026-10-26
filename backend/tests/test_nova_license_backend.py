"""
Automated Test Suite for NOVA License Management Backend.
Covers:
- Cryptographic canonical serialization, signing, verification, tamper detection, unknown key ID, unsupported algorithm, and key rotation.
- Authentication & RBAC authorization (Unauthenticated, Read-only Auditor, Super Admin).
- Customer management CRUD, duplicate customer code rejection, inactive customer handling, and deletion protection when licenses exist.
- Product & License Plan management, limit validation, and immutability of issued license snapshots when a plan is modified.
- License issuance (Subscription & Perpetual), missing key handling, signature verification failure handling, and database rollback safety.
- License status workflows (Renewal, Replacement, Suspension, Revocation) and audit trail verification without secret leakage.
"""
import base64
import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.config import settings
from app.crypto import (
    SignatureVerificationError,
    canonicalize_payload,
    compute_public_key_fingerprint,
    generate_ed25519_keypair_pem,
    sign_license_payload,
    verify_license_envelope,
)
from app.database import Base, get_db
from app.main import app
from app.models import Product, SigningKey, User


# --- Test Fixtures ---

@pytest.fixture()
def test_db_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

    # Generate test Ed25519 keypair 1
    priv_pem_1, pub_pem_1 = generate_ed25519_keypair_pem()
    key_file_1 = tmp_path / "test_key_1.pem"
    key_file_1.write_text(priv_pem_1, encoding="utf-8")

    monkeypatch.setattr(settings, "NOVA_ACTIVE_KEY_ID", "test-key-2026-01")
    monkeypatch.setattr(settings, "NOVA_SIGNING_PRIVATE_KEY_PATH", str(key_file_1))
    monkeypatch.setattr(settings, "NOVA_SIGNING_PRIVATE_KEY_PEM", None)

    db = TestingSessionLocal()

    # Seed Admin and Auditor users
    admin = User(
        username="test_admin",
        email="admin@nova-vision.com",
        full_name="Test Super Admin",
        password_hash=hash_password("StrongAdminPass!2026"),
        role="SUPER_ADMIN",
        is_active=True,
    )
    auditor = User(
        username="test_auditor",
        email="auditor@nova-vision.com",
        full_name="Test ReadOnly Auditor",
        password_hash=hash_password("StrongAuditorPass!2026"),
        role="AUDITOR",
        is_active=True,
    )
    db.add_all([admin, auditor])

    # Register active public key
    sk = SigningKey(
        key_id="test-key-2026-01",
        algorithm="Ed25519",
        public_key_pem=pub_pem_1,
        fingerprint_sha256=compute_public_key_fingerprint(pub_pem_1),
        is_active=True,
        status="ACTIVE",
        description="Primary test key",
    )
    db.add(sk)

    # Seed NOVA-MVP Product
    product = Product(
        product_code="NOVA-MVP",
        product_name="NOVA Machine Vision Platform",
        description="Test Product",
        supported_editions=["developer", "production"],
        status="ACTIVE",
    )
    db.add(product)
    db.commit()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield db, tmp_path, monkeypatch
    db.close()
    app.dependency_overrides.clear()


@pytest.fixture()
def client(test_db_session):
    return TestClient(app)


def get_auth_headers(client: TestClient, username: str, password: str) -> dict:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# =====================================================================
# 1. CRYPTOGRAPHY & CANONICAL SERIALIZATION TESTS
# =====================================================================

def test_canonical_serialization_determinism():
    payload_a = {
        "schema_version": "1.0",
        "license_id": "11111111-2222-3333-4444-555555555555",
        "license_number": "NOVA-2026-000001",
        "customer_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "customer_code": "CUST-01",
        "customer_name": "Precision Vision Co.",
        "product_id": "NOVA-MVP",
        "edition": "production",
        "license_type": "PERPETUAL",
        "issued_at": "2026-10-25T15:00:00Z",
        "not_before": "2026-10-25T15:00:00Z",
        "expires_at": None,
        "features": ["zebra_inspection", "alpha_ocr", "alpha_ocr"],
        "limits": {
            "total_inspection_quota": -1,
            "max_devices": 2,
            "max_concurrent_inspections": 4,
        },
        "key_id": "test-key-01",
    }
    payload_b = {
        "key_id": "test-key-01",
        "limits": {
            "max_concurrent_inspections": 4,
            "max_devices": 2,
            "total_inspection_quota": -1,
        },
        "features": ["alpha_ocr", "zebra_inspection"],
        "expires_at": None,
        "not_before": "2026-10-25T15:00:00Z",
        "issued_at": "2026-10-25T15:00:00Z",
        "license_type": "PERPETUAL",
        "edition": "production",
        "product_id": "NOVA-MVP",
        "customer_name": "Precision Vision Co.",
        "customer_code": "CUST-01",
        "customer_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "license_number": "NOVA-2026-000001",
        "license_id": "11111111-2222-3333-4444-555555555555",
        "schema_version": "1.0",
    }
    bytes_a = canonicalize_payload(payload_a)
    bytes_b = canonicalize_payload(payload_b)
    assert bytes_a == bytes_b
    assert b'"expires_at":null' in bytes_a
    assert b'"features":["alpha_ocr","zebra_inspection"]' in bytes_a


def test_crypto_signing_and_tamper_detection():
    priv_pem, pub_pem = generate_ed25519_keypair_pem()
    from cryptography.hazmat.primitives import serialization
    priv_key = serialization.load_pem_private_key(priv_pem.encode("utf-8"), password=None)

    payload = {
        "schema_version": "1.0",
        "license_id": "11111111-2222-3333-4444-555555555555",
        "license_number": "NOVA-2026-000001",
        "customer_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "customer_code": "CUST-01",
        "customer_name": "Precision Vision Co.",
        "product_id": "NOVA-MVP",
        "edition": "production",
        "license_type": "SUBSCRIPTION",
        "issued_at": "2026-10-25T15:00:00Z",
        "not_before": "2026-10-25T15:00:00Z",
        "expires_at": "2027-10-25T15:00:00Z",
        "features": ["deep_learning_ocr", "plc_modbus_profinet"],
        "limits": {
            "max_devices": 2,
            "max_concurrent_inspections": 4,
            "total_inspection_quota": -1,
        },
        "key_id": "key-v1",
    }

    _, _, envelope = sign_license_payload(payload, priv_key, "key-v1")

    # 1. Valid artifact verifies
    verified_payload = verify_license_envelope(envelope, pub_pem)
    assert verified_payload["license_number"] == "NOVA-2026-000001"

    # 2. Tamper with any signed field (expires_at, max_devices, edition, features, customer_code)
    for tamper_fn in [
        lambda env: env["payload"].__setitem__("expires_at", "2029-10-25T15:00:00Z"),
        lambda env: env["payload"]["limits"].__setitem__("max_devices", 99),
        lambda env: env["payload"].__setitem__("edition", "developer"),
        lambda env: env["payload"]["features"].append("extra_unauthorized_feature"),
        lambda env: env["payload"].__setitem__("customer_code", "CUST-HACKED"),
    ]:
        tampered = copy.deepcopy(envelope)
        tamper_fn(tampered)
        with pytest.raises(SignatureVerificationError):
            verify_license_envelope(tampered, pub_pem)

    # 3. Modified signature fails verification
    bad_sig_env = copy.deepcopy(envelope)
    sig_bytes = bytearray(base64.b64decode(bad_sig_env["signature"]))
    sig_bytes[0] ^= 0xFF
    bad_sig_env["signature"] = base64.b64encode(bytes(sig_bytes)).decode("ascii")
    with pytest.raises(SignatureVerificationError):
        verify_license_envelope(bad_sig_env, pub_pem)

    # 4. Unsupported algorithm fails safely
    bad_alg_env = copy.deepcopy(envelope)
    bad_alg_env["algorithm"] = "RSA-SHA256"
    with pytest.raises(SignatureVerificationError, match="Unsupported signature algorithm"):
        verify_license_envelope(bad_alg_env, pub_pem)


# =====================================================================
# 2. API SECURITY & RBAC AUTHORIZATION TESTS
# =====================================================================

def test_unauthenticated_and_readonly_auditor_restrictions(client: TestClient):
    r_unauth = client.get("/api/customers")
    assert r_unauth.status_code == 401

    r_issue_unauth = client.post("/api/licenses", json={"customer_id": "x", "plan_id": "y"})
    assert r_issue_unauth.status_code == 401

    auditor_headers = get_auth_headers(client, "test_auditor", "StrongAuditorPass!2026")
    r_read = client.get("/api/customers", headers=auditor_headers)
    assert r_read.status_code == 200

    r_create_denied = client.post(
        "/api/customers",
        headers=auditor_headers,
        json={
            "customer_code": "CUST-UNAUTH",
            "company_name": "Unauthorized Corp",
            "contact_person": "John",
            "contact_email": "john@unauth.com",
        },
    )
    assert r_create_denied.status_code == 403

    admin_headers = get_auth_headers(client, "test_admin", "StrongAdminPass!2026")
    r_val_err = client.post(
        "/api/customers",
        headers=admin_headers,
        json={"customer_code": "INVALID CODE WITH SPACES"},
    )
    assert r_val_err.status_code == 422
    assert "StrongAdminPass" not in r_val_err.text
    assert "PRIVATE KEY" not in r_val_err.text


# =====================================================================
# 3. CUSTOMER MANAGEMENT TESTS
# =====================================================================

def test_customer_crud_duplicate_and_inactive_handling(client: TestClient):
    headers = get_auth_headers(client, "test_admin", "StrongAdminPass!2026")

    create_resp = client.post(
        "/api/customers",
        headers=headers,
        json={
            "customer_code": "cust-acme-01",
            "company_name": "Acme Robotics Vietnam",
            "contact_person": "Nguyen Van A",
            "contact_email": "contact@acme-robotics.vn",
            "contact_phone": "+84-901234567",
            "country_region": "Vietnam",
            "address": "Hi-Tech Park, Ho Chi Minh City",
            "notes": "Key automotive tier-1 customer",
        },
    )
    assert create_resp.status_code == 201
    cust = create_resp.json()
    assert cust["customer_code"] == "CUST-ACME-01"
    assert cust["status"] == "ACTIVE"
    customer_id = cust["id"]

    dup_resp = client.post(
        "/api/customers",
        headers=headers,
        json={
            "customer_code": "CUST-ACME-01",
            "company_name": "Another Company",
            "contact_person": "Jane",
            "contact_email": "jane@another.com",
        },
    )
    assert dup_resp.status_code == 409

    patch_resp = client.patch(
        f"/api/customers/{customer_id}",
        headers=headers,
        json={"contact_person": "Tran Thi B", "country_region": "VN"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["contact_person"] == "Tran Thi B"

    deact_resp = client.post(
        f"/api/customers/{customer_id}/deactivate",
        headers=headers,
        json={"reason": "Contract paused for Q4 review"},
    )
    assert deact_resp.status_code == 200
    assert deact_resp.json()["status"] == "INACTIVE"


# =====================================================================
# 4. LICENSE PLANS & IMMUTABLE SNAPSHOT TESTS
# =====================================================================

def test_license_plan_validation_and_snapshot_immutability(client: TestClient):
    headers = get_auth_headers(client, "test_admin", "StrongAdminPass!2026")
    products = client.get("/api/products", headers=headers).json()
    product_id = products[0]["id"]

    bad_plan = client.post(
        "/api/license-plans",
        headers=headers,
        json={
            "plan_code": "BAD-LIMIT-PLAN",
            "plan_name": "Bad Limit Plan",
            "product_id": product_id,
            "edition": "production",
            "license_type": "SUBSCRIPTION",
            "default_duration_days": 365,
            "features": ["ocr"],
            "max_devices": -5,
            "max_concurrent_inspections": 1,
            "total_inspection_quota": -1,
        },
    )
    assert bad_plan.status_code == 422

    plan_resp = client.post(
        "/api/license-plans",
        headers=headers,
        json={
            "plan_code": "PROD-SUB-365",
            "plan_name": "Production Annual Plan",
            "product_id": product_id,
            "edition": "production",
            "license_type": "SUBSCRIPTION",
            "default_duration_days": 365,
            "features": ["surface_defect", "barcode_reader"],
            "max_devices": 2,
            "max_concurrent_inspections": 4,
            "total_inspection_quota": 0,
        },
    )
    assert plan_resp.status_code == 201
    plan = plan_resp.json()
    plan_id = plan["id"]

    cust_resp = client.post(
        "/api/customers",
        headers=headers,
        json={
            "customer_code": "CUST-SNAPSHOT",
            "company_name": "Snapshot Test Corp",
            "contact_person": "Alice",
            "contact_email": "alice@snapshot-corp.com",
        },
    )
    assert cust_resp.status_code == 201, cust_resp.text
    cust_id = cust_resp.json()["id"]

    lic_resp = client.post(
        "/api/licenses",
        headers=headers,
        json={"customer_id": cust_id, "plan_id": plan_id},
    )
    assert lic_resp.status_code == 201
    issued_lic = lic_resp.json()
    assert issued_lic["features_snapshot"] == ["barcode_reader", "surface_defect"]
    assert issued_lic["limits_snapshot"]["max_devices"] == 2
    assert issued_lic["limits_snapshot"]["total_inspection_quota"] == 0

    upd_plan = client.patch(
        f"/api/license-plans/{plan_id}",
        headers=headers,
        json={
            "plan_name": "Updated Plan Name",
            "features": ["only_new_feature"],
            "max_devices": 10,
        },
    )
    assert upd_plan.status_code == 200

    fetched_lic = client.get(f"/api/licenses/{issued_lic['id']}", headers=headers).json()
    assert fetched_lic["features_snapshot"] == ["barcode_reader", "surface_defect"]
    assert fetched_lic["limits_snapshot"]["max_devices"] == 2
    assert fetched_lic["signature_verified"] is True


# =====================================================================
# 5. LICENSE ISSUANCE, PERPETUAL SEMANTICS & FAILURE SAFETY TESTS
# =====================================================================

def test_issuance_perpetual_missing_key_and_db_failure(client: TestClient, test_db_session):
    db, tmp_path, monkeypatch = test_db_session
    headers = get_auth_headers(client, "test_admin", "StrongAdminPass!2026")
    product_id = client.get("/api/products", headers=headers).json()[0]["id"]

    perp_plan_id = client.post(
        "/api/license-plans",
        headers=headers,
        json={
            "plan_code": "PROD-PERP-UNLIM",
            "plan_name": "Production Perpetual Unlimited",
            "product_id": product_id,
            "edition": "production",
            "license_type": "PERPETUAL",
            "features": ["deep_learning_ocr", "high_speed_acquisition"],
            "max_devices": 1,
            "max_concurrent_inspections": -1,
            "total_inspection_quota": -1,
        },
    ).json()["id"]

    cust_resp = client.post(
        "/api/customers",
        headers=headers,
        json={
            "customer_code": "CUST-PERP-01",
            "company_name": "Eternal Vision Ltd",
            "contact_person": "Bob",
            "contact_email": "bob@eternal-vision.com",
        },
    )
    assert cust_resp.status_code == 201, cust_resp.text
    cust_id = cust_resp.json()["id"]

    perp_lic_resp = client.post(
        "/api/licenses",
        headers=headers,
        json={"customer_id": cust_id, "plan_id": perp_plan_id},
    )
    assert perp_lic_resp.status_code == 201
    perp_lic = perp_lic_resp.json()
    assert perp_lic["license_type"] == "PERPETUAL"
    assert perp_lic["expires_at"] is None
    assert perp_lic["effective_status"] == "ACTIVE"
    assert perp_lic["signature_verified"] is True

    dl_resp = client.get(f"/api/licenses/{perp_lic['id']}/download", headers=headers)
    assert dl_resp.status_code == 200
    artifact_data = dl_resp.json()
    assert "private_key" not in json.dumps(artifact_data).lower()
    assert artifact_data["payload"]["expires_at"] is None

    del_cust = client.delete(f"/api/customers/{cust_id}", headers=headers)
    assert del_cust.status_code == 409

    client.post(f"/api/customers/{cust_id}/deactivate", headers=headers, json={"reason": "Deactivated"})
    inactive_issue = client.post(
        "/api/licenses",
        headers=headers,
        json={"customer_id": cust_id, "plan_id": perp_plan_id},
    )
    assert inactive_issue.status_code == 400

    still_there = client.get(f"/api/licenses/{perp_lic['id']}", headers=headers)
    assert still_there.status_code == 200

    client.post(f"/api/customers/{cust_id}/activate", headers=headers)

    monkeypatch.setattr(settings, "NOVA_SIGNING_PRIVATE_KEY_PATH", str(tmp_path / "nonexistent.pem"))
    no_key_resp = client.post(
        "/api/licenses",
        headers=headers,
        json={"customer_id": cust_id, "plan_id": perp_plan_id},
    )
    assert no_key_resp.status_code == 503
    assert "unavailable" in no_key_resp.json()["detail"].lower()

    monkeypatch.setattr(settings, "NOVA_SIGNING_PRIVATE_KEY_PATH", str(tmp_path / "test_key_1.pem"))

    count_before = len(client.get("/api/licenses", headers=headers).json()["items"])
    with patch("app.services.license_service.verify_license_envelope", side_effect=SignatureVerificationError("Simulated post-sign verification failure")):
        fail_verify_resp = client.post(
            "/api/licenses",
            headers=headers,
            json={"customer_id": cust_id, "plan_id": perp_plan_id},
        )
        assert fail_verify_resp.status_code == 500
    count_after = len(client.get("/api/licenses", headers=headers).json()["items"])
    assert count_after == count_before


# =====================================================================
# 6. KEY ROTATION, RENEWAL, REPLACEMENT, SUSPENSION, REVOCATION & AUDIT
# =====================================================================

def test_key_rotation_and_lifecycle_workflows(client: TestClient, test_db_session):
    db, tmp_path, monkeypatch = test_db_session
    headers = get_auth_headers(client, "test_admin", "StrongAdminPass!2026")
    product_id = client.get("/api/products", headers=headers).json()[0]["id"]

    sub_plan_id = client.post(
        "/api/license-plans",
        headers=headers,
        json={
            "plan_code": "DEV-SUB-90D",
            "plan_name": "Developer 90-Day Subscription",
            "product_id": product_id,
            "edition": "developer",
            "license_type": "SUBSCRIPTION",
            "default_duration_days": 90,
            "features": ["pipeline_studio"],
            "max_devices": 1,
            "max_concurrent_inspections": 2,
            "total_inspection_quota": 10000,
        },
    ).json()["id"]

    cust_resp = client.post(
        "/api/customers",
        headers=headers,
        json={
            "customer_code": "CUST-LIFECYCLE",
            "company_name": "Lifecycle Optics Corp",
            "contact_person": "Dr. Lee",
            "contact_email": "lee@lifecycle-optics.com",
        },
    )
    assert cust_resp.status_code == 201, cust_resp.text
    cust_id = cust_resp.json()["id"]

    lic1 = client.post(
        "/api/licenses",
        headers=headers,
        json={"customer_id": cust_id, "plan_id": sub_plan_id},
    ).json()
    assert lic1["key_id"] == "test-key-2026-01"

    priv_pem_2, pub_pem_2 = generate_ed25519_keypair_pem()
    key_file_2 = tmp_path / "test_key_2.pem"
    key_file_2.write_text(priv_pem_2, encoding="utf-8")

    rot_resp = client.post(
        "/api/signing-keys",
        headers=headers,
        json={
            "key_id": "test-key-2026-02",
            "public_key_pem": pub_pem_2,
            "description": "Rotated 2026 Q4 signing key",
            "set_active": True,
        },
    )
    assert rot_resp.status_code == 201
    monkeypatch.setattr(settings, "NOVA_ACTIVE_KEY_ID", "test-key-2026-02")
    monkeypatch.setattr(settings, "NOVA_SIGNING_PRIVATE_KEY_PATH", str(key_file_2))

    renew_resp = client.post(
        f"/api/licenses/{lic1['id']}/renew",
        headers=headers,
        json={"duration_days": 180, "reason": "Customer renewed for 6 months"},
    )
    assert renew_resp.status_code == 201
    lic2 = renew_resp.json()
    assert lic2["id"] != lic1["id"]
    assert lic2["license_number"] != lic1["license_number"]
    assert lic2["key_id"] == "test-key-2026-02"
    assert len(lic2["lineage_previous"]) == 1
    assert lic2["lineage_previous"][0]["previous_license_id"] == lic1["id"]
    assert lic2["lineage_previous"][0]["relationship_type"] == "RENEWAL"

    v1 = client.post(f"/api/licenses/{lic1['id']}/verify", headers=headers).json()
    v2 = client.post(f"/api/licenses/{lic2['id']}/verify", headers=headers).json()
    assert v1["valid"] is True
    assert v2["valid"] is True

    # Unknown key_id verification fails cleanly
    unknown_key_env = copy.deepcopy(lic2["signed_artifact_json"])
    unknown_key_env["key_id"] = "unknown-key-9999"
    unknown_key_env["payload"]["key_id"] = "unknown-key-9999"
    v_unknown = client.post("/api/licenses/verify-artifact", headers=headers, json={"artifact": unknown_key_env}).json()
    assert v_unknown["valid"] is False
    assert "unknown signing key" in v_unknown["reason"].lower()

    replace_resp = client.post(
        f"/api/licenses/{lic2['id']}/replace",
        headers=headers,
        json={
            "reason": "Upgraded station concurrency limit",
            "custom_limits": {
                "max_devices": 2,
                "max_concurrent_inspections": 4,
                "total_inspection_quota": 50000,
            },
        },
    )
    assert replace_resp.status_code == 201
    lic3 = replace_resp.json()
    lic2_after = client.get(f"/api/licenses/{lic2['id']}", headers=headers).json()
    assert lic2_after["status"] == "REPLACED"
    assert lic2_after["effective_status"] == "REPLACED"

    susp_resp = client.post(
        f"/api/licenses/{lic3['id']}/suspend",
        headers=headers,
        json={"reason": "Temporary billing hold"},
    )
    assert susp_resp.status_code == 200
    assert susp_resp.json()["effective_status"] == "SUSPENDED"

    rev_resp = client.post(
        f"/api/licenses/{lic3['id']}/revoke",
        headers=headers,
        json={"reason": "Decommissioned station"},
    )
    assert rev_resp.status_code == 200
    assert rev_resp.json()["effective_status"] == "REVOKED"

    logs_resp = client.get("/api/audit-logs?page_size=100", headers=headers)
    assert logs_resp.status_code == 200
    logs_text = logs_resp.text
    assert "BEGIN PRIVATE KEY" not in logs_text
    assert "StrongAdminPass" not in logs_text

    actions_logged = {item["action"] for item in logs_resp.json()["items"]}
    for expected_action in (
        "CUSTOMER_CREATED",
        "LICENSE_PLAN_CREATED",
        "LICENSE_ISSUED",
        "SIGNING_KEY_ROTATED",
        "LICENSE_RENEWED",
        "LICENSE_REPLACED",
        "LICENSE_SUSPENDED",
        "LICENSE_REVOKED",
    ):
        assert expected_action in actions_logged


def test_all_software_features_default_entitlement(client):
    from app.features import ALL_SOFTWARE_FEATURES, is_all_features_entitlement

    headers = get_auth_headers(client, "test_admin", "StrongAdminPass!2026")
    # 1. GET /api/features endpoint
    resp = client.get("/api/features", headers=headers)
    assert resp.status_code == 200
    features = resp.json()
    assert "*" in features
    assert "deep_learning_ocr" in features

    # 2. Plan creation with empty features defaults to all software features
    products = client.get("/api/products", headers=headers).json()
    product_id = products[0]["id"]
    p_resp = client.post(
        "/api/license-plans",
        headers=headers,
        json={
            "plan_code": "TEST-ALL-FEAT-PLAN",
            "plan_name": "Test All Features Default",
            "product_id": product_id,
            "edition": "production",
            "license_type": "PERPETUAL",
            "features": [],
            "max_devices": 1,
            "max_concurrent_inspections": 1,
            "total_inspection_quota": -1,
        },
    )
    assert p_resp.status_code == 201
    plan_data = p_resp.json()
    assert "*" in plan_data["features"]
    assert is_all_features_entitlement(plan_data["features"])

    # 3. Issuing license inherits all software features by default
    cust_resp = client.post(
        "/api/customers",
        headers=headers,
        json={
            "customer_code": "CUST-ALL-FEAT",
            "company_name": "All Features Factory",
            "contact_person": "Operator",
            "contact_email": "op@factory.com",
        },
    )
    cust_id = cust_resp.json()["id"]

    lic_resp = client.post(
        "/api/licenses",
        headers=headers,
        json={
            "customer_id": cust_id,
            "plan_id": plan_data["id"],
        },
    )
    assert lic_resp.status_code == 201
    lic_data = lic_resp.json()
    assert "*" in lic_data["features_snapshot"]
    assert set(ALL_SOFTWARE_FEATURES).issubset(set(lic_data["features_snapshot"]))
    assert lic_data["signature_verified"] is True
