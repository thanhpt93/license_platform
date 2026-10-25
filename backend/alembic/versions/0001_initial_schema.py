"""Initial schema for NOVA License Management

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-25 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # 2. customers
    op.create_table(
        "customers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("customer_code", sa.String(length=64), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("contact_person", sa.String(length=128), nullable=False),
        sa.Column("contact_email", sa.String(length=255), nullable=False),
        sa.Column("contact_phone", sa.String(length=64), nullable=True),
        sa.Column("country_region", sa.String(length=128), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customers_customer_code", "customers", ["customer_code"], unique=True)
    op.create_index("ix_customers_company_name", "customers", ["company_name"], unique=False)
    op.create_index("ix_customers_contact_email", "customers", ["contact_email"], unique=False)
    op.create_index("ix_customers_status", "customers", ["status"], unique=False)

    # 3. products
    op.create_table(
        "products",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("product_code", sa.String(length=64), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("supported_editions", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_products_product_code", "products", ["product_code"], unique=True)
    op.create_index("ix_products_status", "products", ["status"], unique=False)

    # 4. license_plans
    op.create_table(
        "license_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("plan_code", sa.String(length=64), nullable=False),
        sa.Column("plan_name", sa.String(length=255), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("edition", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("license_type", sa.String(length=32), nullable=False),
        sa.Column("default_duration_days", sa.Integer(), nullable=True),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("max_devices", sa.Integer(), nullable=False),
        sa.Column("max_concurrent_inspections", sa.Integer(), nullable=False),
        sa.Column("total_inspection_quota", sa.Integer(), nullable=False),
        sa.Column("allow_custom_duration", sa.Boolean(), nullable=False),
        sa.Column("allow_custom_limits", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_license_plans_plan_code", "license_plans", ["plan_code"], unique=True)
    op.create_index("ix_license_plans_product_id", "license_plans", ["product_id"], unique=False)
    op.create_index("ix_license_plans_status", "license_plans", ["status"], unique=False)

    # 5. signing_keys
    op.create_table(
        "signing_keys",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("key_id", sa.String(length=64), nullable=False),
        sa.Column("algorithm", sa.String(length=32), nullable=False),
        sa.Column("public_key_pem", sa.Text(), nullable=False),
        sa.Column("fingerprint_sha256", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signing_keys_key_id", "signing_keys", ["key_id"], unique=True)
    op.create_index("ix_signing_keys_is_active", "signing_keys", ["is_active"], unique=False)

    # 6. licenses
    op.create_table(
        "licenses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("license_number", sa.String(length=64), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("plan_id", sa.String(length=36), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("product_code_snapshot", sa.String(length=64), nullable=False),
        sa.Column("plan_code_snapshot", sa.String(length=64), nullable=False),
        sa.Column("plan_name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("edition", sa.String(length=64), nullable=False),
        sa.Column("license_type", sa.String(length=32), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("not_before", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("features_snapshot", sa.JSON(), nullable=False),
        sa.Column("limits_snapshot", sa.JSON(), nullable=False),
        sa.Column("key_id", sa.String(length=64), nullable=False),
        sa.Column("signature_algorithm", sa.String(length=32), nullable=False),
        sa.Column("canonical_payload_json", sa.Text(), nullable=False),
        sa.Column("signature_b64", sa.Text(), nullable=False),
        sa.Column("signed_artifact_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("status_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_updated_by", sa.String(length=36), nullable=True),
        sa.Column("issued_by", sa.String(length=36), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["issued_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["key_id"], ["signing_keys.key_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plan_id"], ["license_plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_licenses_license_number", "licenses", ["license_number"], unique=True)
    op.create_index("ix_licenses_customer_id", "licenses", ["customer_id"], unique=False)
    op.create_index("ix_licenses_product_id", "licenses", ["product_id"], unique=False)
    op.create_index("ix_licenses_plan_id", "licenses", ["plan_id"], unique=False)
    op.create_index("ix_licenses_issued_at", "licenses", ["issued_at"], unique=False)
    op.create_index("ix_licenses_expires_at", "licenses", ["expires_at"], unique=False)
    op.create_index("ix_licenses_key_id", "licenses", ["key_id"], unique=False)
    op.create_index("ix_licenses_status", "licenses", ["status"], unique=False)
    op.create_index("ix_licenses_customer_status", "licenses", ["customer_id", "status"], unique=False)
    op.create_index("ix_licenses_expires_status", "licenses", ["expires_at", "status"], unique=False)

    # 7. license_relationships
    op.create_table(
        "license_relationships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("previous_license_id", sa.String(length=36), nullable=False),
        sa.Column("new_license_id", sa.String(length=36), nullable=False),
        sa.Column("relationship_type", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["new_license_id"], ["licenses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["previous_license_id"], ["licenses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("previous_license_id", "new_license_id", name="uq_license_relationship_pair"),
    )
    op.create_index("ix_license_relationships_previous_license_id", "license_relationships", ["previous_license_id"], unique=False)
    op.create_index("ix_license_relationships_new_license_id", "license_relationships", ["new_license_id"], unique=False)

    # 8. audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=True),
        sa.Column("actor_username", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"], unique=False)
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"], unique=False)
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"], unique=False)
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"], unique=False)
    op.create_index("ix_audit_logs_outcome", "audit_logs", ["outcome"], unique=False)


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("license_relationships")
    op.drop_table("licenses")
    op.drop_table("signing_keys")
    op.drop_table("license_plans")
    op.drop_table("products")
    op.drop_table("customers")
    op.drop_table("users")
