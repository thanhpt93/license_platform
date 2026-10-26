from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.features import ALL_SOFTWARE_FEATURES, get_default_features


# --- Auth & Users ---

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    user: UserResponse


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=8, max_length=128)
    role: Literal["SUPER_ADMIN", "LICENSE_ADMIN", "AUDITOR"] = "LICENSE_ADMIN"


# --- Customers ---

class CustomerCreateRequest(BaseModel):
    customer_code: str = Field(..., min_length=2, max_length=64, pattern=r"^[A-Z0-9_-]+$")
    company_name: str = Field(..., min_length=2, max_length=255)
    contact_person: str = Field(..., min_length=2, max_length=128)
    contact_email: EmailStr
    contact_phone: Optional[str] = Field(None, max_length=64)
    country_region: Optional[str] = Field(None, max_length=128)
    address: Optional[str] = Field(None, max_length=1000)
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("customer_code", mode="before")
    @classmethod
    def normalize_code(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().upper()
        return v


class CustomerUpdateRequest(BaseModel):
    company_name: Optional[str] = Field(None, min_length=2, max_length=255)
    contact_person: Optional[str] = Field(None, min_length=2, max_length=128)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=64)
    country_region: Optional[str] = Field(None, max_length=128)
    address: Optional[str] = Field(None, max_length=1000)
    notes: Optional[str] = Field(None, max_length=2000)
    status: Optional[Literal["ACTIVE", "INACTIVE"]] = None


class CustomerDeactivateRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_code: str
    company_name: str
    contact_person: str
    contact_email: str
    contact_phone: Optional[str]
    country_region: Optional[str]
    address: Optional[str]
    notes: Optional[str]
    status: str
    issued_licenses_count: int = 0
    created_at: datetime
    updated_at: datetime


class PaginatedCustomersResponse(BaseModel):
    items: List[CustomerResponse]
    total: int
    page: int
    page_size: int


# --- Products & License Plans ---

