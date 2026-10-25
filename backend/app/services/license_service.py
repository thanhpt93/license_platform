import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.audit import record_audit_event
from app.crypto import (
    CryptoConfigurationError,
    PAYLOAD_SCHEMA_VERSION,
    SignatureVerificationError,
    format_utc_timestamp,
    load_configured_private_key,
    sign_license_payload,
    verify_license_envelope,
)
from app.models import (
    Customer,
    License,
    LicensePlan,
    LicenseRelationship,
    Product,
    SigningKey,
    User,
)
from app.schemas import (
    LicenseIssueRequest,
    LicenseRelationshipItem,
    LicenseRenewRequest,
    LicenseReplaceRequest,
    LicenseResponse,
)


def compute_effective_status(license_obj: License, now: Optional[datetime] = None) -> str:
    """
    Computes the authoritative license status using server UTC time.
    - Explicit administrative states (REVOKED, SUSPENDED, REPLACED) take precedence.
    - PERPETUAL licenses with status ACTIVE remain ACTIVE (never expire based on null expires_at).
    - SUBSCRIPTION licenses with status ACTIVE whose expires_at <= now are EXPIRED.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if license_obj.status in ("REVOKED", "SUSPENDED", "REPLACED", "EXPIRED"):
        return license_obj.status

    if license_obj.license_type == "SUBSCRIPTION" and license_obj.expires_at is not None:
        expires_utc = (
            license_obj.expires_at.replace(tzinfo=timezone.utc)
            if license_obj.expires_at.tzinfo is None
            else license_obj.expires_at.astimezone(timezone.utc)
        )
        if expires_utc <= now:
            return "EXPIRED"

    return "ACTIVE"


def generate_unique_license_number(db: Session, now: datetime) -> str:
    """
    Generates a unique human-readable license number: NOVA-YYYY-NNNNNN.
    Ensures no collision in the database.
    """
    year = now.year
    prefix = f"NOVA-{year}-"
    count = db.query(func.count(License.id)).filter(License.license_number.like(f"{prefix}%")).scalar() or 0
    seq = count + 1
    while True:
        candidate = f"{prefix}{seq:06d}"
        exists = db.query(License.id).filter(License.license_number == candidate).first()
        if not exists:
            return candidate
        seq += 1


def build_license_response(
    db: Session,
    lic: License,
    include_verification: bool = False,
) -> LicenseResponse:
    now = datetime.now(timezone.utc)
    eff_status = compute_effective_status(lic, now)

    signature_verified: Optional[bool] = None
    if include_verification:
        signing_key = db.query(SigningKey).filter(SigningKey.key_id == lic.key_id).first()
        if signing_key and signing_key.status != "COMPROMISED":
            try:
                verify_license_envelope(lic.signed_artifact_json, signing_key.public_key_pem)
                signature_verified = True
            except Exception:
                signature_verified = False
        else:
            signature_verified = False

    prev_items = []
    for rel in lic.incoming_relationships:
        prev_lic = db.query(License).filter(License.id == rel.previous_license_id).first()
        prev_items.append(
            LicenseRelationshipItem(
                id=rel.id,
                previous_license_id=rel.previous_license_id,
                previous_license_number=prev_lic.license_number if prev_lic else None,
                new_license_id=rel.new_license_id,
                new_license_number=lic.license_number,
                relationship_type=rel.relationship_type,
                reason=rel.reason,
                created_at=rel.created_at,
            )
        )

    next_items = []
    for rel in lic.outgoing_relationships:
        next_lic = db.query(License).filter(License.id == rel.new_license_id).first()
        next_items.append(
            LicenseRelationshipItem(
                id=rel.id,
                previous_license_id=rel.previous_license_id,
                previous_license_number=lic.license_number,
                new_license_id=rel.new_license_id,
                new_license_number=next_lic.license_number if next_lic else None,
                relationship_type=rel.relationship_type,
                reason=rel.reason,
                created_at=rel.created_at,
            )
        )

    return LicenseResponse(
        id=lic.id,
        license_number=lic.license_number,
        customer_id=lic.customer_id,
        customer_code=lic.customer.customer_code if lic.customer else None,
        customer_name=lic.customer.company_name if lic.customer else None,
        product_id=lic.product_id,
        product_code_snapshot=lic.product_code_snapshot,
        plan_id=lic.plan_id,
        plan_code_snapshot=lic.plan_code_snapshot,
        plan_name_snapshot=lic.plan_name_snapshot,
        schema_version=lic.schema_version,
        edition=lic.edition,
        license_type=lic.license_type,
        issued_at=lic.issued_at,
        not_before=lic.not_before,
        expires_at=lic.expires_at,
        features_snapshot=lic.features_snapshot,
        limits_snapshot=lic.limits_snapshot,
        key_id=lic.key_id,
        signature_algorithm=lic.signature_algorithm,
        signature_b64=lic.signature_b64,
        signed_artifact_json=lic.signed_artifact_json,
        status=lic.status,
        effective_status=eff_status,
        status_reason=lic.status_reason,
        status_updated_at=lic.status_updated_at,
        notes=lic.notes,
        created_at=lic.created_at,
        signature_verified=signature_verified,
        lineage_previous=prev_items,
        lineage_next=next_items,
    )


def _create_signed_license_record(
    db: Session,
    *,
    customer: Customer,
    plan: LicensePlan,
    product: Product,
    actor: User,
    not_before_dt: datetime,
    duration_days: Optional[int],
    custom_limits: Optional[Dict[str, int]],
    notes: Optional[str],
) -> License:
    """
    Core atomic helper that constructs the canonical payload, signs it, verifies the signature
    before accepting it, and creates the License ORM object inside the caller's transaction.
    """
    # 1. Verify active signing key is configured and registered in DB
    try:
        key_id, private_key = load_configured_private_key()
    except CryptoConfigurationError as exc:
        record_audit_event(
            db,
            actor=actor,
            action="LICENSE_ISSUANCE_FAILED",
            entity_type="LICENSE",
            outcome="FAILURE",
            reason=str(exc),
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Signing key unavailable: {exc}",
        ) from exc

    signing_key_record = (
        db.query(SigningKey)
        .filter(SigningKey.key_id == key_id, SigningKey.is_active.is_(True), SigningKey.status == "ACTIVE")
        .first()
    )
    if not signing_key_record:
        record_audit_event(
            db,
            actor=actor,
            action="LICENSE_ISSUANCE_FAILED",
            entity_type="LICENSE",
            outcome="FAILURE",
            reason=f"Configured key_id '{key_id}' is not registered as an active SigningKey in the database.",
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Signing key '{key_id}' is not registered as active in the database.",
        )

    now = datetime.now(timezone.utc).replace(microsecond=0)
    if not_before_dt.tzinfo is None:
        not_before_dt = not_before_dt.replace(tzinfo=timezone.utc, microsecond=0)
    else:
        not_before_dt = not_before_dt.astimezone(timezone.utc).replace(microsecond=0)

    # 2. Compute expiration based on plan & overrides
    expires_at_dt: Optional[datetime] = None
    if plan.license_type == "SUBSCRIPTION":
        if duration_days is not None and duration_days != plan.default_duration_days:
            if not plan.allow_custom_duration:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This license plan does not allow custom duration overrides.",
                )
            effective_days = duration_days
        else:
            effective_days = plan.default_duration_days
        if not effective_days or effective_days <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subscription license requires a positive duration in days.",
            )
        expires_at_dt = not_before_dt + timedelta(days=effective_days)
    elif plan.license_type == "PERPETUAL":
        if duration_days is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Perpetual license plans cannot specify a duration_days expiration.",
            )
        expires_at_dt = None

    # 3. Compute immutable limits snapshot
    default_limits = {
        "max_devices": plan.max_devices,
        "max_concurrent_inspections": plan.max_concurrent_inspections,
        "total_inspection_quota": plan.total_inspection_quota,
    }
    if custom_limits is not None and custom_limits != default_limits:
        if not plan.allow_custom_limits:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This license plan does not allow custom limit overrides.",
            )
        limits_snapshot = dict(custom_limits)
    else:
        limits_snapshot = default_limits

    features_snapshot = sorted({str(f).strip() for f in (plan.features or []) if str(f).strip()})

    # 4. Generate unique identifiers
    license_id = str(uuid.uuid4())
    license_number = generate_unique_license_number(db, now)

    # 5. Build canonical payload
    payload: Dict[str, Any] = {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "license_id": license_id,
        "license_number": license_number,
        "customer_id": customer.id,
        "customer_code": customer.customer_code,
        "customer_name": customer.company_name,
        "product_id": product.product_code,
        "edition": plan.edition,
        "license_type": plan.license_type,
        "issued_at": format_utc_timestamp(now),
        "not_before": format_utc_timestamp(not_before_dt),
        "expires_at": format_utc_timestamp(expires_at_dt),
        "features": features_snapshot,
        "limits": limits_snapshot,
        "key_id": key_id,
    }

    # 6. Sign payload AND immediately verify signature before accepting issuance
    try:
        canonical_json_str, signature_b64, envelope = sign_license_payload(
            payload=payload,
            private_key=private_key,
            key_id=key_id,
        )
        verify_license_envelope(envelope, signing_key_record.public_key_pem)
    except (CryptoConfigurationError, SignatureVerificationError, Exception) as exc:
        record_audit_event(
            db,
            actor=actor,
            action="LICENSE_SIGN_OR_VERIFY_FAILED",
            entity_type="LICENSE",
            outcome="FAILURE",
            reason=f"Cryptographic signing or self-verification failed: {exc}",
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"License signing or post-signing verification failed: {exc}",
        ) from exc

    # 7. Instantiate ORM record (persisted inside caller's transaction)
    new_license = License(
        id=license_id,
        license_number=license_number,
        customer_id=customer.id,
        product_id=product.id,
        plan_id=plan.id,
        schema_version=PAYLOAD_SCHEMA_VERSION,
        product_code_snapshot=product.product_code,
        plan_code_snapshot=plan.plan_code,
        plan_name_snapshot=plan.plan_name,
        edition=plan.edition,
        license_type=plan.license_type,
        issued_at=now,
        not_before=not_before_dt,
        expires_at=expires_at_dt,
        features_snapshot=features_snapshot,
        limits_snapshot=limits_snapshot,
        key_id=key_id,
        signature_algorithm="Ed25519",
        canonical_payload_json=canonical_json_str,
        signature_b64=signature_b64,
        signed_artifact_json=envelope,
        status="ACTIVE",
        issued_by=actor.id,
        notes=notes,
    )
    return new_license


def issue_new_license(
    db: Session,
    req: LicenseIssueRequest,
    actor: User,
) -> LicenseResponse:
    customer = db.query(Customer).filter(Customer.id == req.customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    if customer.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot issue a license for an INACTIVE customer.",
        )

    plan = db.query(LicensePlan).filter(LicensePlan.id == req.plan_id).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License plan not found.")
    if plan.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot issue a license using an INACTIVE license plan.",
        )

    product = db.query(Product).filter(Product.id == plan.product_id).first()
    if not product or product.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Associated product is not found or INACTIVE.",
        )

    not_before_dt = req.not_before or datetime.now(timezone.utc)
    custom_limits_dict = req.custom_limits.model_dump() if req.custom_limits else None

    try:
        new_license = _create_signed_license_record(
            db,
            customer=customer,
            plan=plan,
            product=product,
            actor=actor,
            not_before_dt=not_before_dt,
            duration_days=req.duration_days,
            custom_limits=custom_limits_dict,
            notes=req.notes,
        )
        db.add(new_license)
        record_audit_event(
            db,
            actor=actor,
            action="LICENSE_ISSUED",
            entity_type="LICENSE",
            entity_id=new_license.id,
            outcome="SUCCESS",
            reason=f"Issued license {new_license.license_number} for customer {customer.customer_code}",
            metadata={
                "license_number": new_license.license_number,
                "customer_id": customer.id,
                "customer_code": customer.customer_code,
                "plan_code": plan.plan_code,
                "edition": plan.edition,
                "license_type": plan.license_type,
                "key_id": new_license.key_id,
            },
            commit=False,
        )
        db.commit()
        db.refresh(new_license)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database transaction failed during license issuance.",
        ) from exc

    return build_license_response(db, new_license, include_verification=True)


def renew_existing_license(
    db: Session,
    license_id: str,
    req: LicenseRenewRequest,
    actor: User,
) -> LicenseResponse:
    previous_lic = db.query(License).filter(License.id == license_id).first()
    if not previous_lic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found.")

    if previous_lic.license_type != "SUBSCRIPTION":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only SUBSCRIPTION licenses can be renewed. Use replacement for perpetual licenses.",
        )

    if previous_lic.status in ("REVOKED", "REPLACED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot renew a license in '{previous_lic.status}' status.",
        )

    customer = db.query(Customer).filter(Customer.id == previous_lic.customer_id).first()
    if not customer or customer.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer must be ACTIVE to renew a license.",
        )

    plan = db.query(LicensePlan).filter(LicensePlan.id == previous_lic.plan_id).first()
    product = db.query(Product).filter(Product.id == previous_lic.product_id).first()
    if not plan or not product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Original product or plan record not found.",
        )

    now = datetime.now(timezone.utc)
    # If previous license has not expired yet, start renewal validity from now (or keep seamless continuity)
    try:
        new_license = _create_signed_license_record(
            db,
            customer=customer,
            plan=plan,
            product=product,
            actor=actor,
            not_before_dt=now,
            duration_days=req.duration_days or plan.default_duration_days,
            custom_limits=previous_lic.limits_snapshot,
            notes=req.notes or f"Renewal of {previous_lic.license_number}",
        )
        db.add(new_license)
        db.flush()

        rel = LicenseRelationship(
            previous_license_id=previous_lic.id,
            new_license_id=new_license.id,
            relationship_type="RENEWAL",
            reason=req.reason,
            created_by=actor.id,
        )
        db.add(rel)

        record_audit_event(
            db,
            actor=actor,
            action="LICENSE_RENEWED",
            entity_type="LICENSE",
            entity_id=new_license.id,
            outcome="SUCCESS",
            reason=req.reason,
            metadata={
                "previous_license_id": previous_lic.id,
                "previous_license_number": previous_lic.license_number,
                "new_license_id": new_license.id,
                "new_license_number": new_license.license_number,
            },
            commit=False,
        )
        db.commit()
        db.refresh(new_license)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database transaction failed during license renewal.",
        ) from exc

    return build_license_response(db, new_license, include_verification=True)


def replace_existing_license(
    db: Session,
    license_id: str,
    req: LicenseReplaceRequest,
    actor: User,
) -> LicenseResponse:
    previous_lic = db.query(License).filter(License.id == license_id).first()
    if not previous_lic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found.")

    if previous_lic.status in ("REVOKED", "REPLACED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot replace a license that is already '{previous_lic.status}'.",
        )

    customer = db.query(Customer).filter(Customer.id == previous_lic.customer_id).first()
    if not customer or customer.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer must be ACTIVE to replace a license.",
        )

    target_plan_id = req.plan_id or previous_lic.plan_id
    plan = db.query(LicensePlan).filter(LicensePlan.id == target_plan_id).first()
    if not plan or plan.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target license plan not found or INACTIVE.",
        )

    product = db.query(Product).filter(Product.id == plan.product_id).first()
    if not product or product.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Associated product not found or INACTIVE.",
        )

    now = datetime.now(timezone.utc)
    custom_limits_dict = (
        req.custom_limits.model_dump()
        if req.custom_limits
        else (previous_lic.limits_snapshot if not req.plan_id else None)
    )

    try:
        new_license = _create_signed_license_record(
            db,
            customer=customer,
            plan=plan,
            product=product,
            actor=actor,
            not_before_dt=now,
            duration_days=req.duration_days,
            custom_limits=custom_limits_dict,
            notes=req.notes or f"Replacement for {previous_lic.license_number}",
        )
        db.add(new_license)

        # Mark the previous license as REPLACED without modifying its signed payload
        previous_lic.status = "REPLACED"
        previous_lic.status_reason = f"Replaced by {new_license.license_number}: {req.reason}"
        previous_lic.status_updated_at = now
        previous_lic.status_updated_by = actor.id

        db.flush()

        rel = LicenseRelationship(
            previous_license_id=previous_lic.id,
            new_license_id=new_license.id,
            relationship_type="REPLACEMENT",
            reason=req.reason,
            created_by=actor.id,
        )
        db.add(rel)

        record_audit_event(
            db,
            actor=actor,
            action="LICENSE_REPLACED",
            entity_type="LICENSE",
            entity_id=new_license.id,
            outcome="SUCCESS",
            reason=req.reason,
            metadata={
                "replaced_license_id": previous_lic.id,
                "replaced_license_number": previous_lic.license_number,
                "new_license_id": new_license.id,
                "new_license_number": new_license.license_number,
            },
            commit=False,
        )
        db.commit()
        db.refresh(new_license)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database transaction failed during license replacement.",
        ) from exc

    return build_license_response(db, new_license, include_verification=True)
