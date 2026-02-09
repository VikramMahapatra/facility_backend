# app/main.py
from fastapi import FastAPI
from auth_service.app.routers import super_admin_router
from shared.core.database import AuthBase, auth_engine
from fastapi.middleware.cors import CORSMiddleware

from shared.helpers.exception_handler import setup_exception_handlers
from shared.wrappers.response_wrapper import JsonResponseMiddleware
from .routers import authrouter, userrouter
from shared.models import users, user_login_session, refresh_token
from .models import roles, userroles, rolepolicy, user_otps,  otp_verifications, user_organizations, associations

# Create tables
AuthBase.metadata.create_all(bind=auth_engine)

# This MUST exist for uvicorn
app = FastAPI(title="Unified Auth (Google + Mobile)")

# Allow requests from your React app
# ... imports ...

# Allow requests from ANYWHERE (Fixes the CORS error)
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ... rest of code ...

# 2️⃣ Custom JSON response wrapper middleware
app.add_middleware(JsonResponseMiddleware)

# Register exception handlers
setup_exception_handlers(app)

# Routers
app.include_router(authrouter.router)
app.include_router(userrouter.router)
app.include_router(super_admin_router.router)


@app.get("/api/auth/health")
def health():
    return {"status": "healthy"}
