from datetime import datetime, date
from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, Date, Text, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    company: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))  # buyer | supplier | admin
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    products = relationship("Product", back_populates="supplier")
    enquiries = relationship("Enquiry", back_populates="buyer")


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(150), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    material: Mapped[str] = mapped_column(String(80))
    unit_price: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(20), default="piece")
    description: Mapped[str] = mapped_column(Text, default="")

    supplier = relationship("User", back_populates="products")
    enquiries = relationship("Enquiry", back_populates="product")


class Enquiry(Base):
    """An RFQ (request for quotation) raised by a buyer for a product."""
    __tablename__ = "enquiries"
    id: Mapped[int] = mapped_column(primary_key=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    required_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    message: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    lead_score: Mapped[float] = mapped_column(Float, default=0.0)
    score_reasons: Mapped[str] = mapped_column(Text, default="[]")  # JSON list from ml.lead_model.score
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    buyer = relationship("User", back_populates="enquiries")
    product = relationship("Product", back_populates="enquiries")
    quotations = relationship("Quotation", back_populates="enquiry", cascade="all, delete-orphan")


class Quotation(Base):
    __tablename__ = "quotations"
    id: Mapped[int] = mapped_column(primary_key=True)
    enquiry_id: Mapped[int] = mapped_column(ForeignKey("enquiries.id"), index=True)
    price_per_unit: Mapped[float] = mapped_column(Float)
    delivery_days: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    enquiry = relationship("Enquiry", back_populates="quotations")


class ModelVersion(Base):
    """A retrained lead-scoring model. Stored in the DB so every serverless instance sees it."""
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    blob: Mapped[bytes] = mapped_column(LargeBinary)
    auc: Mapped[float] = mapped_column(Float)
    training_rows: Mapped[int] = mapped_column(Integer)
    real_outcomes: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RateEvent(Base):
    """One rate-limited action (e.g. a failed login) for app.ratelimit."""
    __tablename__ = "rate_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    bucket: Mapped[str] = mapped_column(String(200), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
