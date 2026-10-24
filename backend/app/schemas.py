from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserCreate(BaseModel):
    name: str = Field(min_length=2)
    company: str = Field(min_length=2)
    email: EmailStr
    password: str = Field(min_length=6)
    role: Literal["buyer", "supplier"]       # nobody can self-register as admin


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
    name: str
    category: str
    material: str
    unit_price: float = Field(gt=0)
    unit: str = "piece"
    description: str = ""


class ProductOut(ProductIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    supplier_id: int
    supplier_company: str | None = None


class EnquiryIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    required_by: date | None = None
    message: str = ""


class QuotationIn(BaseModel):
    price_per_unit: float = Field(gt=0)
    delivery_days: int = Field(gt=0)
    notes: str = ""


class QuotationOut(QuotationIn):
    model_config = ConfigDict(from_attributes=True)
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