# app/main.py
from fastapi import FastAPI
from shared.database import AuthBase, auth_engine
from fastapi.middleware.cors import CORSMiddleware
from .routers import authrouter, userrouter
from .models import users, roles, userroles, rolepolicy

# Create tables
AuthBase.metadata.create_all(bind=auth_engine)

# This MUST exist for uvicorn
app = FastAPI(title="Unified Auth (Google + Mobile)")

# Allow requests from your React app
origins = [
    "http://localhost:9090",
    "http://127.0.0.1:8002",
    "http://192.0.0.2:9090"
    # Add other origins if deploying later
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # or ["*"] to allow all origins (not recommended for production)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routers
app.include_router(authrouter.router)
app.include_router(userrouter.router)
