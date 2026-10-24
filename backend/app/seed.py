"""Populate the database with demo data.  Run from backend/:  python -m app.seed

To seed a hosted database (this WIPES it), run locally with its URL:
  DATABASE_URL="postgresql://..." SEED_ADMIN_PASSWORD="<strong password>" python -m app.seed --yes

Demo accounts (password for buyers/suppliers: demo1234):
  admin@rfq.example.com      admin  (password: SEED_ADMIN_PASSWORD, or demo1234 on local SQLite)
  sales@forgeline.example.com, sales@apexvalves.example.com, orders@nordpoly.example.com   suppliers
  procurement@kestrel.example.com, buying@meridian.example.com, ops@halcyon.example.com    buyers
"""
import argparse
import os
import random
import sys
from datetime import date, datetime, timedelta

from .auth import hash_password
from .database import Base, SessionLocal, engine, is_sqlite
from . import models
from .scoring import apply_score, retrain

PASSWORD = "demo1234"

SUPPLIERS = [
    ("Ravi Menon", "Forgeline Metals", "sales@forgeline.example.com", [
        ("Hex Bolt M12 x 60", "Fasteners", "Stainless Steel 304", 0.42, "piece", "Fully threaded, DIN 933, A2-70."),
        ("Flat Washer M12", "Fasteners", "Stainless Steel 304", 0.06, "piece", "DIN 125A, bright finish."),
        ("Weld Neck Flange 4\" #150", "Pipe Fittings", "Carbon Steel A105", 38.5, "piece", "ASME B16.5, RF face."),
        ("Seamless Pipe 2\" SCH40", "Pipes", "Carbon Steel A106", 21.0, "metre", "Mill test certificate EN 10204 3.1."),
        ("Round Bar 50mm", "Raw Material", "Alloy Steel EN19", 3.1, "kg", "Hardened and tempered, cut to length."),
    ]),
    ("Elena Duarte", "Apex Valves & Controls", "sales@apexvalves.example.com", [
        ("Ball Valve 2\" Full Bore", "Valves", "Stainless Steel 316", 64.0, "piece", "3-piece body, ISO 5211 mounting pad."),
        ("Gate Valve 6\" Class 300", "Valves", "Carbon Steel WCB", 410.0, "piece", "API 600, bolted bonnet."),
        ("Pneumatic Actuator DA-105", "Automation", "Aluminium", 185.0, "piece", "Double acting, NAMUR interface."),
        ("Pressure Gauge 100mm 0–16 bar", "Instrumentation", "Stainless Steel 316", 27.5, "piece", "Glycerine filled, bottom entry."),
    ]),
    ("Tomas Lindqvist", "Nordpoly Industrial", "orders@nordpoly.example.com", [
        ("PTFE Gasket Sheet 3mm", "Sealing", "PTFE", 46.0, "sheet", "1500 x 1500 mm, virgin grade."),
        ("O-Ring Kit Metric 382pc", "Sealing", "NBR 70", 32.0, "kit", "30 sizes in a compartment case."),
        ("HDPE Pipe 110mm PN10", "Pipes", "HDPE PE100", 6.8, "metre", "Water and gas grade, 6m lengths."),
        ("Conveyor Belt EP400/3", "Material Handling", "Rubber", 58.0, "metre", "Abrasion resistant cover, 800 mm wide."),
    ]),
]

BUYERS = [
    ("Priya Natarajan", "Kestrel Engineering", "procurement@kestrel.example.com"),
    ("Daniel Okafor", "Meridian Process Plants", "buying@meridian.example.com"),
    ("Sofia Brandt", "Halcyon Water Systems", "ops@halcyon.example.com"),
]

# Logins advertised on the public sign-in page. They can't edit the catalogue (see routers/products.py).
DEMO_EMAILS = frozenset([e for _, _, e, _ in SUPPLIERS] + [e for _, _, e in BUYERS])

