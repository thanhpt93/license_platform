from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.audit import record_audit_event
from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_roles,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, TokenResponse, UserCreateRequest, UserResponse

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username.strip()).first()
    if not user or not verify_password(req.password, user.password_hash):
        record_audit_event(
            db,
            actor=None,
            actor_username_override=req.username.strip(),
            action="AUTH_LOGIN_FAILED",
            entity_type="USER",
            entity_id=user.id if user else None,
            outcome="FAILURE",
            reason="Invalid username or password",
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        record_audit_event(
            db,
            actor=user,
            action="AUTH_LOGIN_FAILED",
            entity_type="USER",
            entity_id=user.id,
            outcome="DENIED",
            reason="Inactive user attempted login",
            commit=True,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    token = create_access_token(user)
    record_audit_event(
        db,
        actor=user,
        action="AUTH_LOGIN_SUCCESS",
        entity_type="USER",
        entity_id=user.id,
        outcome="SUCCESS",
        reason=f"Administrator '{user.username}' signed in",
        commit=True,
    )
    return TokenResponse(
        access_token=token,
        expires_in_minutes=settings.NOVA_ACCESS_TOKEN_EXPIRE_MINUTES,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


@router.get("/users", response_model=List[UserResponse])
def list_users(
    current_user: User = Depends(require_roles(["SUPER_ADMIN", "LICENSE_ADMIN", "AUDITOR"], "LIST_USERS")),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at.asc()).all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    req: UserCreateRequest,
    current_user: User = Depends(require_roles(["SUPER_ADMIN"], "CREATE_ADMIN_USER")),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(User)
        .filter((User.username == req.username) | (User.email == req.email))
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )

    new_user = User(
        username=req.username.strip(),
        email=req.email.strip().lower(),
        full_name=req.full_name.strip(),
        password_hash=hash_password(req.password),
        role=req.role,
        is_active=True,
    )
    db.add(new_user)
    db.flush()

    record_audit_event(
        db,
        actor=current_user,
        action="USER_CREATED",
        entity_type="USER",
        entity_id=new_user.id,
        outcome="SUCCESS",
        reason=f"Created user '{new_user.username}' with role {new_user.role}",
        metadata={"username": new_user.username, "role": new_user.role},
        commit=False,
    )
    db.commit()
    db.refresh(new_user)
    return UserResponse.model_validate(new_user)
