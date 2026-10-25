from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from app.models import AuditLog, User

FORBIDDEN_METADATA_KEYS = {
    "password",
    "password_hash",
    "private_key",
    "private_key_pem",
    "passphrase",
    "secret",
    "token",
    "access_token",
    "authorization",
}


def sanitize_metadata(metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Strips any sensitive keys recursively before persisting audit metadata."""
    if metadata is None:
        return None
    cleaned: Dict[str, Any] = {}
    for k, v in metadata.items():
        key_lower = str(k).lower()
        if any(forbidden in key_lower for forbidden in FORBIDDEN_METADATA_KEYS):
            continue
        if isinstance(v, dict):
            cleaned[k] = sanitize_metadata(v)
        else:
            cleaned[k] = v
    return cleaned


def record_audit_event(
    db: Session,
    *,
    actor: Optional[User],
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    outcome: str = "SUCCESS",
    reason: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    actor_username_override: Optional[str] = None,
    commit: bool = False,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_username=actor.username if actor else actor_username_override,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        outcome=outcome,
        reason=reason,
        metadata_json=sanitize_metadata(metadata),
    )
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    return entry
