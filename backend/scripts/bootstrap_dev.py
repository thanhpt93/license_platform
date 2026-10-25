"""
Development Environment Bootstrap Utility for NOVA License Management.

Usage:
    python scripts/bootstrap_dev.py --admin-password "<PASSWORD>"

What this script does:
1. Generates a local development Ed25519 key pair in `backend/keys/` if not already present.
2. Writes a local `backend/.env` pointing to the generated private key and SQLite database if `.env` does not exist.
3. Registers the public key (`nova-key-2026-01`), initial product (`NOVA-MVP`), standard license plans,
   and initial administrator user in the database.

IMPORTANT:
- This script is strictly for explicit operator/developer initialization.
- The backend application NEVER runs this automatically on startup.
"""
import argparse
import os
import secrets
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.audit import record_audit_event  # noqa: E402
from app.auth import hash_password  # noqa: E402
from app.crypto import compute_public_key_fingerprint, generate_ed25519_keypair_pem  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Customer, LicensePlan, Product, SigningKey, User  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Bootstrap local development environment for NOVA License Management")
    parser.add_argument(
        "--admin-username",
        default=os.environ.get("NOVA_BOOTSTRAP_ADMIN_USERNAME", "admin"),
        help="Initial Super Administrator username",
    )
    parser.add_argument(
        "--admin-email",
        default=os.environ.get("NOVA_BOOTSTRAP_ADMIN_EMAIL", "admin@nova-vision.local"),
        help="Initial Super Administrator email",
    )
    parser.add_argument(
        "--admin-password",
        default=os.environ.get("NOVA_BOOTSTRAP_ADMIN_PASSWORD"),
        help="Initial Super Administrator password (if omitted, a random password is generated and displayed once)",
    )
    parser.add_argument(
        "--key-id",
        default="nova-key-2026-01",
        help="Initial active Ed25519 key ID",
    )
    args = parser.parse_args()

    keys_dir = BACKEND_DIR / "keys"
    keys_dir.mkdir(parents=True, exist_ok=True)
    priv_key_path = keys_dir / f"{args.key_id}_private.pem"
    pub_key_path = keys_dir / f"{args.key_id}_public.pem"

    if not priv_key_path.exists() or not pub_key_path.exists():
        priv_pem, pub_pem = generate_ed25519_keypair_pem()
        priv_key_path.write_text(priv_pem, encoding="utf-8")
        pub_key_path.write_text(pub_pem, encoding="utf-8")
        print(f"[Bootstrap] Generated development Ed25519 key pair at: {keys_dir}")
    else:
        pub_pem = pub_key_path.read_text(encoding="utf-8")
        print(f"[Bootstrap] Using existing Ed25519 key pair at: {keys_dir}")

    env_path = BACKEND_DIR / ".env"
    if not env_path.exists():
        jwt_secret = secrets.token_hex(32)
        env_content = (
            f"NOVA_DATABASE_URL=sqlite:///./nova_license.db\n"
            f"NOVA_JWT_SECRET_KEY={jwt_secret}\n"
            f"NOVA_JWT_ALGORITHM=HS256\n"
            f"NOVA_ACCESS_TOKEN_EXPIRE_MINUTES=480\n"
            f"NOVA_ACTIVE_KEY_ID={args.key_id}\n"
            f"NOVA_SIGNING_PRIVATE_KEY_PATH=./keys/{args.key_id}_private.pem\n"
            f"NOVA_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000\n"
        )
        env_path.write_text(env_content, encoding="utf-8")
        print(f"[Bootstrap] Created local configuration file: {env_path}")

    admin_password = args.admin_password
    generated_random_pw = False
    if not admin_password:
        admin_password = secrets.token_urlsafe(12)
        generated_random_pw = True

    db = SessionLocal()
    try:
        # 1. Admin User
        admin_user = db.query(User).filter(User.username == args.admin_username).first()
        if not admin_user:
            admin_user = User(
                username=args.admin_username,
                email=args.admin_email,
                full_name="NOVA System Administrator",
                password_hash=hash_password(admin_password),
                role="SUPER_ADMIN",
                is_active=True,
            )
            db.add(admin_user)
            db.flush()
            record_audit_event(
                db,
                actor=admin_user,
                action="BOOTSTRAP_ADMIN_CREATED",
                entity_type="USER",
                entity_id=admin_user.id,
                outcome="SUCCESS",
                reason="Initial Super Administrator created via bootstrap_dev.py",
            )
            print(f"[Bootstrap] Created SUPER_ADMIN user: {args.admin_username}")
            if generated_random_pw:
                print(f"[Bootstrap] Generated Admin Password: {admin_password}")
        else:
            if args.admin_password:
                admin_user.password_hash = hash_password(args.admin_password)
                print(f"[Bootstrap] Updated password for existing admin user: {args.admin_username}")

        # 2. Auditor User (Read-only role for testing RBAC)
        auditor_user = db.query(User).filter(User.username == "auditor").first()
        if not auditor_user:
            auditor_user = User(
                username="auditor",
                email="auditor@nova-vision.local",
                full_name="NOVA Security Auditor",
                password_hash=hash_password(admin_password),
                role="AUDITOR",
                is_active=True,
            )
            db.add(auditor_user)
            db.flush()

        # 3. Active Signing Key registration
        signing_key = db.query(SigningKey).filter(SigningKey.key_id == args.key_id).first()
        if not signing_key:
            fingerprint = compute_public_key_fingerprint(pub_pem)
            signing_key = SigningKey(
                key_id=args.key_id,
                algorithm="Ed25519",
                public_key_pem=pub_pem.strip(),
                fingerprint_sha256=fingerprint,
                is_active=True,
                status="ACTIVE",
                description="Primary Ed25519 signing key for NOVA Machine Vision Platform",
            )
            db.add(signing_key)
            db.flush()
            record_audit_event(
                db,
                actor=admin_user,
                action="SIGNING_KEY_REGISTERED",
                entity_type="SIGNING_KEY",
                entity_id=signing_key.key_id,
                outcome="SUCCESS",
                reason=f"Registered active signing key {signing_key.key_id}",
                metadata={"fingerprint_sha256": fingerprint},
            )
            print(f"[Bootstrap] Registered active public key: {args.key_id}")

        # 4. Initial Product: NOVA-MVP
        product = db.query(Product).filter(Product.product_code == "NOVA-MVP").first()
        if not product:
            product = Product(
                product_code="NOVA-MVP",
                product_name="NOVA Machine Vision Platform",
                description="Industrial AI & Rule-Based Machine Vision Inspection Platform",
                supported_editions=["developer", "production"],
                status="ACTIVE",
            )
            db.add(product)
            db.flush()
            print("[Bootstrap] Registered product: NOVA-MVP (NOVA Machine Vision Platform)")

        # 5. Initial Commercial License Plans
        default_plans = [
            {
                "plan_code": "NOVA-DEV-SUB-1Y",
                "plan_name": "NOVA Developer Annual Subscription",
                "edition": "developer",
                "description": "Full pipeline authoring, simulation, and camera calibration suite for vision engineers.",
                "license_type": "SUBSCRIPTION",
                "default_duration_days": 365,
                "features": [
                    "pipeline_studio",
                    "offline_simulator",
                    "camera_calibration",
                    "deep_learning_ocr",
                    "surface_defect_detection",
                ],
                "max_devices": 2,
                "max_concurrent_inspections": 2,
                "total_inspection_quota": -1,
                "allow_custom_duration": True,
                "allow_custom_limits": True,
            },
            {
                "plan_code": "NOVA-PROD-SUB-1Y",
                "plan_name": "NOVA Production Line Annual Subscription",
                "edition": "production",
                "description": "High-speed runtime execution license for factory floor inspection stations.",
                "license_type": "SUBSCRIPTION",
                "default_duration_days": 365,
                "features": [
                    "high_speed_acquisition",
                    "multi_camera_sync",
                    "plc_modbus_profinet",
                    "deep_learning_ocr",
                    "surface_defect_detection",
                    "spc_telemetry_export",
                ],
                "max_devices": 1,
                "max_concurrent_inspections": 4,
                "total_inspection_quota": -1,
                "allow_custom_duration": True,
                "allow_custom_limits": True,
            },
            {
                "plan_code": "NOVA-PROD-PERP",
                "plan_name": "NOVA Production Perpetual Entitlement",
                "edition": "production",
                "description": "Perpetual factory station license with unlimited runtime duration and multi-line support.",
                "license_type": "PERPETUAL",
                "default_duration_days": None,
                "features": [
                    "high_speed_acquisition",
                    "multi_camera_sync",
                    "plc_modbus_profinet",
                    "deep_learning_ocr",
                    "surface_defect_detection",
                    "spc_telemetry_export",
                    " EtherCAT_trigger_bridge".strip(),
                ],
                "max_devices": 4,
                "max_concurrent_inspections": 8,
                "total_inspection_quota": -1,
                "allow_custom_duration": False,
                "allow_custom_limits": True,
            },
        ]

        for p_data in default_plans:
            existing_plan = db.query(LicensePlan).filter(LicensePlan.plan_code == p_data["plan_code"]).first()
            if not existing_plan:
                plan = LicensePlan(
                    plan_code=p_data["plan_code"],
                    plan_name=p_data["plan_name"],
                    product_id=product.id,
                    edition=p_data["edition"],
                    description=p_data["description"],
                    license_type=p_data["license_type"],
                    default_duration_days=p_data["default_duration_days"],
                    features=sorted(p_data["features"]),
                    max_devices=p_data["max_devices"],
                    max_concurrent_inspections=p_data["max_concurrent_inspections"],
                    total_inspection_quota=p_data["total_inspection_quota"],
                    allow_custom_duration=p_data["allow_custom_duration"],
                    allow_custom_limits=p_data["allow_custom_limits"],
                    status="ACTIVE",
                )
                db.add(plan)
                print(f"[Bootstrap] Created license plan: {p_data['plan_code']}")

        db.commit()
        print("[Bootstrap] Initialization completed successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
