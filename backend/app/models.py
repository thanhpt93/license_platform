import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(128), nullable=False)
    password_hash = Column(String(255), nullable=False)
    # Roles: SUPER_ADMIN, LICENSE_ADMIN, AUDITOR
    role = Column(String(32), nullable=False, default="LICENSE_ADMIN")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    customer_code = Column(String(64), unique=True, nullable=False, index=True)
    company_name = Column(String(255), nullable=False, index=True)
    contact_person = Column(String(128), nullable=False)
    contact_email = Column(String(255), nullable=False, index=True)
    contact_phone = Column(String(64), nullable=True)
    country_region = Column(String(128), nullable=True)
    address = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    # Status: ACTIVE or INACTIVE
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    licenses = relationship("License", back_populates="customer")


class Product(Base):
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    product_code = Column(String(64), unique=True, nullable=False, index=True)
    product_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    supported_editions = Column(JSON, nullable=False, default=lambda: ["developer", "production"])
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    plans = relationship("LicensePlan", back_populates="product")
    licenses = relationship("License", back_populates="product")


class LicensePlan(Base):
    __tablename__ = "license_plans"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    plan_code = Column(String(64), unique=True, nullable=False, index=True)
    plan_name = Column(String(255), nullable=False)
    product_id = Column(String(36), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    edition = Column(String(64), nullable=False)  # developer, production
    description = Column(Text, nullable=True)
    license_type = Column(String(32), nullable=False)  # SUBSCRIPTION or PERPETUAL
    default_duration_days = Column(Integer, nullable=True)  # null for PERPETUAL, >0 for SUBSCRIPTION
    features = Column(JSON, nullable=False, default=list)  # list of strings
    max_devices = Column(Integer, nullable=False, default=1)  # -1 unlimited, 0 disabled, >0 cap
    max_concurrent_inspections = Column(Integer, nullable=False, default=1)  # -1 unlimited, 0 disabled, >0 cap
    total_inspection_quota = Column(Integer, nullable=False, default=-1)  # -1 unlimited, 0 disabled, >0 cap
    allow_custom_duration = Column(Boolean, nullable=False, default=True)
    allow_custom_limits = Column(Boolean, nullable=False, default=True)
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)  # ACTIVE or INACTIVE
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    product = relationship("Product", back_populates="plans")
    licenses = relationship("License", back_populates="plan")


class SigningKey(Base):
    """
    Stores ONLY public key metadata and verification material.
    Private signing keys must NEVER be stored in database tables.
    """
    __tablename__ = "signing_keys"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    key_id = Column(String(64), unique=True, nullable=False, index=True)
    algorithm = Column(String(32), nullable=False, default="Ed25519")
    public_key_pem = Column(Text, nullable=False)
    fingerprint_sha256 = Column(String(128), nullable=False)
    is_active = Column(Boolean, nullable=False, default=False, index=True)
    status = Column(String(32), nullable=False, default="ACTIVE")  # ACTIVE, RETIRED, COMPROMISED
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    rotated_at = Column(DateTime(timezone=True), nullable=True)


class License(Base):
    __tablename__ = "licenses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    license_number = Column(String(64), unique=True, nullable=False, index=True)
    customer_id = Column(String(36), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True)
    product_id = Column(String(36), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True)
    plan_id = Column(String(36), ForeignKey("license_plans.id", ondelete="RESTRICT"), nullable=False, index=True)

    # Immutable snapshot of plan & entitlements at issuance
    schema_version = Column(String(16), nullable=False, default="1.0")
    product_code_snapshot = Column(String(64), nullable=False)
    plan_code_snapshot = Column(String(64), nullable=False)
    plan_name_snapshot = Column(String(255), nullable=False)
    edition = Column(String(64), nullable=False)
    license_type = Column(String(32), nullable=False)  # SUBSCRIPTION, PERPETUAL
    issued_at = Column(DateTime(timezone=True), nullable=False, index=True)
    not_before = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    features_snapshot = Column(JSON, nullable=False)
    limits_snapshot = Column(JSON, nullable=False)

    # Cryptographic signature fields
    key_id = Column(String(64), ForeignKey("signing_keys.key_id", ondelete="RESTRICT"), nullable=False, index=True)
    signature_algorithm = Column(String(32), nullable=False, default="Ed25519")
    canonical_payload_json = Column(Text, nullable=False)
    signature_b64 = Column(Text, nullable=False)
    signed_artifact_json = Column(JSON, nullable=False)

    # Administrative Status: ACTIVE, EXPIRED, SUSPENDED, REVOKED, REPLACED
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)
    status_reason = Column(Text, nullable=True)
    status_updated_at = Column(DateTime(timezone=True), nullable=True)
    status_updated_by = Column(String(36), nullable=True)
    issued_by = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    customer = relationship("Customer", back_populates="licenses")
    product = relationship("Product", back_populates="licenses")
    plan = relationship("LicensePlan", back_populates="licenses")

    outgoing_relationships = relationship(
        "LicenseRelationship",
        foreign_keys="LicenseRelationship.previous_license_id",
        back_populates="previous_license",
    )
    incoming_relationships = relationship(
        "LicenseRelationship",
        foreign_keys="LicenseRelationship.new_license_id",
        back_populates="new_license",
    )


class LicenseRelationship(Base):
    """
    Tracks lineage across RENEWAL and REPLACEMENT operations.
    """
    __tablename__ = "license_relationships"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    previous_license_id = Column(String(36), ForeignKey("licenses.id", ondelete="RESTRICT"), nullable=False, index=True)
    new_license_id = Column(String(36), ForeignKey("licenses.id", ondelete="RESTRICT"), nullable=False, index=True)
    relationship_type = Column(String(32), nullable=False)  # RENEWAL, REPLACEMENT
    reason = Column(Text, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    previous_license = relationship(
        "License",
        foreign_keys=[previous_license_id],
        back_populates="outgoing_relationships",
    )
    new_license = relationship(
        "License",
        foreign_keys=[new_license_id],
        back_populates="incoming_relationships",
    )

    __table_args__ = (
        UniqueConstraint("previous_license_id", "new_license_id", name="uq_license_relationship_pair"),
    )


class AuditLog(Base):
    """
    Immutable administrative audit trail.
    Never logs private keys, passphrases, passwords, or session tokens.
    """
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    actor_id = Column(String(36), nullable=True, index=True)
    actor_username = Column(String(64), nullable=True)
    action = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False, index=True)
    entity_id = Column(String(64), nullable=True, index=True)
    outcome = Column(String(32), nullable=False, default="SUCCESS", index=True)  # SUCCESS, FAILURE, DENIED
    reason = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)


Index("ix_licenses_customer_status", License.customer_id, License.status)
Index("ix_licenses_expires_status", License.expires_at, License.status)
