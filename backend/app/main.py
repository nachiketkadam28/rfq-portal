import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
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

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(enquiries.router)
app.include_router(dashboard.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
