# NOVA License Artifact & Cryptographic Specification (v1.0)

## 1. Overview
This specification defines the canonical format, digital signature envelope, entitlement semantics, and verification procedure for **NOVA Machine Vision Platform** license files (`.novalic` / JSON).

Future components—specifically the **NOVA License Validator** embedded in NOVA Machine Vision Platform—must implement verification according to this specification without altering or reinterpreting the schema.

---

## 2. Signature Envelope Format

A downloaded NOVA license artifact is a UTF-8 encoded JSON document with the following top-level structure:

```json
{
  "artifact_format": "NOVA-LICENSE-ENVELOPE-V1",
  "algorithm": "Ed25519",
  "key_id": "nova-key-2026-01",
  "payload": {
    "schema_version": "1.0",
    "license_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "license_number": "NOVA-2026-000001",
    "customer_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "customer_code": "CUST-ACME-01",
    "customer_name": "Acme Vision Automation Ltd.",
    "product_id": "NOVA-MVP",
    "edition": "production",
    "license_type": "SUBSCRIPTION",
    "issued_at": "2026-10-25T15:00:00Z",
    "not_before": "2026-10-25T15:00:00Z",
    "expires_at": "2027-10-25T15:00:00Z",
    "features": [
      "*",
      "anomaly_detection",
      "barcode_reader",
      "blob_analysis",
      "camera_calibration",
      "contour_detection",
      "deep_learning_ocr",
      "ethercat_trigger_bridge",
      "high_speed_acquisition",
      "measurement_metrology",
      "mqtt_publisher",
      "multi_camera_sync",
      "offline_simulator",
      "pipeline_studio",
      "plc_modbus_profinet",
      "qr_reader",
      "shape_analysis",
      "spc_telemetry_export",
      "surface_defect_detection",
      "tcp_ip_stream",
      "template_matching"
    ],
    "limits": {
      "max_devices": 2,
      "max_concurrent_inspections": 4,
      "total_inspection_quota": -1
    },
    "key_id": "nova-key-2026-01"
  },
  "signature": "base64url-or-standard-base64-encoded-64-byte-ed25519-signature"
}
```

### Envelope Fields
| Field | Type | Required | Description |
|---|---|---|---|
| `artifact_format` | `string` | Yes | Constant `"NOVA-LICENSE-ENVELOPE-V1"`. |
| `algorithm` | `string` | Yes | Constant `"Ed25519"`. |
| `key_id` | `string` | Yes | Unique identifier of the signing key pair. Must match `payload.key_id`. |
| `payload` | `object` | Yes | The structured license payload object (see Section 3). |
| `signature` | `string` | Yes | Standard Base64 (RFC 4648) encoded 64-byte Ed25519 signature over the canonicalized `payload` bytes. |

> **Security Invariant:** The private key is never included in the envelope, API responses, or client distributions.

---

## 3. License Payload Schema (`schema_version = "1.0"`)

| Field | Type | Nullable | Description |
|---|---|---|---|
| `schema_version` | `string` | No | Version of the payload schema. Must be `"1.0"`. |
| `license_id` | `string` (UUIDv4) | No | Globally unique immutable identifier for this issued license. |
| `license_number` | `string` | No | Human-readable unique license number (e.g., `NOVA-2026-000001`). |
| `customer_id` | `string` (UUIDv4) | No | Internal immutable customer identifier. |
| `customer_code` | `string` | No | Unique customer code at the time of issuance. |
| `customer_name` | `string` | No | Legal company name of the licensed customer at issuance. |
| `product_id` | `string` | No | Product code (e.g., `"NOVA-MVP"`). |
| `edition` | `string` | No | `"developer"` or `"production"`. |
| `license_type` | `string` | No | `"SUBSCRIPTION"` or `"PERPETUAL"`. |
| `issued_at` | `string` (ISO-8601 UTC) | No | Exact UTC timestamp when the license was signed (`YYYY-MM-DDTHH:MM:SSZ`). |
| `not_before` | `string` (ISO-8601 UTC) | No | UTC timestamp from which the license becomes valid (`YYYY-MM-DDTHH:MM:SSZ`). |
| `expires_at` | `string` (ISO-8601 UTC) \| `null` | Yes | UTC timestamp when the license expires. Required for `SUBSCRIPTION`; `null` for `PERPETUAL`. |
| `features` | `array<string>` | No | Lexicographically sorted array of enabled feature identifiers (deduplicated, lowercase ASCII/underscore). |
| `limits` | `object` | No | Dictionary of quantitative limits (see Section 4). |
| `key_id` | `string` | No | Identifier of the signing key used to sign this payload. |

---

## 4. Explicit Entitlement & Limit Semantics

