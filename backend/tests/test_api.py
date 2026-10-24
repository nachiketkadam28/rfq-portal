import os
import tempfile

_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.database import Base, engine  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestClient(app)


def register(client, email, role, company="Acme"):
    r = client.post("/api/auth/register", json={
        "name": "Test User", "company": company, "email": email, "password": "secret123", "role": role,
    })
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def make_product(client, headers, **kw):
    body = {"name": "Hex Bolt", "category": "Fasteners", "material": "SS304", "unit_price": 0.5, **kw}
    r = client.post("/api/products", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_register_login_me(client):
    register(client, "a@example.com", "buyer")
    r = client.post("/api/auth/login", data={"username": "A@example.com", "password": "secret123"})
    assert r.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.json()["email"] == "a@example.com"
    assert "password_hash" not in me.json()


def test_cannot_register_admin_or_duplicate(client):
    r = client.post("/api/auth/register", json={
        "name": "Evil", "company": "Evil", "email": "e@example.com", "password": "secret123", "role": "admin",
    })
    assert r.status_code == 422
    register(client, "d@example.com", "buyer")
    r = client.post("/api/auth/register", json={
        "name": "Dup", "company": "Dup", "email": "d@example.com", "password": "secret123", "role": "buyer",
    })
    assert r.status_code == 409


def test_wrong_password(client):
    register(client, "a@example.com", "buyer")
    r = client.post("/api/auth/login", data={"username": "a@example.com", "password": "nope"})
    assert r.status_code == 401


def test_product_permissions_and_search(client):
    sup = register(client, "s@example.com", "supplier", company="Forge")
    other = register(client, "s2@example.com", "supplier")
    buyer = register(client, "b@example.com", "buyer")
    p = make_product(client, sup)
    make_product(client, sup, name="Ball Valve", category="Valves", unit_price=60)
    assert p["supplier_company"] == "Forge"
    assert client.post("/api/products", json={**p, "unit_price": 1}, headers=buyer).status_code == 403
    assert client.put(f"/api/products/{p['id']}", json={**p, "unit_price": 1}, headers=other).status_code == 403
    assert client.get("/api/products", params={"q": "valve"}).json()[0]["name"] == "Ball Valve"
    assert len(client.get("/api/products", params={"category": "Fasteners"}).json()) == 1
    assert len(client.get("/api/products", params={"max_price": 10}).json()) == 1
    facets = client.get("/api/products/facets").json()
    assert {c["name"] for c in facets["categories"]} == {"Fasteners", "Valves"}


def test_rfq_lifecycle(client):
    sup = register(client, "s@example.com", "supplier")
    buyer = register(client, "b@example.com", "buyer")
    stranger = register(client, "c@example.com", "buyer")
    p = make_product(client, sup)

    r = client.post("/api/enquiries", json={
        "product_id": p["id"], "quantity": 5000, "required_by": "2099-01-01", "message": "Need certs",
    }, headers=buyer)
    assert r.status_code == 201, r.text
    enq = r.json()
    assert enq["lead_score"] is None  # hidden from the buyer
    assert enq["status"] == "new"

    seen = client.get("/api/enquiries", headers=sup).json()
    assert len(seen) == 1 and 0 <= seen[0]["lead_score"] <= 100
    assert seen[0]["score_reasons"]
    assert client.get(f"/api/enquiries/{enq['id']}", headers=stranger).status_code == 404

    # Buyer cannot accept before there is a quote.
    assert client.patch(f"/api/enquiries/{enq['id']}/status", json={"status": "won"}, headers=buyer).status_code == 409
    assert client.post(f"/api/enquiries/{enq['id']}/quotations", json={"price_per_unit": 0.45, "delivery_days": 10}, headers=buyer).status_code == 403

    r = client.post(f"/api/enquiries/{enq['id']}/quotations", json={"price_per_unit": 0.45, "delivery_days": 10}, headers=sup)
    assert r.json()["status"] == "quoted" and len(r.json()["quotations"]) == 1

    r = client.patch(f"/api/enquiries/{enq['id']}/status", json={"status": "won"}, headers=buyer)
    assert r.json()["status"] == "won"
    assert client.patch(f"/api/enquiries/{enq['id']}/status", json={"status": "lost"}, headers=sup).status_code == 409

    dash = client.get("/api/dashboard", headers=sup).json()
    assert dash["status_counts"]["won"] == 1
    assert dash["win_rate"] == 100.0
    assert dash["won_value"] == pytest.approx(5000 * 0.45)


def test_product_with_enquiries_cannot_be_deleted(client):
    sup = register(client, "s@example.com", "supplier")
    buyer = register(client, "b@example.com", "buyer")
    p = make_product(client, sup)
    client.post("/api/enquiries", json={"product_id": p["id"], "quantity": 1}, headers=buyer)
    assert client.delete(f"/api/products/{p['id']}", headers=sup).status_code == 409


def test_admin_only_routes(client):
    buyer = register(client, "b@example.com", "buyer")
    assert client.get("/api/admin/users", headers=buyer).status_code == 403
    assert client.post("/api/admin/model/retrain", headers=buyer).status_code == 403


def test_lead_model_prefers_strong_leads():
    from ml.lead_model import LeadInput, score

    weak, _ = score(LeadInput(quantity=1, unit_price=1, days_to_deadline=None, message_words=0, prior_enquiries=0, prior_wins=0))
    strong, reasons = score(LeadInput(quantity=500, unit_price=40, days_to_deadline=25, message_words=40, prior_enquiries=6, prior_wins=4))
    assert strong > weak
    assert len(reasons) == 3


def test_retrain_stores_model_in_db_not_on_disk(client):
    from ml.lead_model import MODEL_PATH
    from app import models
    from app.auth import hash_password
    from app.database import SessionLocal

    db = SessionLocal()
    db.add(models.User(name="Admin", company="Portal", email="admin@example.com", password_hash=hash_password("secret123"), role="admin"))
    db.commit()
    token = client.post("/api/auth/login", data={"username": "admin@example.com", "password": "secret123"}).json()["access_token"]
    before = MODEL_PATH.stat().st_mtime

    r = client.post("/api/admin/model/retrain", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    assert 0.5 < r.json()["auc"] <= 1
    assert db.query(models.ModelVersion).count() == 1
    assert MODEL_PATH.stat().st_mtime == before  # bundled file untouched (read-only hosts)

    # New enquiries are scored with the stored model.
    sup = register(client, "s@example.com", "supplier")
    buyer = register(client, "b@example.com", "buyer")
    p = make_product(client, sup)
    r = client.post("/api/enquiries", json={"product_id": p["id"], "quantity": 100}, headers=buyer)
    assert r.status_code == 201
    db.close()


def test_postgres_url_normalised():
    from app.database import _normalize

    assert _normalize("postgres://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"
    assert _normalize("postgresql://u:p@h/db?sslmode=require") == "postgresql+psycopg2://u:p@h/db?sslmode=require"
    assert _normalize("postgresql+psycopg2://u:p@h/db") == "postgresql+psycopg2://u:p@h/db"
    assert _normalize("sqlite:///./x.db") == "sqlite:///./x.db"


def test_cors_allows_configured_origin(client):
    r = client.options("/api/products", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    r = client.options("/api/products", headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in r.headers
