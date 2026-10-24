"""Regression tests for the security review fixes."""
from datetime import date, timedelta

import pytest

from tests.test_api import client, make_product, register  # noqa: F401  (fixture + helpers)


def login(client, email, password):
    return client.post("/api/auth/login", data={"username": email, "password": password})


# -- Critical: forged tokens / missing secret ---------------------------

def test_hosted_without_secret_disables_auth(client, monkeypatch):
    from app import auth
    register(client, "a@example.com", "buyer")
    monkeypatch.setattr(auth, "SECRET_KEY", None)
    assert login(client, "a@example.com", "secret123").status_code == 503
    r = client.post("/api/auth/register", json={
        "name": "New", "company": "Acme", "email": "n@example.com", "password": "secret123", "role": "buyer"})
    assert r.status_code == 503
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer x.y.z"}).status_code == 503
    assert client.get("/api/products").status_code == 200  # public catalogue stays up


def test_token_signed_with_other_secret_rejected(client):
    import jwt
    forged = jwt.encode({"sub": "1", "role": "admin", "exp": 9999999999}, "attacker-secret", algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_token_without_exp_rejected(client):
    import jwt
    from app.auth import SECRET_KEY
    register(client, "a@example.com", "buyer")
    no_exp = jwt.encode({"sub": "1", "role": "buyer"}, SECRET_KEY, algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {no_exp}"}).status_code == 401


def test_health_reports_misconfiguration(client, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "CONFIG_PROBLEMS", ["SECRET_KEY is missing"])
    assert client.get("/api/health").json()["status"] == "misconfigured"


# -- High: long passwords, brute force ----------------------------------

def test_long_password_rejected_not_500(client):
    r = client.post("/api/auth/register", json={
        "name": "Long", "company": "Acme", "email": "l@example.com", "password": "x" * 100, "role": "buyer"})
    assert r.status_code == 422
    register(client, "a@example.com", "buyer")
    assert login(client, "a@example.com", "x" * 100).status_code == 401


def test_short_password_rejected(client):
    r = client.post("/api/auth/register", json={
        "name": "Short", "company": "Acme", "email": "s@example.com", "password": "1234567", "role": "buyer"})
    assert r.status_code == 422


def test_login_locks_after_repeated_failures(client):
    register(client, "a@example.com", "buyer")
    for _ in range(5):
        assert login(client, "a@example.com", "wrong-password").status_code == 401
    r = login(client, "a@example.com", "secret123")  # even the right password is blocked now
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    assert login(client, "other@example.com", "wrong-password").status_code == 401  # other emails unaffected


def test_registration_rate_limited_per_ip(client):
    for i in range(10):
        register(client, f"u{i}@example.com", "buyer")
    r = client.post("/api/auth/register", json={
        "name": "Spam", "company": "Acme", "email": "spam@example.com", "password": "secret123", "role": "buyer"})
    assert r.status_code == 429


def test_unknown_email_still_runs_bcrypt(client, monkeypatch):
    from app import auth
    calls = []
    real = auth.bcrypt.checkpw
    monkeypatch.setattr(auth.bcrypt, "checkpw", lambda pw, h: calls.append(1) or real(pw, h))
    assert login(client, "nobody@example.com", "secret123").status_code == 401
    assert calls, "login with an unknown email must still hash, so timing does not reveal accounts"


# -- Medium: input bounds, pagination -----------------------------------

@pytest.mark.parametrize("field,value", [
    ("unit_price", 1e308), ("unit_price", 0), ("name", "A" * 151), ("description", "d" * 5001), ("unit", "u" * 21),
])
def test_product_bounds(client, field, value):
    sup = register(client, "s@example.com", "supplier")
    body = {"name": "Bolt", "category": "Fasteners", "material": "SS", "unit_price": 1.0, field: value}
    assert client.post("/api/products", json=body, headers=sup).status_code == 422


@pytest.mark.parametrize("patch", [
    {"quantity": 10**30}, {"quantity": 10_000_001}, {"message": "m" * 5001},
    {"required_by": (date.today() - timedelta(days=1)).isoformat()},
])
def test_enquiry_bounds(client, patch):
    sup = register(client, "s@example.com", "supplier")
    buyer = register(client, "b@example.com", "buyer")
    p = make_product(client, sup)
    r = client.post("/api/enquiries", json={"product_id": p["id"], "quantity": 5, **patch}, headers=buyer)
    assert r.status_code == 422


def test_quote_bounds_and_dashboard_stays_up(client):
    sup = register(client, "s@example.com", "supplier")
    buyer = register(client, "b@example.com", "buyer")
    p = make_product(client, sup)
    e = client.post("/api/enquiries", json={"product_id": p["id"], "quantity": 5}, headers=buyer).json()
    for body in ({"price_per_unit": 1e308, "delivery_days": 5}, {"price_per_unit": 1, "delivery_days": 99999},
                 {"price_per_unit": 1, "delivery_days": 5, "notes": "n" * 2001}):
        assert client.post(f"/api/enquiries/{e['id']}/quotations", json=body, headers=sup).status_code == 422
    assert client.get("/api/dashboard", headers=sup).status_code == 200


def test_register_field_lengths(client):
    r = client.post("/api/auth/register", json={
        "name": "A" * 101, "company": "Acme", "email": "a@example.com", "password": "secret123", "role": "buyer"})
    assert r.status_code == 422


def test_pagination_limits(client):
    sup = register(client, "s@example.com", "supplier")
    for i in range(3):
        make_product(client, sup, name=f"Part {i}")
    assert len(client.get("/api/products", params={"limit": 2}).json()) == 2
    assert [p["name"] for p in client.get("/api/products", params={"limit": 2, "offset": 2}).json()] == ["Part 2"]
    assert client.get("/api/products", params={"limit": 1000}).status_code == 422
    assert client.get("/api/products", params={"q": "x" * 101}).status_code == 422


def test_search_wildcards_are_literal(client):
    sup = register(client, "s@example.com", "supplier")
    make_product(client, sup, name="Hex Bolt")
    assert client.get("/api/products", params={"q": "%"}).json() == []
    assert client.get("/api/products", params={"q": "_"}).json() == []
    make_product(client, sup, name="100% PTFE tape")
    assert [p["name"] for p in client.get("/api/products", params={"q": "100%"}).json()] == ["100% PTFE tape"]


def test_api_security_headers(client):
    r = client.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


# -- Medium: demo accounts, model poisoning -----------------------------

def test_demo_accounts_cannot_change_catalogue(client):
    from app.seed import DEMO_EMAILS
    demo_supplier = next(e for e in DEMO_EMAILS if e.startswith("sales@forgeline"))
    demo = register(client, demo_supplier, "supplier")
    r = client.post("/api/products", json={"name": "Spam", "category": "C", "material": "M", "unit_price": 1}, headers=demo)
    assert r.status_code == 403
    # Real suppliers are unaffected.
    real = register(client, "real@example.com", "supplier")
    assert client.post("/api/products", json={"name": "Ok", "category": "C", "material": "M", "unit_price": 1},
                       headers=real).status_code == 201


def test_retrain_caps_outcomes_per_account_and_ignores_unquoted(client, monkeypatch):
    from app import scoring
    from app.database import SessionLocal

    monkeypatch.setattr(scoring, "MAX_OUTCOMES_PER_ACCOUNT", 2)
    sup = register(client, "s@example.com", "supplier")
    buyer = register(client, "b@example.com", "buyer")
    p = make_product(client, sup)
    for i in range(4):
        e = client.post("/api/enquiries", json={"product_id": p["id"], "quantity": 5}, headers=buyer).json()
        if i < 3:
            client.post(f"/api/enquiries/{e['id']}/quotations", json={"price_per_unit": 1, "delivery_days": 5}, headers=sup)
        client.patch(f"/api/enquiries/{e['id']}/status", json={"status": "lost"}, headers=sup)
    db = SessionLocal()
    kept = scoring._trusted_outcomes(db)
    assert len(kept) == 2 and all(e.quotations for e in kept)
    db.close()


def test_retrain_keeps_current_model_when_quality_drops(client, monkeypatch):
    from app import models, scoring
    from app.database import SessionLocal

    monkeypatch.setattr(scoring, "MIN_AUC_TO_ACTIVATE", 1.01)  # nothing can pass
    db = SessionLocal()
    info = scoring.retrain(db)
    assert info["activated"] is False
    assert db.query(models.ModelVersion).count() == 0
    db.close()
