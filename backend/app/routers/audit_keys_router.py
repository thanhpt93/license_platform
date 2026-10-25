from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.audit import record_audit_event
from app.auth import get_current_user, require_roles
from app.config import settings
from app.crypto import (
    CryptoConfigurationError,
    compute_public_key_fingerprint,
    load_configured_private_key,
    load_ed25519_public_key,
)
from app.database import get_db
from app.models import AuditLog, SigningKey, User
from app.schemas import (
    AuditLogResponse,
    PaginatedAuditLogsResponse,
    SigningKeyRegisterRequest,
    SigningKeyResponse,
)

router = APIRouter(prefix="/api", tags=["Audit & Signing Keys"])


@router.get("/audit-logs", response_model=PaginatedAuditLogsResponse)
def list_audit_logs(
    search: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(AuditLog)

    if search and search.strip():
        q = f"%{search.strip()}%"
        query = query.filter(
            or_(
                AuditLog.action.ilike(q),
                AuditLog.actor_username.ilike(q),
                AuditLog.reason.ilike(q),
                AuditLog.entity_id.ilike(q),
            )
        )
    if action and action.strip():
        query = query.filter(AuditLog.action == action.strip().upper())
    if entity_type and entity_type.strip():
        query = query.filter(AuditLog.entity_type == entity_type.strip().upper())
    if outcome and outcome.strip():
        query = query.filter(AuditLog.outcome == outcome.strip().upper())

    total = query.count()
    logs = (
        query.order_by(AuditLog.timestamp.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaginatedAuditLogsResponse(
        items=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/signing-keys", response_model=List[SigningKeyResponse])
def list_signing_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    keys = db.query(SigningKey).order_by(SigningKey.created_at.desc()).all()
    return [SigningKeyResponse.model_validate(k) for k in keys]


@router.get("/signing-keys/status")
def get_signing_engine_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reports whether the server's configured private signing key is loaded and matches
    an active registered public key in the database. Never exposes private key material.
    """
    configured_key_id = settings.NOVA_ACTIVE_KEY_ID
    try:
        loaded_key_id, _ = load_configured_private_key()
        private_key_loaded = True
        load_error = None
    except CryptoConfigurationError as exc:
        loaded_key_id = configured_key_id
        private_key_loaded = False
        load_error = str(exc)

    active_db_key = (
        db.query(SigningKey)
        .filter(SigningKey.is_active.is_(True), SigningKey.status == "ACTIVE")
        .first()
    )

    ready = bool(
        private_key_loaded
        and active_db_key is not None
        and active_db_key.key_id == loaded_key_id
    )
    return {
        "signing_engine_ready": ready,
        "configured_key_id": configured_key_id,
        "private_key_loaded": private_key_loaded,
        "active_db_key_id": active_db_key.key_id if active_db_key else None,
        "active_db_key_fingerprint": active_db_key.fingerprint_sha256 if active_db_key else None,
        "status_message": (
            "Ed25519 signing engine is operational."
            if ready
            else (load_error or "Configured key ID does not match active database public key.")
        ),
    }


@router.post("/signing-keys", response_model=SigningKeyResponse, status_code=status.HTTP_201_CREATED)
def register_signing_key(
    req: SigningKeyRegisterRequest,
    current_user: User = Depends(require_roles(["SUPER_ADMIN"], "REGISTER_OR_ROTATE_SIGNING_KEY")),
    db: Session = Depends(get_db),
):
    """
    Registers a new Ed25519 public key for signature verification and optionally rotates it
    to be the active signing key while keeping historical public keys intact for verification.
    """
    existing = db.query(SigningKey).filter(SigningKey.key_id == req.key_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Signing key ID '{req.key_id}' is already registered.",
        )

    try:
        _ = load_ed25519_public_key(req.public_key_pem)
        fingerprint = compute_public_key_fingerprint(req.public_key_pem)
    except CryptoConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    now = datetime.now(timezone.utc)
    if req.set_active:
        # Retire previously active keys for new signing, but keep them ACTIVE/RETIRED for verification
        previously_active = db.query(SigningKey).filter(SigningKey.is_active.is_(True)).all()
        for old_key in previously_active:
            old_key.is_active = False
            old_key.status = "RETIRED"
            old_key.rotated_at = now

    new_key = SigningKey(
        key_id=req.key_id,
        algorithm="Ed25519",
        public_key_pem=req.public_key_pem.strip(),
        fingerprint_sha256=fingerprint,
        is_active=req.set_active,
        status="ACTIVE",
        description=req.description.strip() if req.description else None,
    )
    db.add(new_key)
    db.flush()

    record_audit_event(
        db,
        actor=current_user,
        action="SIGNING_KEY_REGISTERED" if not req.set_active else "SIGNING_KEY_ROTATED",
        entity_type="SIGNING_KEY",
        entity_id=new_key.key_id,
        outcome="SUCCESS",
        reason=f"Registered Ed25519 public key '{new_key.key_id}' (active={new_key.is_active})",
        metadata={
            "key_id": new_key.key_id,
            "fingerprint_sha256": fingerprint,
            "is_active": new_key.is_active,
        },
        commit=False,
    )
    db.commit()
    db.refresh(new_key)
    return SigningKeyResponse.model_validate(new_key)


@router.post("/signing-keys/{key_id}/activate", response_model=SigningKeyResponse)
def activate_signing_key(
    key_id: str,
    current_user: User = Depends(require_roles(["SUPER_ADMIN"], "ACTIVATE_SIGNING_KEY")),
    db: Session = Depends(get_db),
):
    target_key = db.query(SigningKey).filter(SigningKey.key_id == key_id).first()
    if not target_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signing key not found.")

    if target_key.status == "COMPROMISED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot activate a COMPROMISED signing key.",
        )

    now = datetime.now(timezone.utc)
    for k in db.query(SigningKey).filter(SigningKey.is_active.is_(True)).all():
        if k.key_id != key_id:
            k.is_active = False
            k.status = "RETIRED"
            k.rotated_at = now

    target_key.is_active = True
    target_key.status = "ACTIVE"

    record_audit_event(
        db,
        actor=current_user,
        action="SIGNING_KEY_ROTATED",
        entity_type="SIGNING_KEY",
        entity_id=target_key.key_id,
        outcome="SUCCESS",
        reason=f"Activated signing key '{target_key.key_id}'",
        metadata={"key_id": target_key.key_id, "fingerprint_sha256": target_key.fingerprint_sha256},
        commit=False,
    )
    db.commit()
    db.refresh(target_key)
    return SigningKeyResponse.model_validate(target_key)
