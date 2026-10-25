import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.audit import record_audit_event
from app.auth import get_current_user, require_roles
from app.crypto import SignatureVerificationError, verify_license_envelope
from app.database import get_db
from app.models import Customer, License, SigningKey, User
from app.schemas import (
    LicenseIssueRequest,
    LicenseRenewRequest,
    LicenseReplaceRequest,
    LicenseResponse,
    LicenseStatusActionRequest,
    PaginatedLicensesResponse,
    VerifyArtifactRequest,
    VerifyArtifactResponse,
)
from app.services.license_service import (
    build_license_response,
    compute_effective_status,
    issue_new_license,
    renew_existing_license,
    replace_existing_license,
)

router = APIRouter(prefix="/api/licenses", tags=["Licenses"])


@router.get("", response_model=PaginatedLicensesResponse)
def list_licenses(
    search: Optional[str] = Query(None, description="Search by license number, customer code, or company name"),
    status_filter: Optional[str] = Query(None, alias="status"),
    edition: Optional[str] = Query(None),
    license_type: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(License).join(Customer, License.customer_id == Customer.id)

    if search and search.strip():
        q = f"%{search.strip()}%"
        query = query.filter(
            or_(
                License.license_number.ilike(q),
                Customer.customer_code.ilike(q),
                Customer.company_name.ilike(q),
                License.plan_code_snapshot.ilike(q),
            )
        )

    if customer_id:
        query = query.filter(License.customer_id == customer_id)
    if edition:
        query = query.filter(License.edition == edition)
    if license_type:
        query = query.filter(License.license_type == license_type.upper())

    all_matching = query.order_by(License.issued_at.desc()).all()

    now = datetime.now(timezone.utc)
    if status_filter and status_filter.strip():
        desired = status_filter.strip().upper()
        filtered = [lic for lic in all_matching if compute_effective_status(lic, now) == desired]
    else:
        filtered = all_matching

    total = len(filtered)
    start = (page - 1) * page_size
    paginated = filtered[start : start + page_size]

    return PaginatedLicensesResponse(
        items=[build_license_response(db, lic, include_verification=False) for lic in paginated],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=LicenseResponse, status_code=status.HTTP_201_CREATED)
def create_license(
    req: LicenseIssueRequest,
    current_user: User = Depends(require_roles(["SUPER_ADMIN", "LICENSE_ADMIN"], "ISSUE_LICENSE")),
    db: Session = Depends(get_db),
):
    return issue_new_license(db, req, current_user)


@router.post("/verify-artifact", response_model=VerifyArtifactResponse)
def verify_standalone_artifact(
    req: VerifyArtifactRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Verifies any uploaded or submitted signed license artifact JSON against registered public keys.
    """
    now = datetime.now(timezone.utc)
    envelope = req.artifact
    if not envelope or not isinstance(envelope, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid JSON artifact object must be provided.",
        )

    key_id = envelope.get("key_id")
    if not key_id or not isinstance(key_id, str):
        record_audit_event(
            db,
            actor=current_user,
            action="LICENSE_VERIFY_FAILED",
            entity_type="LICENSE",
            outcome="FAILURE",
            reason="Missing key_id in submitted artifact",
            commit=True,
        )
        return VerifyArtifactResponse(
            valid=False,
            reason="Missing or invalid key_id in artifact envelope",
            verified_at=now,
        )

    signing_key = db.query(SigningKey).filter(SigningKey.key_id == key_id).first()
    if not signing_key:
        record_audit_event(
            db,
            actor=current_user,
            action="LICENSE_VERIFY_FAILED",
            entity_type="LICENSE",
            outcome="FAILURE",
            reason=f"Unknown key_id: {key_id}",
            commit=True,
        )
        return VerifyArtifactResponse(
            valid=False,
            key_id=key_id,
            reason=f"Unknown signing key ID: {key_id}",
            verified_at=now,
        )

    if signing_key.status == "COMPROMISED":
        return VerifyArtifactResponse(
            valid=False,
            key_id=key_id,
            reason=f"Signing key '{key_id}' has been marked COMPROMISED",
            verified_at=now,
        )

    try:
        payload = verify_license_envelope(envelope, signing_key.public_key_pem)
    except SignatureVerificationError as exc:
        record_audit_event(
            db,
            actor=current_user,
            action="LICENSE_VERIFY_FAILED",
            entity_type="LICENSE",
            entity_id=envelope.get("payload", {}).get("license_id") if isinstance(envelope.get("payload"), dict) else None,
            outcome="FAILURE",
            reason=str(exc),
            commit=True,
        )
        return VerifyArtifactResponse(
            valid=False,
            key_id=key_id,
            algorithm=envelope.get("algorithm"),
            reason=str(exc),
            verified_at=now,
        )

    lic_id = payload.get("license_id")
    lic_record = db.query(License).filter(License.id == lic_id).first() if lic_id else None
    eff_status = compute_effective_status(lic_record, now) if lic_record else "EXTERNAL_VALID"

    record_audit_event(
        db,
        actor=current_user,
        action="LICENSE_VERIFIED",
        entity_type="LICENSE",
        entity_id=lic_id,
        outcome="SUCCESS",
        reason=f"Verified signature for license {payload.get('license_number')}",
        metadata={"key_id": key_id, "license_number": payload.get("license_number")},
        commit=True,
    )
    return VerifyArtifactResponse(
        valid=True,
        license_id=lic_id,
        license_number=payload.get("license_number"),
        key_id=key_id,
        algorithm=envelope.get("algorithm"),
        effective_status=eff_status,
        reason="Cryptographic signature and canonical payload verified successfully.",
        verified_at=now,
    )


@router.get("/{license_id}", response_model=LicenseResponse)
def get_license(
    license_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lic = db.query(License).filter(License.id == license_id).first()
    if not lic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found.")
    return build_license_response(db, lic, include_verification=True)


@router.post("/{license_id}/verify", response_model=VerifyArtifactResponse)
def verify_stored_license(
    license_id: str,
    req: Optional[VerifyArtifactRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    lic = db.query(License).filter(License.id == license_id).first()
    if not lic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found.")

    envelope = (req.artifact if req and req.artifact else None) or lic.signed_artifact_json
    if not envelope or not isinstance(envelope, dict):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored license artifact is missing or malformed.",
        )

    key_id = envelope.get("key_id")
    signing_key = db.query(SigningKey).filter(SigningKey.key_id == key_id).first()
    if not signing_key:
        record_audit_event(
            db,
            actor=current_user,
            action="LICENSE_VERIFY_FAILED",
            entity_type="LICENSE",
            entity_id=lic.id,
            outcome="FAILURE",
            reason=f"Signing key '{key_id}' not found",
            commit=True,
        )
        return VerifyArtifactResponse(
            valid=False,
            license_id=lic.id,
            license_number=lic.license_number,
            key_id=key_id,
            reason=f"Unknown signing key ID: {key_id}",
            verified_at=now,
        )

    try:
        payload = verify_license_envelope(envelope, signing_key.public_key_pem)
    except SignatureVerificationError as exc:
        record_audit_event(
            db,
            actor=current_user,
            action="LICENSE_VERIFY_FAILED",
            entity_type="LICENSE",
            entity_id=lic.id,
            outcome="FAILURE",
            reason=str(exc),
            commit=True,
        )
        return VerifyArtifactResponse(
            valid=False,
            license_id=lic.id,
            license_number=lic.license_number,
            key_id=key_id,
            algorithm=envelope.get("algorithm"),
            effective_status=compute_effective_status(lic, now),
            reason=str(exc),
            verified_at=now,
        )

    record_audit_event(
        db,
        actor=current_user,
        action="LICENSE_VERIFIED",
        entity_type="LICENSE",
        entity_id=lic.id,
        outcome="SUCCESS",
        reason=f"Verified signature for license {lic.license_number}",
        metadata={"key_id": key_id, "license_number": lic.license_number},
        commit=True,
    )
    return VerifyArtifactResponse(
        valid=True,
        license_id=lic.id,
        license_number=payload.get("license_number"),
        key_id=key_id,
        algorithm=envelope.get("algorithm"),
        effective_status=compute_effective_status(lic, now),
        reason="Cryptographic signature and canonical payload verified successfully.",
        verified_at=now,
    )


@router.post("/{license_id}/renew", response_model=LicenseResponse, status_code=status.HTTP_201_CREATED)
def renew_license(
    license_id: str,
    req: LicenseRenewRequest,
    current_user: User = Depends(require_roles(["SUPER_ADMIN", "LICENSE_ADMIN"], "RENEW_LICENSE")),
    db: Session = Depends(get_db),
):
    return renew_existing_license(db, license_id, req, current_user)


@router.post("/{license_id}/replace", response_model=LicenseResponse, status_code=status.HTTP_201_CREATED)
def replace_license(
    license_id: str,
    req: LicenseReplaceRequest,
    current_user: User = Depends(require_roles(["SUPER_ADMIN", "LICENSE_ADMIN"], "REPLACE_LICENSE")),
    db: Session = Depends(get_db),
):
    return replace_existing_license(db, license_id, req, current_user)


@router.post("/{license_id}/suspend", response_model=LicenseResponse)
def suspend_license(
    license_id: str,
    req: LicenseStatusActionRequest,
    current_user: User = Depends(require_roles(["SUPER_ADMIN", "LICENSE_ADMIN"], "SUSPEND_LICENSE")),
    db: Session = Depends(get_db),
):
    lic = db.query(License).filter(License.id == license_id).first()
    if not lic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found.")

    if lic.status in ("REVOKED", "REPLACED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot suspend a license that is already {lic.status}.",
        )
    if lic.status == "SUSPENDED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="License is already SUSPENDED.",
        )

    now = datetime.now(timezone.utc)
    lic.status = "SUSPENDED"
    lic.status_reason = req.reason.strip()
    lic.status_updated_at = now
    lic.status_updated_by = current_user.id

    record_audit_event(
        db,
        actor=current_user,
        action="LICENSE_SUSPENDED",
        entity_type="LICENSE",
        entity_id=lic.id,
        outcome="SUCCESS",
        reason=req.reason.strip(),
        metadata={"license_number": lic.license_number},
        commit=False,
    )
    db.commit()
    db.refresh(lic)
    return build_license_response(db, lic, include_verification=True)


@router.post("/{license_id}/revoke", response_model=LicenseResponse)
def revoke_license(
    license_id: str,
    req: LicenseStatusActionRequest,
    current_user: User = Depends(require_roles(["SUPER_ADMIN", "LICENSE_ADMIN"], "REVOKE_LICENSE")),
    db: Session = Depends(get_db),
):
    lic = db.query(License).filter(License.id == license_id).first()
    if not lic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found.")

    if lic.status == "REVOKED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="License is already REVOKED.",
        )

    now = datetime.now(timezone.utc)
    lic.status = "REVOKED"
    lic.status_reason = req.reason.strip()
    lic.status_updated_at = now
    lic.status_updated_by = current_user.id

    record_audit_event(
        db,
        actor=current_user,
        action="LICENSE_REVOKED",
        entity_type="LICENSE",
        entity_id=lic.id,
        outcome="SUCCESS",
        reason=req.reason.strip(),
        metadata={"license_number": lic.license_number},
        commit=False,
    )
    db.commit()
    db.refresh(lic)
    return build_license_response(db, lic, include_verification=True)


@router.get("/{license_id}/download")
def download_license_artifact(
    license_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lic = db.query(License).filter(License.id == license_id).first()
    if not lic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found.")

    if not lic.signed_artifact_json or not isinstance(lic.signed_artifact_json, dict):
        record_audit_event(
            db,
            actor=current_user,
            action="LICENSE_DOWNLOAD_FAILED",
            entity_type="LICENSE",
            entity_id=lic.id,
            outcome="FAILURE",
            reason="Signed artifact JSON is missing on license record",
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Signed license artifact is missing or unavailable.",
        )

    # Ensure no private key material could ever exist in the downloaded artifact
    artifact_copy = dict(lic.signed_artifact_json)
    artifact_copy.pop("private_key", None)

    record_audit_event(
        db,
        actor=current_user,
        action="LICENSE_DOWNLOADED",
        entity_type="LICENSE",
        entity_id=lic.id,
        outcome="SUCCESS",
        reason=f"Downloaded signed artifact for {lic.license_number}",
        metadata={"license_number": lic.license_number, "key_id": lic.key_id},
        commit=True,
    )

    filename = f"{lic.license_number}.novalic.json"
    content_bytes = json.dumps(artifact_copy, indent=2, ensure_ascii=False).encode("utf-8")
    return Response(
        content=content_bytes,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
