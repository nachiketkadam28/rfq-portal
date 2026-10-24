from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator

# Upper bounds keep values inside DB column types and keep totals finite.
MAX_PRICE = 1_000_000
MAX_QUANTITY = 10_000_000


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    company: str = Field(min_length=2, max_length=150)
    email: EmailStr = Field(max_length=150)
    password: str = Field(min_length=8)
    role: Literal["buyer", "supplier"]       # nobody can self-register as admin

    @field_validator("password")
    @classmethod
    def password_fits_bcrypt(cls, v: str) -> str:
        if len(v.encode()) > 72:
            raise ValueError("must be at most 72 bytes")
        return v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    company: str
    email: str
    role: str                                # note: no password field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    category: str = Field(min_length=1, max_length=80)
    material: str = Field(min_length=1, max_length=80)
    unit_price: float = Field(gt=0, le=MAX_PRICE)
    unit: str = Field("piece", min_length=1, max_length=20)
    description: str = Field("", max_length=5000)


class ProductOut(BaseModel):
    # Plain fields (no input limits) so rows stored before a limit existed still serialize.
    model_config = ConfigDict(from_attributes=True)
    name: str
    category: str
    material: str
    unit_price: float
    unit: str
    description: str
    id: int
    supplier_id: int
    supplier_company: str | None = None


class EnquiryIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0, le=MAX_QUANTITY)
    required_by: date | None = None
    message: str = Field("", max_length=5000)

    @field_validator("required_by")
    @classmethod
    def not_in_past(cls, v: date | None) -> date | None:
        if v is not None and v < date.today():
            raise ValueError("must be today or later")
        return v


class QuotationIn(BaseModel):
    price_per_unit: float = Field(gt=0, le=MAX_PRICE)
    delivery_days: int = Field(gt=0, le=3650)
    notes: str = Field("", max_length=2000)


class QuotationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    price_per_unit: float
    delivery_days: int
    notes: str
    id: int
    created_at: datetime


class ScoreReason(BaseModel):
    feature: str
    impact: float


class EnquiryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    product_name: str
    product_category: str
    product_unit: str
    list_price: float
    supplier_company: str
    buyer_name: str
    buyer_company: str
    quantity: int
    required_by: date | None
    message: str
    status: str
    lead_score: float | None                 # hidden (None) from buyers
    score_reasons: list[ScoreReason] = []
    created_at: datetime
    quotations: list[QuotationOut] = []


class StatusUpdate(BaseModel):
    status: Literal["won", "lost"]


class ModelInfo(BaseModel):
    auc: float
    training_rows: int
    real_outcomes: int