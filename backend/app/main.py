import os

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .auth import IS_HOSTED, SECRET_KEY
from .database import Base, engine, is_sqlite
from . import models  # noqa: F401  (registers tables)
from .routers import auth, dashboard, enquiries, products

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Industrial B2B RFQ & CRM Portal")

# Comma-separated exact origins, e.g. "https://rfq-desk.vercel.app,https://rfq.example.com".
# CORS_ORIGIN_REGEX additionally matches preview deployments, e.g. r"https://rfq-portal-[\w-]+\.vercel\.app".
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip().rstrip("/")
        for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if o.strip()
    ],
    allow_origin_regex=os.getenv("CORS_ORIGIN_REGEX") or None,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


# Misconfiguration is reported loudly but doesn't take the public catalogue down.
CONFIG_PROBLEMS = []
if IS_HOSTED and not SECRET_KEY:
    CONFIG_PROBLEMS.append("SECRET_KEY is missing or shorter than 32 characters; sign-in is disabled")
if IS_HOSTED and is_sqlite:
    CONFIG_PROBLEMS.append("DATABASE_URL is not set; data is stored in SQLite and will be lost")
for problem in CONFIG_PROBLEMS:
    logging.getLogger("uvicorn.error").error("CONFIG: %s", problem)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(enquiries.router)
app.include_router(dashboard.router)


@app.get("/api/health")
def health():
    if CONFIG_PROBLEMS:
        return {"status": "misconfigured", "problems": CONFIG_PROBLEMS}
    return {"status": "ok"}
