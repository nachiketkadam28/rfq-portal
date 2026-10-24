from collections import Counter, defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from .. import models
from ..auth import get_current_user, require_role
from ..database import get_db
from ..scoring import retrain
from .enquiries import to_out

router = APIRouter(prefix="/api", tags=["dashboard"])

STATUSES = ["new", "quoted", "won", "lost"]


def _last_months(n: int = 6) -> list[str]:
    now = datetime.utcnow()
    y, m = now.year, now.month
    out = []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


def _order_value(e: models.Enquiry) -> float:
    """Value at the latest quoted price, or list price if not quoted yet."""
    price = max(e.quotations, key=lambda q: q.created_at).price_per_unit if e.quotations else e.product.unit_price
    return e.quantity * price


def _summary(enquiries: list[models.Enquiry]) -> dict:
    counts = Counter(e.status for e in enquiries)
    closed = counts["won"] + counts["lost"]
    months = _last_months()
    monthly = {m: {"month": m, "enquiries": 0, "won": 0} for m in months}
    for e in enquiries:
        key = e.created_at.strftime("%Y-%m")
        if key in monthly:
            monthly[key]["enquiries"] += 1
            monthly[key]["won"] += e.status == "won"
    return {
        "status_counts": {s: counts[s] for s in STATUSES},
        "total": len(enquiries),
        "win_rate": round(counts["won"] / closed * 100, 1) if closed else None,
        "pipeline_value": round(sum(_order_value(e) for e in enquiries if e.status in ("new", "quoted")), 2),
        "won_value": round(sum(_order_value(e) for e in enquiries if e.status == "won"), 2),
        "monthly": list(monthly.values()),
    }


@router.get("/dashboard")
def dashboard(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(models.Enquiry).options(
        joinedload(models.Enquiry.product).joinedload(models.Product.supplier),
        joinedload(models.Enquiry.buyer),
        selectinload(models.Enquiry.quotations),
    )
    if user.role == "buyer":
        stmt = stmt.where(models.Enquiry.buyer_id == user.id)
    elif user.role == "supplier":
        stmt = stmt.join(models.Enquiry.product).where(models.Product.supplier_id == user.id)
    enquiries = list(db.scalars(stmt).unique())
    data = {"role": user.role, **_summary(enquiries)}

    if user.role == "buyer":
        data["awaiting_decision"] = [to_out(e, user) for e in enquiries if e.status == "quoted"][:5]
        return data

    open_ = [e for e in enquiries if e.status in ("new", "quoted")]
    data["avg_open_score"] = round(sum(e.lead_score for e in open_) / len(open_), 1) if open_ else None
    data["hot_leads"] = [to_out(e, user) for e in sorted(open_, key=lambda e: -e.lead_score)[:5]]
    by_product: dict[str, dict] = defaultdict(lambda: {"enquiries": 0, "won": 0})
    for e in enquiries:
        by_product[e.product.name]["enquiries"] += 1
        by_product[e.product.name]["won"] += e.status == "won"
    data["top_products"] = sorted(
        ({"product": k, **v} for k, v in by_product.items()), key=lambda r: -r["enquiries"]
    )[:5]
    # Distribution of scores of open leads in 20-point bands, for the "lead quality" chart.
    bands = [0] * 5
    for e in open_:
        bands[min(int(e.lead_score // 20), 4)] += 1
    data["score_bands"] = [{"band": f"{i * 20}–{i * 20 + 20}", "count": c} for i, c in enumerate(bands)]

    if user.role == "admin":
        roles = dict(db.execute(select(models.User.role, func.count()).group_by(models.User.role)).all())
        data["users"] = {r: roles.get(r, 0) for r in ("buyer", "supplier", "admin")}
        data["products"] = db.scalar(select(func.count()).select_from(models.Product))
    return data


@router.get("/admin/users")
def list_users(_: models.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    rows = db.execute(
        select(models.User, func.count(models.Product.id))
        .outerjoin(models.Product, models.Product.supplier_id == models.User.id)
        .group_by(models.User.id)
        .order_by(models.User.created_at.desc())
    ).all()
    enq = dict(db.execute(select(models.Enquiry.buyer_id, func.count()).group_by(models.Enquiry.buyer_id)).all())
    return [
        {
            "id": u.id, "name": u.name, "company": u.company, "email": u.email, "role": u.role,
            "created_at": u.created_at, "products": n, "enquiries": enq.get(u.id, 0),
        }
        for u, n in rows
    ]


@router.post("/admin/model/retrain")
def retrain_model(_: models.User = Depends(require_role("admin")), db: Session = Depends(get_db)):
    return retrain(db)
