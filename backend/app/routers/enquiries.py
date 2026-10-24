import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from .. import models, schemas
from ..auth import get_current_user, require_role
from ..database import get_db
from ..scoring import apply_score

router = APIRouter(prefix="/api/enquiries", tags=["enquiries"])


def to_out(e: models.Enquiry, viewer: models.User) -> schemas.EnquiryOut:
    # Buyers never see how their enquiry was scored.
    hide = viewer.role == "buyer"
    return schemas.EnquiryOut(
        id=e.id,
        product_id=e.product_id,
        product_name=e.product.name,
        product_category=e.product.category,
        product_unit=e.product.unit,
        list_price=e.product.unit_price,
        supplier_company=e.product.supplier.company,
        buyer_name=e.buyer.name,
        buyer_company=e.buyer.company,
        quantity=e.quantity,
        required_by=e.required_by,
        message=e.message,
        status=e.status,
        lead_score=None if hide else e.lead_score,
        score_reasons=[] if hide else json.loads(e.score_reasons or "[]"),
        created_at=e.created_at,
        quotations=[schemas.QuotationOut.model_validate(q) for q in sorted(e.quotations, key=lambda q: q.created_at)],
    )


def _query():
    return select(models.Enquiry).options(
        joinedload(models.Enquiry.product).joinedload(models.Product.supplier),
        joinedload(models.Enquiry.buyer),
        selectinload(models.Enquiry.quotations),
    )


def _visible(e: models.Enquiry, user: models.User) -> bool:
    return user.role == "admin" or e.buyer_id == user.id or e.product.supplier_id == user.id


def _get(db: Session, enquiry_id: int, user: models.User) -> models.Enquiry:
    e = db.scalars(_query().where(models.Enquiry.id == enquiry_id)).unique().one_or_none()
    if not e or not _visible(e, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Enquiry not found")
    return e


@router.post("", response_model=schemas.EnquiryOut, status_code=status.HTTP_201_CREATED)
def create_enquiry(
    data: schemas.EnquiryIn,
    user: models.User = Depends(require_role("buyer")),
    db: Session = Depends(get_db),
):
    product = db.get(models.Product, data.product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    e = models.Enquiry(**data.model_dump(), buyer_id=user.id)
    db.add(e)
    db.flush()
    apply_score(db, e, product)
    db.commit()
    return to_out(_get(db, e.id, user), user)


@router.get("", response_model=list[schemas.EnquiryOut])
def list_enquiries(
    status_: Literal["new", "quoted", "won", "lost"] | None = Query(None, alias="status"),
    sort: Literal["score", "recent"] = "recent",
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = _query()
    if user.role == "buyer":
        stmt = stmt.where(models.Enquiry.buyer_id == user.id)
    elif user.role == "supplier":
        stmt = stmt.join(models.Enquiry.product).where(models.Product.supplier_id == user.id)
    if status_:
        stmt = stmt.where(models.Enquiry.status == status_)
    if sort == "score" and user.role != "buyer":
        stmt = stmt.order_by(models.Enquiry.lead_score.desc())
    else:
        stmt = stmt.order_by(models.Enquiry.created_at.desc())
    stmt = stmt.order_by(models.Enquiry.id.desc()).limit(limit).offset(offset)
    return [to_out(e, user) for e in db.scalars(stmt).unique()]


@router.get("/{enquiry_id}", response_model=schemas.EnquiryOut)
def get_enquiry(enquiry_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return to_out(_get(db, enquiry_id, user), user)


@router.post("/{enquiry_id}/quotations", response_model=schemas.EnquiryOut, status_code=status.HTTP_201_CREATED)
def send_quotation(
    enquiry_id: int,
    data: schemas.QuotationIn,
    user: models.User = Depends(require_role("supplier")),
    db: Session = Depends(get_db),
):
    e = _get(db, enquiry_id, user)
    if e.product.supplier_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the product's supplier can quote")
    if e.status in ("won", "lost"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Enquiry is already closed")
    e.quotations.append(models.Quotation(**data.model_dump()))
    e.status = "quoted"
    db.commit()
    return to_out(_get(db, enquiry_id, user), user)


@router.patch("/{enquiry_id}/status", response_model=schemas.EnquiryOut)
def update_status(
    enquiry_id: int,
    data: schemas.StatusUpdate,
    user: models.User = Depends(require_role("buyer", "supplier")),
    db: Session = Depends(get_db),
):
    """Close an enquiry. Buyers accept (won) or decline (lost) a quote; suppliers record the outcome."""
    e = _get(db, enquiry_id, user)
    if e.status in ("won", "lost"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Enquiry is already closed")
    if user.role == "buyer" and data.status == "won" and not e.quotations:
        raise HTTPException(status.HTTP_409_CONFLICT, "There is no quotation to accept yet")
    e.status = data.status
    db.commit()
    return to_out(_get(db, enquiry_id, user), user)
