from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import require_role
from ..database import get_db

router = APIRouter(prefix="/api/products", tags=["products"])


def to_out(p: models.Product) -> schemas.ProductOut:
    out = schemas.ProductOut.model_validate(p)
    out.supplier_company = p.supplier.company if p.supplier else None
    return out


@router.get("", response_model=list[schemas.ProductOut])
def list_products(
    q: str | None = None,
    category: str | None = None,
    material: str | None = None,
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    supplier_id: int | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(models.Product).options(joinedload(models.Product.supplier))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(
            models.Product.name.ilike(like),
            models.Product.description.ilike(like),
            models.Product.material.ilike(like),
            models.Product.category.ilike(like),
        ))
    if category:
        stmt = stmt.where(models.Product.category == category)
    if material:
        stmt = stmt.where(models.Product.material == material)
    if min_price is not None:
        stmt = stmt.where(models.Product.unit_price >= min_price)
    if max_price is not None:
        stmt = stmt.where(models.Product.unit_price <= max_price)
    if supplier_id is not None:
        stmt = stmt.where(models.Product.supplier_id == supplier_id)
    return [to_out(p) for p in db.scalars(stmt.order_by(models.Product.name))]


@router.get("/facets")
def facets(db: Session = Depends(get_db)):
    """Distinct categories/materials with counts, for catalogue filters."""
    cats = db.execute(
        select(models.Product.category, func.count()).group_by(models.Product.category).order_by(models.Product.category)
    ).all()
    mats = db.execute(
        select(models.Product.material, func.count()).group_by(models.Product.material).order_by(models.Product.material)
    ).all()
    return {
        "categories": [{"name": c, "count": n} for c, n in cats],
        "materials": [{"name": m, "count": n} for m, n in mats],
    }


@router.get("/mine", response_model=list[schemas.ProductOut])
def my_products(user: models.User = Depends(require_role("supplier")), db: Session = Depends(get_db)):
    stmt = select(models.Product).where(models.Product.supplier_id == user.id).order_by(models.Product.name)
    return [to_out(p) for p in db.scalars(stmt)]


@router.get("/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    p = db.get(models.Product, product_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return to_out(p)


@router.post("", response_model=schemas.ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    data: schemas.ProductIn,
    user: models.User = Depends(require_role("supplier")),
    db: Session = Depends(get_db),
):
    p = models.Product(**data.model_dump(), supplier_id=user.id)
    db.add(p)
    db.commit()
    db.refresh(p)
    return to_out(p)


def _owned(product_id: int, user: models.User, db: Session) -> models.Product:
    p = db.get(models.Product, product_id)
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    if p.supplier_id != user.id and user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only manage your own products")
    return p


@router.put("/{product_id}", response_model=schemas.ProductOut)
def update_product(
    product_id: int,
    data: schemas.ProductIn,
    user: models.User = Depends(require_role("supplier", "admin")),
    db: Session = Depends(get_db),
):
    p = _owned(product_id, user, db)
    for k, v in data.model_dump().items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return to_out(p)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    user: models.User = Depends(require_role("supplier", "admin")),
    db: Session = Depends(get_db),
):
    p = _owned(product_id, user, db)
    if p.enquiries:
        raise HTTPException(status.HTTP_409_CONFLICT, "Product has enquiries and cannot be deleted")
    db.delete(p)
    db.commit()
