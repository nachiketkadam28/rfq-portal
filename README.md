# RFQ Desk — Industrial B2B RFQ & CRM Portal

Buyers browse a parts catalogue and send requests for quotation (RFQs). Suppliers see incoming
requests ranked by an ML lead score, send priced quotes, and track win/loss. Admins see the whole
portal and can retrain the scoring model.

## Run it

Backend (FastAPI, SQLite by default; set `DATABASE_URL` for Postgres):

```bash
cd backend
venv\Scripts\python -m app.seed          # demo data (wipes the DB)
venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Frontend (React + Vite, proxies `/api` to port 8000):

```bash
cd frontend
npm install
npm run dev                               # http://localhost:5173
```

Demo accounts (password `demo1234`): `procurement@kestrel.example.com` (buyer),
`sales@forgeline.example.com` (supplier), `admin@rfq.example.com` (admin).

Tests: `cd backend && venv\Scripts\python -m pytest`

## Deploying (Vercel or any serverless host)

Backend environment variables:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Hosted Postgres (e.g. Neon). `postgres://` and `postgresql://` both work. SQLite cannot persist on serverless. |
| `SECRET_KEY` | Long random string for signing logins. |
| `CORS_ORIGINS` | Your frontend URL(s), comma-separated, e.g. `https://rfq-desk.vercel.app`. |
| `CORS_ORIGIN_REGEX` | Optional, for preview deploys, e.g. `https://rfq-desk-[\w-]+\.vercel\.app`. |

Seed the hosted database once, from your machine (this wipes it):

```bash
cd backend
DATABASE_URL="postgresql://..." SEED_ADMIN_PASSWORD="a-long-password" venv/Scripts/python -m app.seed --yes
```

The lead model never writes to disk at runtime: the bundled `ml/lead_model.joblib` is used until an
admin retrains, and retrained models are stored in the `model_versions` table so every instance
picks them up.

## API

| Method | Path | Who |
|---|---|---|
| POST | `/api/auth/register`, `/api/auth/login` | anyone |
| GET | `/api/auth/me` | signed in |
| GET | `/api/products?q&category&material&min_price&max_price`, `/api/products/facets`, `/api/products/{id}` | anyone |
| GET | `/api/products/mine` | supplier |
| POST / PUT / DELETE | `/api/products[/{id}]` | owning supplier (admin may edit/delete) |
| POST | `/api/enquiries` | buyer |
| GET | `/api/enquiries?status&sort=score\|recent`, `/api/enquiries/{id}` | buyer (own), supplier (on own products), admin (all) |
| POST | `/api/enquiries/{id}/quotations` | owning supplier |
| PATCH | `/api/enquiries/{id}/status` (`won`/`lost`) | buyer accepts/declines, supplier records outcome |
| GET | `/api/dashboard` | role-aware summary |
| GET | `/api/admin/users`, POST `/api/admin/model/retrain` | admin |

## Lead scoring

`backend/ml/lead_model.py` is a scaled logistic regression over order value, quantity, deadline
presence and urgency, request detail, and the buyer's history. It starts from synthetic data;
retraining mixes in every won/lost enquiry and rescores open ones. Each score stores its top three
feature contributions, which the supplier sees as "what moved the score". Buyers never see scores.