MESSAGES = [
    "",
    "Please quote best price.",
    "Need for a plant shutdown. Please include test certificates and packing details.",
    "Recurring requirement every quarter. Quote for this lot and indicate price for 2x volume. Delivery to Pune warehouse, DAP terms.",
    "Urgent replacement for a running line. Material certificates mandatory, third-party inspection by TUV. Please confirm stock availability and dispatch time.",
    "Budgetary quote for a tender.",
]


def run(reset: bool = True, admin_password: str = PASSWORD) -> None:
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    rnd = random.Random(42)
    db = SessionLocal()
    pw = hash_password(PASSWORD)

    db.add(models.User(name="Portal Admin", company="RFQ Portal", email="admin@rfq.example.com",
                       password_hash=hash_password(admin_password), role="admin"))
    products: list[models.Product] = []
    suppliers: list[models.User] = []
    for name, company, email, items in SUPPLIERS:
        s = models.User(name=name, company=company, email=email, password_hash=pw, role="supplier")
        db.add(s)
        db.flush()
        suppliers.append(s)
        for pname, cat, mat, price, unit, desc in items:
            p = models.Product(supplier_id=s.id, name=pname, category=cat, material=mat, unit_price=price, unit=unit, description=desc)
            db.add(p)
            products.append(p)
    buyers = [models.User(name=n, company=c, email=e, password_hash=pw, role="buyer") for n, c, e in BUYERS]
    db.add_all(buyers)
    db.flush()

    # ~45 enquiries spread over the last 6 months; older ones are mostly closed.
    now = datetime.utcnow()
    for i in range(45):
        age = rnd.randint(0, 175)
        created = now - timedelta(days=age, hours=rnd.randint(0, 23))
        p = rnd.choice(products)
        qty = int(rnd.lognormvariate(7.5, 0.8)) if p.unit_price < 10 else int(rnd.lognormvariate(3.8, 0.8)) + 5
        qty = max(10, round(qty, -1))
        deadline = created.date() + timedelta(days=rnd.randint(5, 90)) if rnd.random() < 0.7 else None
        e = models.Enquiry(
            buyer_id=rnd.choice(buyers).id, product_id=p.id, quantity=qty, required_by=deadline,
            message=rnd.choice(MESSAGES), created_at=created,
        )
        db.add(e)
        db.flush()
        apply_score(db, e, p, today=created.date())

        if (age > 10 and rnd.random() < 0.9) or rnd.random() < 0.25:
            e.quotations.append(models.Quotation(
                price_per_unit=round(p.unit_price * rnd.uniform(0.88, 1.05), 2),
                delivery_days=rnd.choice([7, 10, 14, 21, 30]),
                notes=rnd.choice(["Ex-works, packing included.", "Price valid 30 days.", "Includes MTC 3.1.", ""]),
                created_at=created + timedelta(days=rnd.randint(1, 3)),
            ))
            e.status = "quoted"
            if age > 30:
                # Higher-scored leads close as won more often, so retraining has a real signal.
                e.status = "won" if rnd.random() < 0.05 + e.lead_score / 160 else "lost"
    db.commit()
    # Train on the seeded outcomes and store the model in the DB, so hosted instances use it.
    info = retrain(db)
    db.close()
    print(f"Seeded {len(products)} products, {len(buyers)} buyers, {len(suppliers)} suppliers, 45 enquiries.")
    print(f"Lead model trained: AUC {info['auc']} on {info['training_rows']} rows ({info['real_outcomes']} real outcomes).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Wipe the database and load demo data.")
    parser.add_argument("--yes", action="store_true", help="confirm wiping a non-SQLite database")
    args = parser.parse_args()

    target = engine.url.render_as_string(hide_password=True)
    admin_password = os.getenv("SEED_ADMIN_PASSWORD")
    if not is_sqlite:
        if not args.yes:
            sys.exit(f"Refusing to wipe {target} without --yes.")
        # The demo login page advertises demo1234, so a hosted admin must get its own password.
        if not admin_password or len(admin_password) < 12:
            sys.exit("Set SEED_ADMIN_PASSWORD (12+ characters) to seed a hosted database.")
    print(f"Seeding {target} ...")
    run(admin_password=admin_password or PASSWORD)


if __name__ == "__main__":
    main()
