from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.crypto import CryptoConfigurationError, load_configured_private_key
from app.database import get_db
from app.models import AuditLog, Customer, License, SigningKey, User
from app.schemas import AuditLogResponse, DashboardSummaryResponse
from app.services.license_service import build_license_response, compute_effective_status

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    period_days: int = Query(30, ge=1, le=365, description="Period in days for issued licenses count"),
    expiring_within_days: int = Query(30, ge=1, le=180, description="Threshold in days for expiring soon"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    period_cutoff = now - timedelta(days=period_days)
    expiring_cutoff = now + timedelta(days=expiring_within_days)

    total_customers = db.query(func.count(Customer.id)).scalar() or 0
    active_customers = (
        db.query(func.count(Customer.id)).filter(Customer.status == "ACTIVE").scalar() or 0
    )

    all_licenses = db.query(License).order_by(License.issued_at.desc()).all()

    active_count = 0
    expired_count = 0
    revoked_or_suspended_count = 0
    expiring_soon_records = []
    issued_in_period_count = 0

    for lic in all_licenses:
        eff = compute_effective_status(lic, now)
        issued_utc = (
            lic.issued_at.replace(tzinfo=timezone.utc)
            if lic.issued_at.tzinfo is None
            else lic.issued_at.astimezone(timezone.utc)
        )
        if issued_utc >= period_cutoff:
            issued_in_period_count += 1

        if eff == "ACTIVE":
            active_count += 1
            if lic.license_type == "SUBSCRIPTION" and lic.expires_at is not None:
                exp_utc = (
                    lic.expires_at.replace(tzinfo=timezone.utc)
                    if lic.expires_at.tzinfo is None
                    else lic.expires_at.astimezone(timezone.utc)
                )
                if now < exp_utc <= expiring_cutoff:
                    expiring_soon_records.append(lic)
        elif eff == "EXPIRED":
            expired_count += 1
        elif eff in ("REVOKED", "SUSPENDED"):
            revoked_or_suspended_count += 1

    expiring_soon_records.sort(
        key=lambda x: (
            x.expires_at.replace(tzinfo=timezone.utc)
            if x.expires_at and x.expires_at.tzinfo is None
            else (x.expires_at or now)
        )
    )

    recent_licenses = [
        build_license_response(db, lic, include_verification=False)
        for lic in all_licenses[:8]
    ]
    expiring_soon_list = [
        build_license_response(db, lic, include_verification=False)
        for lic in expiring_soon_records[:8]
    ]

    recent_logs = (
        db.query(AuditLog)
        .order_by(AuditLog.timestamp.desc())
        .limit(10)
        .all()
    )

    # Check signing engine readiness
    try:
        loaded_key_id, _ = load_configured_private_key()
        active_key = (
            db.query(SigningKey)
            .filter(
                SigningKey.key_id == loaded_key_id,
                SigningKey.is_active.is_(True),
                SigningKey.status == "ACTIVE",
            )
            .first()
        )
        signing_ready = active_key is not None
        active_key_id = active_key.key_id if active_key else loaded_key_id
    except CryptoConfigurationError:
        signing_ready = False
        active_key_id = None

    return DashboardSummaryResponse(
        total_customers=total_customers,
        active_customers=active_customers,
        active_licenses=active_count,
        expiring_soon_licenses=len(expiring_soon_records),
        expired_licenses=expired_count,
        revoked_or_suspended_licenses=revoked_or_suspended_count,
        issued_in_period=issued_in_period_count,
        period_days=period_days,
        recent_licenses=recent_licenses,
        expiring_soon_list=expiring_soon_list,
        recent_audit_logs=[AuditLogResponse.model_validate(log) for log in recent_logs],
        signing_engine_ready=signing_ready,
        active_key_id=active_key_id,
    )