class ProductCreateRequest(BaseModel):
    product_code: str = Field(..., min_length=2, max_length=64, pattern=r"^[A-Z0-9_-]+$")
    product_name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    supported_editions: List[str] = Field(default_factory=lambda: ["developer", "production"], min_length=1)

    @field_validator("product_code", mode="before")
    @classmethod
    def normalize_product_code(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().upper()
        return v


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_code: str
    product_name: str
    description: Optional[str]
    supported_editions: List[str]
    status: str
    created_at: datetime
    updated_at: datetime


def validate_limit_integer(val: int, field_name: str) -> int:
    if isinstance(val, bool) or not isinstance(val, int):
        raise ValueError(f"{field_name} must be an integer")
    if val < -1:
        raise ValueError(
            f"{field_name} must be -1 (unlimited), 0 (disabled/unavailable), or a positive integer (>0)"
        )
    return val


class LicensePlanCreateRequest(BaseModel):
    plan_code: str = Field(..., min_length=2, max_length=64, pattern=r"^[A-Z0-9_-]+$")
    plan_name: str = Field(..., min_length=2, max_length=255)
    product_id: str = Field(..., min_length=1)
    edition: Literal["developer", "production"]
    description: Optional[str] = Field(None, max_length=2000)
    license_type: Literal["SUBSCRIPTION", "PERPETUAL"]
    default_duration_days: Optional[int] = Field(None)
    features: List[str] = Field(default_factory=get_default_features)
    max_devices: int = Field(default=1)
    max_concurrent_inspections: int = Field(default=1)
    total_inspection_quota: int = Field(default=-1)
    allow_custom_duration: bool = True
    allow_custom_limits: bool = True
    status: Literal["ACTIVE", "INACTIVE"] = "ACTIVE"

    @field_validator("plan_code", mode="before")
    @classmethod
    def normalize_plan_code(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip().upper()
        return v

    @field_validator("max_devices")
    @classmethod
    def check_max_devices(cls, v: int) -> int:
        return validate_limit_integer(v, "max_devices")

    @field_validator("max_concurrent_inspections")
    @classmethod
    def check_max_concurrent_inspections(cls, v: int) -> int:
        return validate_limit_integer(v, "max_concurrent_inspections")

    @field_validator("total_inspection_quota")
    @classmethod
    def check_total_inspection_quota(cls, v: int) -> int:
        return validate_limit_integer(v, "total_inspection_quota")

    @field_validator("features")
    @classmethod
    def normalize_features(cls, v: List[str]) -> List[str]:
        if not v or "*" in v or "all" in [str(f).lower() for f in v]:
            return list(ALL_SOFTWARE_FEATURES)
        cleaned = sorted({f.strip() for f in v if f and f.strip()})
        return cleaned or list(ALL_SOFTWARE_FEATURES)

    @model_validator(mode="after")
    def check_duration_by_type(self) -> "LicensePlanCreateRequest":
        if self.license_type == "SUBSCRIPTION":
            if self.default_duration_days is None or self.default_duration_days <= 0:
                raise ValueError("SUBSCRIPTION plans must specify a positive default_duration_days (> 0)")
        elif self.license_type == "PERPETUAL":
            self.default_duration_days = None
        return self


class LicensePlanUpdateRequest(BaseModel):
    plan_name: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    default_duration_days: Optional[int] = None
    features: Optional[List[str]] = None
    max_devices: Optional[int] = None
    max_concurrent_inspections: Optional[int] = None
    total_inspection_quota: Optional[int] = None
    allow_custom_duration: Optional[bool] = None
    allow_custom_limits: Optional[bool] = None
    status: Optional[Literal["ACTIVE", "INACTIVE"]] = None

    @field_validator("max_devices")
    @classmethod
    def check_max_devices(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            return validate_limit_integer(v, "max_devices")
        return v

    @field_validator("max_concurrent_inspections")
    @classmethod
    def check_max_concurrent_inspections(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            return validate_limit_integer(v, "max_concurrent_inspections")
        return v

    @field_validator("total_inspection_quota")
    @classmethod
    def check_total_inspection_quota(cls, v: Optional[int]) -> Optional[int]:
        if v is not None:
            return validate_limit_integer(v, "total_inspection_quota")
        return v

    @field_validator("features")
    @classmethod
    def normalize_features(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            if not v or "*" in v or "all" in [str(f).lower() for f in v]:
                return list(ALL_SOFTWARE_FEATURES)
            cleaned = sorted({f.strip() for f in v if f and f.strip()})
            return cleaned or list(ALL_SOFTWARE_FEATURES)
        return v


class LicensePlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    plan_code: str
    plan_name: str
    product_id: str
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    edition: str
    description: Optional[str]
    license_type: str
    default_duration_days: Optional[int]
    features: List[str]
    max_devices: int
    max_concurrent_inspections: int
    total_inspection_quota: int
    allow_custom_duration: bool
    allow_custom_limits: bool
    status: str
    created_at: datetime
    updated_at: datetime


# --- Licenses & Issuance ---

class LicenseLimitsSchema(BaseModel):
    max_devices: int
    max_concurrent_inspections: int
    total_inspection_quota: int

    @field_validator("max_devices")
    @classmethod
    def check_max_devices(cls, v: int) -> int:
        return validate_limit_integer(v, "max_devices")

    @field_validator("max_concurrent_inspections")
    @classmethod
    def check_max_concurrent_inspections(cls, v: int) -> int:
        return validate_limit_integer(v, "max_concurrent_inspections")

    @field_validator("total_inspection_quota")
    @classmethod
    def check_total_inspection_quota(cls, v: int) -> int:
        return validate_limit_integer(v, "total_inspection_quota")


class LicenseIssueRequest(BaseModel):
    customer_id: str = Field(..., min_length=1)
    plan_id: str = Field(..., min_length=1)
    not_before: Optional[datetime] = None
    duration_days: Optional[int] = Field(None, gt=0, le=36500)
    custom_limits: Optional[LicenseLimitsSchema] = None
    custom_features: Optional[List[str]] = None
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("custom_features")
    @classmethod
    def normalize_custom_features(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            if not v or "*" in v or "all" in [str(f).lower() for f in v]:
                return list(ALL_SOFTWARE_FEATURES)
            cleaned = sorted({f.strip() for f in v if f and f.strip()})
            return cleaned or list(ALL_SOFTWARE_FEATURES)
        return v


class LicenseRenewRequest(BaseModel):
    duration_days: Optional[int] = Field(None, gt=0, le=36500)
    reason: str = Field(..., min_length=3, max_length=1000)
    notes: Optional[str] = Field(None, max_length=2000)


class LicenseReplaceRequest(BaseModel):
    plan_id: Optional[str] = None
    duration_days: Optional[int] = Field(None, gt=0, le=36500)
    custom_limits: Optional[LicenseLimitsSchema] = None
    custom_features: Optional[List[str]] = None
    reason: str = Field(..., min_length=3, max_length=1000)
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("custom_features")
    @classmethod
    def normalize_custom_features(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is not None:
            if not v or "*" in v or "all" in [str(f).lower() for f in v]:
                return list(ALL_SOFTWARE_FEATURES)
            cleaned = sorted({f.strip() for f in v if f and f.strip()})
            return cleaned or list(ALL_SOFTWARE_FEATURES)
        return v


class LicenseStatusActionRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)


class LicenseRelationshipItem(BaseModel):
    id: str
    previous_license_id: str
    previous_license_number: Optional[str] = None
    new_license_id: str
    new_license_number: Optional[str] = None
    relationship_type: str
    reason: Optional[str]
    created_at: datetime


class LicenseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    license_number: str
    customer_id: str
    customer_code: Optional[str] = None
    customer_name: Optional[str] = None
    product_id: str
    product_code_snapshot: str
    plan_id: str
    plan_code_snapshot: str
    plan_name_snapshot: str
    schema_version: str
    edition: str
    license_type: str
    issued_at: datetime
    not_before: datetime
    expires_at: Optional[datetime]
    features_snapshot: List[str]
    limits_snapshot: Dict[str, int]
    key_id: str
    signature_algorithm: str
    signature_b64: str
    signed_artifact_json: Dict[str, Any]
    status: str
    effective_status: str
    status_reason: Optional[str]
    status_updated_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    signature_verified: Optional[bool] = None
    lineage_previous: List[LicenseRelationshipItem] = Field(default_factory=list)
    lineage_next: List[LicenseRelationshipItem] = Field(default_factory=list)


class PaginatedLicensesResponse(BaseModel):
    items: List[LicenseResponse]
    total: int
    page: int
    page_size: int


class VerifyArtifactRequest(BaseModel):
    artifact: Optional[Dict[str, Any]] = None


class VerifyArtifactResponse(BaseModel):
    valid: bool
    license_id: Optional[str] = None
    license_number: Optional[str] = None
    key_id: Optional[str] = None
    algorithm: Optional[str] = None
    effective_status: Optional[str] = None
    reason: Optional[str] = None
    verified_at: datetime


# --- Signing Keys ---

class SigningKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    key_id: str
    algorithm: str
    public_key_pem: str
    fingerprint_sha256: str
    is_active: bool
    status: str
    description: Optional[str]
    created_at: datetime
    rotated_at: Optional[datetime]


class SigningKeyRegisterRequest(BaseModel):
    key_id: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    public_key_pem: str = Field(..., min_length=32)
    description: Optional[str] = Field(None, max_length=500)
    set_active: bool = True


# --- Audit Logs ---

class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    timestamp: datetime
    actor_id: Optional[str]
    actor_username: Optional[str]
    action: str
    entity_type: str
    entity_id: Optional[str]
    outcome: str
    reason: Optional[str]
    metadata_json: Optional[Dict[str, Any]]


class PaginatedAuditLogsResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int


# --- Dashboard ---

class DashboardSummaryResponse(BaseModel):
    total_customers: int
    active_customers: int
    active_licenses: int
    expiring_soon_licenses: int
    expired_licenses: int
    revoked_or_suspended_licenses: int
    issued_in_period: int
    period_days: int
    recent_licenses: List[LicenseResponse]
    expiring_soon_list: List[LicenseResponse]
    recent_audit_logs: List[AuditLogResponse]
    signing_engine_ready: bool
    active_key_id: Optional[str] = None
