from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import (
    audit_keys_router,
    auth_router,
    customers_router,
    dashboard_router,
    licenses_router,
    products_router,
)

app = FastAPI(
    title="NOVA License Management API",
    description="Enterprise License Administration & Cryptographic Signing Service for NOVA Machine Vision Platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Returns clean, actionable validation errors without echoing raw sensitive input values
    such as passwords, private keys, or passphrases.
    """
    sanitized_errors = []
    for err in exc.errors():
        loc = " -> ".join(str(x) for x in err.get("loc", []))
        msg = err.get("msg", "Invalid value")
        sanitized_errors.append({"field": loc, "message": msg, "type": err.get("type")})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation failed",
            "errors": sanitized_errors,
        },
    )


@app.get("/api/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "service": settings.NOVA_APP_NAME,
        "version": "1.0.0",
    }


app.include_router(auth_router.router)
app.include_router(dashboard_router.router)
app.include_router(customers_router.router)
app.include_router(products_router.router)
app.include_router(licenses_router.router)
app.include_router(audit_keys_router.router)
