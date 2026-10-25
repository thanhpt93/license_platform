from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.audit import record_audit_event
from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import LicensePlan, Product, User
from app.schemas import (
    LicensePlanCreateRequest,
    LicensePlanResponse,
    LicensePlanUpdateRequest,
    ProductCreateRequest,
    ProductResponse,
)

router = APIRouter(prefix="/api", tags=["Products & License Plans"])


def _to_plan_response(plan: LicensePlan) -> LicensePlanResponse:
    resp = LicensePlanResponse.model_validate(plan)
    if plan.product:
        resp.product_code = plan.product.product_code
        resp.product_name = plan.product.product_name
    return resp


@router.get("/products", response_model=List[ProductResponse])
def list_products(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    products = db.query(Product).order_by(Product.created_at.asc()).all()
    return [ProductResponse.model_validate(p) for p in products]


@router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    req: ProductCreateRequest,
    current_user: User = Depends(require_roles(["SUPER_ADMIN", "LICENSE_ADMIN"], "CREATE_PRODUCT")),
    db: Session = Depends(get_db),
):
    existing = db.query(Product).filter(Product.product_code == req.product_code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product code '{req.product_code}' already exists.",
        )

    product = Product(
        product_code=req.product_code,
        product_name=req.product_name.strip(),
        description=req.description.strip() if req.description else None,
        supported_editions=req.supported_editions,
        status="ACTIVE",
    )
    db.add(product)
    db.flush()

    record_audit_event(
        db,
        actor=current_user,
        action="PRODUCT_CREATED",
        entity_type="PRODUCT",
        entity_id=product.id,
        outcome="SUCCESS",
        reason=f"Created product '{product.product_name}' ({product.product_code})",
        metadata={"product_code": product.product_code},
        commit=False,
    )
    db.commit()
    db.refresh(product)
    return ProductResponse.model_validate(product)


@router.get("/license-plans", response_model=List[LicensePlanResponse])
def list_license_plans(
    product_id: Optional[str] = Query(None),
    edition: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(LicensePlan)
    if product_id:
        query = query.filter(LicensePlan.product_id == product_id)
    if edition:
        query = query.filter(LicensePlan.edition == edition)
    if status_filter:
        query = query.filter(LicensePlan.status == status_filter.upper())

    plans = query.order_by(LicensePlan.created_at.desc()).all()
    return [_to_plan_response(p) for p in plans]


@router.post("/license-plans", response_model=LicensePlanResponse, status_code=status.HTTP_201_CREATED)
def create_license_plan(
    req: LicensePlanCreateRequest,
    current_user: User = Depends(require_roles(["SUPER_ADMIN", "LICENSE_ADMIN"], "CREATE_LICENSE_PLAN")),
    db: Session = Depends(get_db),
):
    existing = db.query(LicensePlan).filter(LicensePlan.plan_code == req.plan_code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"License plan code '{req.plan_code}' already exists.",
        )

    product = db.query(Product).filter(Product.id == req.product_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    plan = LicensePlan(
        plan_code=req.plan_code,
        plan_name=req.plan_name.strip(),
        product_id=req.product_id,
        edition=req.edition,
        description=req.description.strip() if req.description else None,
        license_type=req.license_type,
        default_duration_days=req.default_duration_days,
        features=req.features,
        max_devices=req.max_devices,
        max_concurrent_inspections=req.max_concurrent_inspections,
        total_inspection_quota=req.total_inspection_quota,
        allow_custom_duration=req.allow_custom_duration,
        allow_custom_limits=req.allow_custom_limits,
        status=req.status,
    )
    db.add(plan)
    db.flush()

    record_audit_event(
        db,
        actor=current_user,
        action="LICENSE_PLAN_CREATED",
        entity_type="LICENSE_PLAN",
        entity_id=plan.id,
        outcome="SUCCESS",
        reason=f"Created license plan '{plan.plan_name}' ({plan.plan_code})",
        metadata={
            "plan_code": plan.plan_code,
            "edition": plan.edition,
            "license_type": plan.license_type,
        },
        commit=False,
    )
    db.commit()
    db.refresh(plan)
    return _to_plan_response(plan)


@router.patch("/license-plans/{plan_id}", response_model=LicensePlanResponse)
def update_license_plan(
    plan_id: str,
    req: LicensePlanUpdateRequest,
    current_user: User = Depends(require_roles(["SUPER_ADMIN", "LICENSE_ADMIN"], "UPDATE_LICENSE_PLAN")),
    db: Session = Depends(get_db),
):
    """
    Updates a license plan configuration.
    Does NOT modify any previously issued licenses (which preserve their immutable snapshots).
    """
    plan = db.query(LicensePlan).filter(LicensePlan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License plan not found.")

    update_data = req.model_dump(exclude_unset=True)
    if plan.license_type == "PERPETUAL" and "default_duration_days" in update_data:
        update_data["default_duration_days"] = None
    elif (
        plan.license_type == "SUBSCRIPTION"
        and "default_duration_days" in update_data
        and (update_data["default_duration_days"] is None or update_data["default_duration_days"] <= 0)
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SUBSCRIPTION plans must maintain a positive default_duration_days (> 0).",
        )

    changed_fields = []
    for k, v in update_data.items():
        if getattr(plan, k) != v:
            setattr(plan, k, v)
            changed_fields.append(k)

    record_audit_event(
        db,
        actor=current_user,
        action="LICENSE_PLAN_UPDATED",
        entity_type="LICENSE_PLAN",
        entity_id=plan.id,
        outcome="SUCCESS",
        reason=f"Updated license plan '{plan.plan_code}'",
        metadata={"plan_code": plan.plan_code, "changed_fields": changed_fields},
        commit=False,
    )
    db.commit()
    db.refresh(plan)
    return _to_plan_response(plan)
