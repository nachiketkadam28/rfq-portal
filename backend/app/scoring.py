import json
from datetime import date

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ml import lead_model
from . import models


def _buyer_history(db: Session, buyer_id: int, before_id: int | None = None) -> tuple[int, int]:
    stmt = select(func.count(), func.count().filter(models.Enquiry.status == "won")).where(
        models.Enquiry.buyer_id == buyer_id
    )
    if before_id is not None:
        stmt = stmt.where(models.Enquiry.id < before_id)
    total, won = db.execute(stmt).one()
    return int(total), int(won)


def lead_input(db: Session, enquiry: models.Enquiry, product: models.Product, today: date | None = None) -> lead_model.LeadInput:
    today = today or date.today()
    prior, wins = _buyer_history(db, enquiry.buyer_id, before_id=enquiry.id)
    return lead_model.LeadInput(
        quantity=enquiry.quantity,
        unit_price=product.unit_price,
        days_to_deadline=(enquiry.required_by - today).days if enquiry.required_by else None,
        message_words=len(enquiry.message.split()),
        prior_enquiries=prior,
        prior_wins=wins,
    )


# (version id, model) of the newest retrained model this process has loaded.
_active: tuple[int, object] | None = None


def current_model(db: Session):
    """Newest model in the DB, falling back to the bundled one. Cheap: one indexed max() per call."""
    global _active
    latest = db.scalar(select(func.max(models.ModelVersion.id)))
    if latest is None:
        return lead_model.bundled()
    if _active is None or _active[0] != latest:
        _active = (latest, lead_model.loads(db.get(models.ModelVersion, latest).blob))
    return _active[1]


def apply_score(db: Session, enquiry: models.Enquiry, product: models.Product, today: date | None = None) -> None:
    score, reasons = lead_model.score(lead_input(db, enquiry, product, today), current_model(db))
    enquiry.lead_score = score
    enquiry.score_reasons = json.dumps(reasons)


def retrain(db: Session) -> dict:
    """Retrain on synthetic data plus every enquiry with a known outcome, then rescore open ones."""
    closed = db.scalars(select(models.Enquiry).where(models.Enquiry.status.in_(["won", "lost"]))).all()
    X = [lead_model.featurize(lead_input(db, e, e.product, today=e.created_at.date())) for e in closed]
    y = [1 if e.status == "won" else 0 for e in closed]
    model, info = lead_model.fit(np.array(X) if X else None, np.array(y) if y else None)
    db.add(models.ModelVersion(blob=lead_model.dumps(model), **info))
    db.flush()
    for e in db.scalars(select(models.Enquiry).where(models.Enquiry.status.in_(["new", "quoted"]))):
        apply_score(db, e, e.product, today=e.created_at.date())
    db.commit()
    return info
