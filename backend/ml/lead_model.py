"""Lead scoring model: estimates how likely an RFQ is to convert into an order.

The model is a scaled logistic regression, which keeps it fast to train and lets us
explain each score as per-feature contributions. With no real history yet it is
trained on synthetic enquiries; once suppliers mark enquiries won/lost, those
labelled rows are mixed in on retrain. Retrained models are stored in the database
(app.scoring), not on disk, because serverless hosts have a read-only filesystem.
"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

MODEL_PATH = Path(__file__).with_name("lead_model.joblib")

FEATURES = [
    "log_order_value",
    "log_quantity",
    "has_deadline",
    "urgency",
    "message_words",
    "prior_enquiries",
    "prior_wins",
]

LABELS = {
    "log_order_value": "Order value",
    "log_quantity": "Quantity",
    "has_deadline": "Has a required-by date",
    "urgency": "Deadline urgency",
    "message_words": "Detailed requirements",
    "prior_enquiries": "Repeat buyer",
    "prior_wins": "Past orders won",
}


@dataclass
class LeadInput:
    quantity: int
    unit_price: float
    days_to_deadline: int | None
    message_words: int
    prior_enquiries: int
    prior_wins: int


def featurize(x: LeadInput) -> list[float]:
    has_deadline = 0.0 if x.days_to_deadline is None else 1.0
    # Urgency peaks for deadlines 1–6 weeks out: real projects, not fire drills.
    if x.days_to_deadline is None:
        urgency = 0.0
    else:
        d = max(x.days_to_deadline, 0)
        urgency = math.exp(-((d - 25) ** 2) / (2 * 20**2))
    return [
        math.log1p(max(x.quantity, 0) * max(x.unit_price, 0)),
        math.log1p(max(x.quantity, 0)),
        has_deadline,
        urgency,
        float(min(x.message_words, 120)),
        float(min(x.prior_enquiries, 20)),
        float(min(x.prior_wins, 10)),
    ]


def synthetic_dataset(n: int = 4000, seed: int = 7) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    rows, labels = [], []
    for _ in range(n):
        x = LeadInput(
            quantity=int(rng.lognormal(4.5, 1.3)) + 1,
            unit_price=float(rng.lognormal(2.5, 1.2)),
            days_to_deadline=None if rng.random() < 0.35 else int(rng.integers(0, 150)),
            message_words=int(rng.gamma(2.0, 12)),
            prior_enquiries=int(rng.poisson(1.5)),
            prior_wins=0,
        )
        x.prior_wins = int(rng.binomial(x.prior_enquiries, 0.4))
        f = featurize(x)
        logit = (
            -3.2
            + 0.18 * f[0]
            + 0.9 * f[2]
            + 1.6 * f[3]
            + 0.025 * f[4]
            + 0.15 * f[5]
            + 0.55 * f[6]
            + rng.normal(0, 0.6)
        )
        rows.append(f)
        labels.append(int(rng.random() < 1 / (1 + math.exp(-logit))))
    return np.array(rows), np.array(labels)


def fit(extra_X: np.ndarray | None = None, extra_y: np.ndarray | None = None) -> tuple[Pipeline, dict]:
    """Train a model in memory. Persisting it is the caller's job (see app.scoring)."""
    X, y = synthetic_dataset()
    real = 0
    if extra_X is not None and len(extra_X):
        # Weight real outcomes by repeating them; they matter more than synthetic rows.
        real = len(extra_X)
        X = np.vstack([X] + [extra_X] * 5)
        y = np.concatenate([y] + [extra_y] * 5)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=0, stratify=y)
    model = Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression(max_iter=1000))])
    model.fit(X_tr, y_tr)
    auc = float(roc_auc_score(y_te, model.predict_proba(X_te)[:, 1]))
    model.fit(X, y)
    return model, {"auc": round(auc, 3), "training_rows": int(len(X)), "real_outcomes": real}


def dumps(model: Pipeline) -> bytes:
    buf = io.BytesIO()
    joblib.dump(model, buf)
    return buf.getvalue()


def loads(blob: bytes) -> Pipeline:
    return joblib.load(io.BytesIO(blob))


_bundled: Pipeline | None = None


def bundled() -> Pipeline:
    """The model shipped with the code. Never writes to disk, so it works on read-only hosts."""
    global _bundled
    if _bundled is None:
        _bundled = joblib.load(MODEL_PATH) if MODEL_PATH.exists() else fit()[0]
    return _bundled


def score(x: LeadInput, model: Pipeline | None = None) -> tuple[float, list[dict]]:
    """Return (score 0-100, top reasons) for one enquiry."""
    model = model or bundled()
    f = np.array([featurize(x)])
    prob = float(model.predict_proba(f)[0, 1])
    scaled = model.named_steps["scale"].transform(f)[0]
    contrib = scaled * model.named_steps["clf"].coef_[0]
    reasons = sorted(
        ({"feature": LABELS[name], "impact": round(float(c), 3)} for name, c in zip(FEATURES, contrib)),
        key=lambda r: abs(r["impact"]),
        reverse=True,
    )[:3]
    return round(prob * 100, 1), reasons


if __name__ == "__main__":
    # Rebuild the bundled model file (run locally, then commit lead_model.joblib).
    m, info = fit()
    joblib.dump(m, MODEL_PATH)
    print(info)
