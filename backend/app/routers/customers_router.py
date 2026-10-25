from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.audit import record_audit_event
from app.auth import get_current_user, require_roles
from app.database import get_db
from app.models import Customer, License, User
from app.schemas import (
    CustomerCreateRequest,
    CustomerDeactivateRequest,
    CustomerResponse,
    CustomerUpdateRequest,
    PaginatedCustomersResponse,
)

router = APIRouter(prefix="/api/customers", tags=["Customers"])


def _to_customer_response(db: Session, customer: Customer) -> CustomerResponse:
    lic_count = (
        db.query(func.count(License.id))
        .filter(License.customer_id == customer.id)
        .scalar()
        or 0
    )
    resp = CustomerResponse.model_validate(customer)
    resp.issued_licenses_count = lic_count
    return resp


@router.get("", response_model=PaginatedCustomersResponse)
def list_customers(
    search: Optional[str] = Query(None, description="Search by customer code, company name, or email"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by ACTIVE or INACTIVE"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Customer)

    if search and search.strip():
        q = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Customer.customer_code.ilike(q),
                Customer.company_name.ilike(q),
                Customer.contact_email.ilike(q),
                Customer.contact_person.ilike(q),
            )
        )

    if status_filter and status_filter.strip():
        query = query.filter(Customer.status == status_filter.strip().upper())

    total = query.count()
    customers = (
        query.order_by(Customer.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [_to_customer_response(db, c) for c in customers]
    return PaginatedCustomersResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    req: CustomerCreateRequest,
    current_user: User = Depends(require_roles(["SUPER_ADMIN", "LICENSE_ADMIN"], "CREATE_CUSTOMER")),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(Customer)
        .filter(Customer.customer_code == req.customer_code)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Customer code '{req.customer_code}' already exists.",
        )

    customer = Customer(
        customer_code=req.customer_code,
        company_name=req.company_name.strip(),
        contact_person=req.contact_person.strip(),
        contact_email=req.contact_email.strip().lower(),
        contact_phone=req.contact_phone.strip() if req.contact_phone else None,
        country_region=req.country_region.strip() if req.country_region else None,
        address=req.address.strip() if req.address else None,
        notes=req.notes.strip() if req.notes else None,
        status="ACTIVE",
    )
    db.add(customer)
    db.flush()

    record_audit_event(
        db,
        actor=current_user,
        action="CUSTOMER_CREATED",
        entity_type="CUSTOMER",
        entity_id=customer.id,
        outcome="SUCCESS",
        reason=f"Created customer '{customer.company_name}' ({customer.customer_code})",
        metadata={"customer_code": customer.customer_code, "company_name": customer.company_name},
        commit=False,
    )
    db.commit()
    db.refresh(customer)
    return _to_customer_response(db, customer)


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return _to_customer_response(db, customer)


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: str,
    req: CustomerUpdateRequest,
    current_user: User = Depends(require_roles(["SUPER_ADMIN", "LICENSE_ADMIN"], "UPDATE_CUSTOMER")),
    db: Session = Depends(get_db),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    update_data = req.model_dump(exclude_unset=True)
    changed_fields = []
    for field, val in update_data.items():
        if isinstance(val, str):
            val = val.strip()
        if getattr(customer, field) != val:
            setattr(customer, field, val)
            changed_fields.append(field)

    record_audit_event(
        db,
        actor=current_user,
        action="CUSTOMER_UPDATED",
        entity_type="CUSTOMER",
        entity_id=customer.id,
        outcome="SUCCESS",
        reason=f"Updated customer '{customer.customer_code}'",
        metadata={"changed_fields": changed_fields, "customer_code": customer.customer_code},
        commit=False,
    )
    db.commit()
    db.refresh(customer)
    return _to_customer_response(db, customer)


@router.post("/{customer_id}/deactivate", response_model=CustomerResponse)
def deactivate_customer(
    customer_id: str,
    req: CustomerDeactivateRequest,
    current_user: User = Depends(require_roles(["SUPER_ADMIN", "LICENSE_ADMIN"], "DEACTIVATE_CUSTOMER")),
    db: Session = Depends(get_db),
):
    """
    Deactivates a customer while preserving all historical license records untouched.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    if customer.status == "INACTIVE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer is already INACTIVE.",
        )

    customer.status = "INACTIVE"
    record_audit_event(
        db,
        actor=current_user,
        action="CUSTOMER_DEACTIVATED",
        entity_type="CUSTOMER",
        entity_id=customer.id,
        outcome="SUCCESS",
        reason=req.reason,
        metadata={"customer_code": customer.customer_code},
        commit=False,
    )
    db.commit()
    db.refresh(customer)
    return _to_customer_response(db, customer)


@router.post("/{customer_id}/activate", response_model=CustomerResponse)
def activate_customer(
    customer_id: str,
    current_user: User = Depends(require_roles(["SUPER_ADMIN", "LICENSE_ADMIN"], "ACTIVATE_CUSTOMER")),
    db: Session = Depends(get_db),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    customer.status = "ACTIVE"
    record_audit_event(
        db,
        actor=current_user,
        action="CUSTOMER_ACTIVATED",
        entity_type="CUSTOMER",
        entity_id=customer.id,
        outcome="SUCCESS",
        reason=f"Reactivated customer {customer.customer_code}",
        metadata={"customer_code": customer.customer_code},
        commit=False,
    )
    db.commit()
    db.refresh(customer)
    return _to_customer_response(db, customer)


@router.delete("/{customer_id}")
def delete_customer(
    customer_id: str,
    current_user: User = Depends(require_roles(["SUPER_ADMIN"], "DELETE_CUSTOMER")),
    db: Session = Depends(get_db),
):
    """
    Prevents deletion of customers associated with issued licenses.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    lic_count = (
        db.query(func.count(License.id))
        .filter(License.customer_id == customer.id)
        .scalar()
        or 0
    )
    if lic_count > 0:
        record_audit_event(
            db,
            actor=current_user,
            action="CUSTOMER_DELETE_BLOCKED",
            entity_type="CUSTOMER",
            entity_id=customer.id,
            outcome="DENIED",
            reason=f"Cannot delete customer {customer.customer_code} with {lic_count} issued licenses",
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete customer '{customer.customer_code}' because {lic_count} license(s) have been issued. Deactivate the customer instead to preserve historical records.",
        )

    code = customer.customer_code
    db.delete(customer)
    record_audit_event(
        db,
        actor=current_user,
        action="CUSTOMER_DELETED",
        entity_type="CUSTOMER",
        entity_id=customer_id,
        outcome="SUCCESS",
        reason=f"Deleted customer {code} with zero issued licenses",
        commit=False,
    )
    db.commit()
    return {"detail": f"Customer {code} deleted."}
