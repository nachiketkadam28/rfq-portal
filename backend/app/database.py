import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase


def _normalize(url: str) -> str:
    # Neon/Supabase hand out "postgres://" or bare "postgresql://". SQLAlchemy 2 rejects the
    # first and maps the second to psycopg v3; we ship psycopg2-binary, so name it explicitly.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


# SQLite by default; set DATABASE_URL to a hosted Postgres in production
# (serverless filesystems are read-only or wiped, so SQLite cannot persist there).
DATABASE_URL = _normalize(os.getenv("DATABASE_URL", "sqlite:///./rfq.db"))

is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if is_sqlite else {},
    # Serverless instances freeze between requests; drop dead connections instead of erroring.
    pool_pre_ping=not is_sqlite,
    pool_recycle=300,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
