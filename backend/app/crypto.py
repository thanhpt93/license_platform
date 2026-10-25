import base64
import hashlib
import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from app.config import settings

ARTIFACT_FORMAT_V1 = "NOVA-LICENSE-ENVELOPE-V1"
ALGORITHM_ED25519 = "Ed25519"
PAYLOAD_SCHEMA_VERSION = "1.0"


class CryptoConfigurationError(Exception):
    """Raised when the signing key is missing, misconfigured, or invalid."""


class SignatureVerificationError(Exception):
    """Raised when a license artifact fails schema or cryptographic verification."""


def format_utc_timestamp(dt: Optional[datetime]) -> Optional[str]:
    """Formats a datetime to canonical ISO-8601 UTC string with second precision and 'Z' suffix."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc_timestamp(ts: str) -> datetime:
    """Parses an ISO-8601 UTC string ('YYYY-MM-DDTHH:MM:SSZ')."""
    if not isinstance(ts, str) or not ts.endswith("Z"):
        raise ValueError(f"Timestamp must be an ISO-8601 UTC string ending with 'Z': {ts}")
    dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    return dt.replace(tzinfo=timezone.utc)


def _normalize_canonical_value(value: Any) -> Any:
    """Recursively normalizes strings (NFC), lists, dicts, ints, and nulls for canonical JSON."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        raise ValueError("Floating-point numbers are not permitted in canonical license payloads")
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [_normalize_canonical_value(item) for item in value]
    if isinstance(value, dict):
        return {
            unicodedata.normalize("NFC", str(k)): _normalize_canonical_value(v)
            for k, v in value.items()
        }
    raise TypeError(f"Unsupported type in canonical payload: {type(value)}")


def canonicalize_payload(payload: Dict[str, Any]) -> bytes:
    """
    Produces deterministic RFC 8785 / JCS compatible UTF-8 bytes from a license payload dictionary.
    - Keys sorted lexicographically at all levels (sort_keys=True)
    - Compact separators (",", ":") with no insignificant whitespace
    - UTF-8 encoding without ASCII escaping (ensure_ascii=False)
    - Strings normalized to Unicode NFC
    """
    normalized = _normalize_canonical_value(payload)
    if "features" in normalized and isinstance(normalized["features"], list):
        normalized["features"] = sorted({str(f) for f in normalized["features"]})
    canonical_str = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return canonical_str.encode("utf-8")


def compute_public_key_fingerprint(public_key_pem: str) -> str:
    """Computes SHA-256 hex digest over the raw 32-byte Ed25519 public key."""
    pub_key = load_ed25519_public_key(public_key_pem)
    raw_bytes = pub_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return hashlib.sha256(raw_bytes).hexdigest()


def load_ed25519_public_key(public_key_pem: str) -> Ed25519PublicKey:
    try:
        key = serialization.load_pem_public_key(public_key_pem.strip().encode("utf-8"))
    except Exception as exc:
        raise CryptoConfigurationError("Invalid public key PEM format") from exc
    if not isinstance(key, Ed25519PublicKey):
        raise CryptoConfigurationError("Public key is not an Ed25519 key")
    return key