### 4.1 Licensing Models (`license_type`)
1. **`SUBSCRIPTION`**:
   - Must have a non-null `expires_at` timestamp where `expires_at > not_before`.
   - Valid when `not_before <= current_utc_time < expires_at`.
2. **`PERPETUAL`**:
   - `expires_at` is `null`.
   - Never expires based on time (`not_before <= current_utc_time`).
   - **Important:** A null `expires_at` on a `PERPETUAL` license must **never** be interpreted as expired.

### 4.2 Limit Value Semantics (`limits`)
To avoid ambiguous zero semantics, all numeric limits in `limits` (`max_devices`, `max_concurrent_inspections`, `total_inspection_quota`) follow strict integer rules:
- **`-1`**: **Unlimited** (no cap enforced).
- **`0`**: **Disabled / Unavailable** (zero capacity; the capability is explicitly disallowed).
- **`> 0` (Positive Integer)**: **Exact Maximum Cap** enforced by the runtime.

Negative integers other than `-1` and floating-point numbers are invalid and rejected by validation.

### 4.3 Feature Entitlement Semantics (Default All-Features Access)
In the current phase, creating a license or commercial plan defaults to granting access to **all software features** across the platform:
- The signed `features` array includes the universal wildcard `"*"` alongside the full canonical list of platform modules (`anomaly_detection`, `barcode_reader`, `blob_analysis`, `camera_calibration`, `contour_detection`, `deep_learning_ocr`, `ethercat_trigger_bridge`, `high_speed_acquisition`, `measurement_metrology`, `mqtt_publisher`, `multi_camera_sync`, `offline_simulator`, `pipeline_studio`, `plc_modbus_profinet`, `qr_reader`, `shape_analysis`, `spc_telemetry_export`, `surface_defect_detection`, `tcp_ip_stream`, `template_matching`).
- Downstream software verifiers can evaluate either `if "*" in features` or test for a specific module ID (`if feature_id in features`), both of which evaluate to authorized access.
- If a restricted subset of features is explicitly specified for custom plans, only the chosen features are signed into the license snapshot.

---

## 5. Canonical Serialization Rules (RFC 8785 / JCS Compatible)

Before signing or verifying, the `payload` object is converted into canonical UTF-8 bytes using deterministic JSON serialization:

1. **Character Encoding**: UTF-8 without BOM.
2. **Object Key Ordering**: All JSON object keys at every nesting level are sorted lexicographically by Unicode code point (`sort_keys=True`).
3. **Whitespace**: Zero insignificant whitespace. Key-value separator is `":"` and item separator is `","` (`separators=(",", ":")`).
4. **Timestamps**: All timestamps (`issued_at`, `not_before`, `expires_at`) are normalized to UTC second precision with a trailing `"Z"` suffix (`YYYY-MM-DDTHH:MM:SSZ`).
5. **Arrays**: The `features` list is deduplicated and sorted lexicographically before serialization.
6. **Null Handling**: `null` values (such as `expires_at: null` for perpetual licenses) are explicitly preserved as the JSON literal `null`—never omitted.
7. **Numbers**: All limit values are serialized as base-10 integers without leading zeros, decimal points, or exponents.
8. **String Escaping**: Standard JSON string escaping with `ensure_ascii=False` over NFC-normalized UTF-8 strings.

---

## 6. Verification Algorithm

Any verifier (both the License Administration Server and the future NOVA Runtime Validator) must execute these exact steps:

1. **Envelope Integrity Check**:
   - Confirm `artifact_format == "NOVA-LICENSE-ENVELOPE-V1"`.
   - Confirm `algorithm == "Ed25519"`.
   - Confirm `key_id` is non-empty and matches `payload.key_id`.
2. **Schema Validation**:
   - Validate `payload` against the v1.0 schema rules (required fields, valid UUIDs, valid ISO-8601 UTC timestamps, valid limit integers `>= -1`).
   - If `license_type == "SUBSCRIPTION"`, verify `expires_at` is present and `expires_at > not_before`.
   - If `license_type == "PERPETUAL"`, verify `expires_at is None`.
3. **Key Lookup**:
   - Retrieve the trusted Ed25519 public key corresponding to `key_id`.
   - Note: Even if a key has been rotated out of active signing (`is_active = False`), its public key remains valid for verifying historical licenses unless explicitly compromised/revoked.
4. **Canonical Byte Reconstruction**:
   - Serialize `payload` using the Canonical Serialization Rules in Section 5 to obtain `canonical_bytes`.
5. **Cryptographic Signature Verification**:
   - Base64-decode `signature` into 64 raw bytes.
   - Verify `Ed25519PublicKey.verify(signature_bytes, canonical_bytes)`.
   - If any byte of `payload` or `signature` was modified, verification fails immediately.