def load_configured_private_key() -> Tuple[str, Ed25519PrivateKey]:
    """
    Loads the active Ed25519 private signing key from the configured environment/file.
    Never generates a key automatically or falls back to an insecure default.
    """
    key_id = settings.NOVA_ACTIVE_KEY_ID
    if not key_id or not key_id.strip():
        raise CryptoConfigurationError(
            "No active signing key ID (NOVA_ACTIVE_KEY_ID) is configured on the server."
        )

    pem_bytes: Optional[bytes] = None
    if settings.NOVA_SIGNING_PRIVATE_KEY_PEM and settings.NOVA_SIGNING_PRIVATE_KEY_PEM.strip():
        raw_pem = settings.NOVA_SIGNING_PRIVATE_KEY_PEM.strip().replace("\\n", "\n")
        pem_bytes = raw_pem.encode("utf-8")
    elif settings.resolved_private_key_path is not None:
        key_path = settings.resolved_private_key_path
        if not key_path.is_file():
            raise CryptoConfigurationError(
                "Configured signing private key file is unavailable on the server."
            )
        pem_bytes = key_path.read_bytes()
    else:
        raise CryptoConfigurationError(
            "No signing private key source (NOVA_SIGNING_PRIVATE_KEY_PATH or NOVA_SIGNING_PRIVATE_KEY_PEM) is configured."
        )

    passphrase_bytes: Optional[bytes] = None
    if settings.NOVA_SIGNING_KEY_PASSPHRASE:
        passphrase_bytes = settings.NOVA_SIGNING_KEY_PASSPHRASE.encode("utf-8")

    try:
        private_key = serialization.load_pem_private_key(pem_bytes, password=passphrase_bytes)
    except Exception as exc:
        raise CryptoConfigurationError("Failed to load Ed25519 private signing key.") from exc

    if not isinstance(private_key, Ed25519PrivateKey):
        raise CryptoConfigurationError("Configured private signing key is not an Ed25519 key.")

    return key_id.strip(), private_key


def generate_ed25519_keypair_pem(passphrase: Optional[str] = None) -> Tuple[str, str]:
    """
    Helper for CLI key initialization / rotation scripts and isolated tests.
    Returns (private_key_pem, public_key_pem).
    """
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    encryption = (
        serialization.BestAvailableEncryption(passphrase.encode("utf-8"))
        if passphrase
        else serialization.NoEncryption()
    )
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption,
    ).decode("utf-8")

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


def validate_payload_schema(payload: Dict[str, Any]) -> None:
    """
    Validates that a license payload dictionary conforms to schema_version 1.0.
    Raises SignatureVerificationError on any violation.
    """
    if not isinstance(payload, dict):
        raise SignatureVerificationError("Payload must be a JSON object")

    required_fields = {
        "schema_version",
        "license_id",
        "license_number",
        "customer_id",
        "customer_code",
        "customer_name",
        "product_id",
        "edition",
        "license_type",
        "issued_at",
        "not_before",
        "expires_at",
        "features",
        "limits",
        "key_id",
    }
    missing = required_fields - set(payload.keys())
    if missing:
        raise SignatureVerificationError(f"Payload is missing required fields: {sorted(missing)}")

    if payload.get("schema_version") != PAYLOAD_SCHEMA_VERSION:
        raise SignatureVerificationError(
            f"Unsupported payload schema_version: {payload.get('schema_version')}"
        )

    for str_field in (
        "license_id",
        "license_number",
        "customer_id",
        "customer_code",
        "customer_name",
        "product_id",
        "edition",
        "license_type",
        "key_id",
    ):
        val = payload.get(str_field)
        if not isinstance(val, str) or not val.strip():
            raise SignatureVerificationError(f"Field '{str_field}' must be a non-empty string")

    if payload["edition"] not in ("developer", "production"):
        raise SignatureVerificationError(f"Unsupported edition: {payload['edition']}")

    license_type = payload["license_type"]
    if license_type not in ("SUBSCRIPTION", "PERPETUAL"):
        raise SignatureVerificationError(f"Unsupported license_type: {license_type}")

    try:
        _ = parse_utc_timestamp(payload["issued_at"])
        not_before_dt = parse_utc_timestamp(payload["not_before"])
    except Exception as exc:
        raise SignatureVerificationError(f"Invalid timestamp in payload: {exc}") from exc

    expires_at_val = payload.get("expires_at")
    if license_type == "SUBSCRIPTION":
        if expires_at_val is None:
            raise SignatureVerificationError("SUBSCRIPTION license must have a non-null expires_at")
        try:
            expires_at_dt = parse_utc_timestamp(expires_at_val)
        except Exception as exc:
            raise SignatureVerificationError(f"Invalid expires_at timestamp: {exc}") from exc
        if expires_at_dt <= not_before_dt:
            raise SignatureVerificationError("expires_at must be strictly after not_before")
    elif license_type == "PERPETUAL":
        if expires_at_val is not None:
            raise SignatureVerificationError("PERPETUAL license must have expires_at set to null")

    features = payload.get("features")
    if not isinstance(features, list) or not all(isinstance(f, str) and f.strip() for f in features):
        raise SignatureVerificationError("Field 'features' must be a list of non-empty strings")

    limits = payload.get("limits")
    if not isinstance(limits, dict):
        raise SignatureVerificationError("Field 'limits' must be an object")

    for limit_key in ("max_devices", "max_concurrent_inspections", "total_inspection_quota"):
        if limit_key not in limits:
            raise SignatureVerificationError(f"Missing limit field '{limit_key}'")
        limit_val = limits[limit_key]
        if isinstance(limit_val, bool) or not isinstance(limit_val, int) or limit_val < -1:
            raise SignatureVerificationError(
                f"Invalid limit value for '{limit_key}': must be integer >= -1"
            )


def sign_license_payload(
    payload: Dict[str, Any],
    private_key: Ed25519PrivateKey,
    key_id: str,
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Validates, canonicalizes, and signs a license payload.
    Returns (canonical_json_str, signature_b64, envelope_dict).
    """
    if payload.get("key_id") != key_id:
        raise CryptoConfigurationError("Payload key_id does not match signing key_id")

    validate_payload_schema(payload)
    canonical_bytes = canonicalize_payload(payload)
    canonical_json_str = canonical_bytes.decode("utf-8")

    signature_bytes = private_key.sign(canonical_bytes)
    signature_b64 = base64.b64encode(signature_bytes).decode("ascii")

    # Re-parse canonical JSON so the envelope's payload object has normalized features & fields
    normalized_payload = json.loads(canonical_json_str)

    envelope = {
        "artifact_format": ARTIFACT_FORMAT_V1,
        "algorithm": ALGORITHM_ED25519,
        "key_id": key_id,
        "payload": normalized_payload,
        "signature": signature_b64,
    }
    return canonical_json_str, signature_b64, envelope


def verify_license_envelope(
    envelope: Dict[str, Any],
    public_key_pem: str,
) -> Dict[str, Any]:
    """
    Verifies a license artifact envelope against the specified Ed25519 public key PEM.
    1. Checks envelope format, algorithm, and key_id consistency.
    2. Validates the payload schema.
    3. Reconstructs canonical UTF-8 payload bytes.
    4. Verifies the Ed25519 digital signature.
    Returns the validated payload dict if valid, or raises SignatureVerificationError.
    """
    if not isinstance(envelope, dict):
        raise SignatureVerificationError("License artifact must be a JSON object")

    if envelope.get("artifact_format") != ARTIFACT_FORMAT_V1:
        raise SignatureVerificationError(
            f"Unsupported artifact_format: {envelope.get('artifact_format')}"
        )

    algorithm = envelope.get("algorithm")
    if algorithm != ALGORITHM_ED25519:
        raise SignatureVerificationError(f"Unsupported signature algorithm: {algorithm}")

    key_id = envelope.get("key_id")
    if not isinstance(key_id, str) or not key_id.strip():
        raise SignatureVerificationError("Missing or invalid key_id in artifact envelope")

    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise SignatureVerificationError("Missing or invalid payload in artifact envelope")

    if payload.get("key_id") != key_id:
        raise SignatureVerificationError(
            "Envelope key_id does not match signed payload key_id"
        )

    signature_b64 = envelope.get("signature")
    if not isinstance(signature_b64, str) or not signature_b64.strip():
        raise SignatureVerificationError("Missing or invalid signature in artifact envelope")

    validate_payload_schema(payload)

    try:
        signature_bytes = base64.b64decode(signature_b64, validate=True)
    except Exception as exc:
        raise SignatureVerificationError("Signature is not valid Base64") from exc

    if len(signature_bytes) != 64:
        raise SignatureVerificationError("Ed25519 signature must be exactly 64 bytes")

    canonical_bytes = canonicalize_payload(payload)
    public_key = load_ed25519_public_key(public_key_pem)

    try:
        public_key.verify(signature_bytes, canonical_bytes)
    except InvalidSignature as exc:
        raise SignatureVerificationError("Cryptographic signature verification failed") from exc

    return payload
