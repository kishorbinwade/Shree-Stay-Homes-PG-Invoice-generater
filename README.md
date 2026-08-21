# Shree Stay Homes & PG — Billing & Invoice Generator

A complete, **offline-first**, **privacy-first** PG billing & invoicing application for **SHREE STAY HOMES & PG** (PG Accommodation & Stay Services).

Create invoices → automatic billing calculations in ₹ INR → watermarked A4 PDF → download / print → email to owner (and optionally tenant) → invoice history → backup & restore.

> **MongoDB is not required. No cloud database. No public hosting.** All billing and tenant data is stored in a **local SQLite database** (`backend/data/pg_billing.db`) on your computer. Internet is needed **only** for sending email via Gmail SMTP.

---

## Architecture

```
Linux PC
├── React frontend  →  http://localhost:3000
│
└── FastAPI backend  →  http://127.0.0.1:8001
       ├── SQLite  →  backend/data/pg_billing.db   (all billing data)
       └── Gmail SMTP  →  only when sending invoice emails
```

- The backend binds to **127.0.0.1** by default (local-only) and CORS allows only `http://localhost:3000`.
- The backend stores **no secrets in SQLite** — the Gmail App Password lives only in `backend/.env` (git-ignored).
- Everything works **offline** (create/edit/search/calculate/history/PDF/download/print). Only email needs internet.

---

## Features

- **Dashboard** — total invoices, billed, collected, pending; current-month values; occupancy, overdue amount, food orders today, monthly expenses & net profit; 6-month billed-vs-collected chart; recent invoices
- **Monthly Billing** — generate invoices for all active tenants at once: rent, actual food consumption (from food orders), electricity, maintenance, auto-carried previous balance, discount; editable preview before generating; duplicate monthly invoices for the same tenant + month are prevented
- **Overdue Tracking** — due-date-based buckets: Overdue (with days overdue), Due Today, Upcoming, with pending amounts
- **WhatsApp Payment Reminders** — opens WhatsApp with a pre-filled message (invoice, totals, due date) to the tenant's mobile. No WhatsApp API/server; the owner taps send
- **Food Orders (on-demand)** — Breakfast/Lunch/Dinner per tenant (quantity, price, status: Ordered/Served/Cancelled); today's-meals dashboard with date filter; daily orders → monthly food total → automatically billed in Monthly Billing; cancelled orders never billed
- **Expenses & Profit** — categorized expenses; monthly/date-range reports: revenue, expenses, Net Profit = Revenue − Expenses; food revenue vs food expense vs food profit; CSV export
- **Google Forms CSV Import** — no Google API needed: download form responses as CSV → auto column detection & field mapping (manual override per column) → validated preview (new/duplicate/invalid) → import into local SQLite. Duplicate protection by mobile/email with explicit Skip or Update-Existing (shows exact field changes first). Import history stored with per-row details. Imported tenants start as "Pending Admission" until room/bed/rent are assigned
- **Create Invoice** — tenant details, room/bed, check-in/out, itemized charges (rent, deposit, electricity, food, maintenance, other, discount, previous balance); instant Subtotal → Discount → Total → Paid → Balance; auto payment status; advance-payment guard
- **Sequential invoice numbers** — `SHPG-2026-0001`, `0002`, … allocated atomically inside a SQLite transaction (`BEGIN IMMEDIATE`), so numbers never duplicate — even across restarts or restores
- **Watermarked PDF** — professional A4 invoice (logo, address, GSTIN, itemized charges, payment details, authorized signature) with embedded diagonal watermark + footer on every page; multi-page; ₹ glyph embedded; generated locally in the browser
- **Email via Gmail SMTP** — every invoice PDF is emailed to the owner (`shreehomestaypg@gmail.com`) by default; optional tenant copy; real PDF attachment; per-recipient status with retry; clear errors for auth failure / no internet
- **Invoice History** — server-side search (tenant / invoice no), month & status filters, date sorting; view, download, print, resend email, WhatsApp reminder, duplicate, edit (same number), delete with confirmation
- **Tenants & Rooms/Beds** — tenant profiles with aggregates; room/bed/rent/deposit/joining assignment; Pending Admission → Active workflow
- **Payments** — payment ledger across invoices (mode, transaction ID/UTR, balances)
- **Settings** — business info, logo & signature upload, owner email, email toggles, invoice prefix & starting number, terms, notes, watermark text — stored in SQLite
- **Backup & Restore** — export everything as JSON (invoices, tenants, expenses, food orders, import history, settings, sequences) or invoices as CSV; validated merge-import (existing records never silently overwritten; duplicates skipped; numbering sequence preserved); Delete All Data behind a strong confirmation
- **PWA / Offline** — installable app shell, service-worker caching, offline indicator; everything except Gmail email works offline

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Tailwind CSS, shadcn/ui, recharts, framer-motion |
| Backend | FastAPI (REST API + email) |
| Database | SQLite via Python's built-in `sqlite3` (WAL mode) — file at `backend/data/pg_billing.db` |
| PDF | jsPDF + jspdf-autotable in the browser (embedded subset font with ₹ glyph) |
| Email | Gmail SMTP (STARTTLS, port 587) via stdlib `smtplib` — real PDF attachment |

---

## Run Locally (Linux)

### Prerequisites

- **Python 3.10+** with venv support (`sudo apt install python3 python3-venv`)
- **Node.js 18+** and **yarn** (`npm install -g yarn`) — or npm
- **No database server to install** — SQLite is built into Python

### Quick start

```bash
git clone https://github.com/kishorbinwade/Shree-Stay-Homes-PG-Invoice-generater.git
cd Shree-Stay-Homes-PG-Invoice-generater
./scripts/run-local.sh
```

Then open **http://localhost:3000**

The script:
1. Creates `backend/.env` and `frontend/.env` from the `.env.example` templates (first run only)
2. Creates a Python virtual environment and installs backend dependencies
3. Creates `backend/data/` and starts FastAPI on **127.0.0.1:8001** (SQLite auto-initializes)
4. Installs frontend dependencies and starts React on **port 3000**

Stop both with `Ctrl+C`.

### Manual start (alternative)

```bash
# Terminal 1 — backend
cd backend
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --host 127.0.0.1 --port 8001

# Terminal 2 — frontend
cd frontend
cp .env.example .env
yarn install && yarn start        # http://localhost:3000
```

---

## Configuration

### `frontend/.env`

| Key | Purpose | Local value |
|---|---|---|
| `REACT_APP_BACKEND_URL` | Where the local API is reachable | `http://localhost:8001` |

### `backend/.env` (never committed — git-ignored)

| Key | Purpose |
|---|---|
| `SMTP_USER` | Your Gmail address (`shreehomestaypg@gmail.com`) — **required for email** |
| `SMTP_APP_PASSWORD` | Gmail **App Password** — **required for email** |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_TLS` | `smtp.gmail.com` / `587` / `true` |
| `EMAIL_FROM_NAME` | Sender display name (`Shree Stay Homes & PG`) |
| `EMAIL_REPLY_TO` | Reply-to inbox |
| `CORS_ORIGINS` | `http://localhost:3000` |

### Email configuration (Gmail SMTP)

1. On the Google account, turn on **2-Step Verification**: https://myaccount.google.com/security
2. Create an **App Password**: https://myaccount.google.com/apppasswords
3. Put both values in `backend/.env`:
   ```
   SMTP_USER=shreehomestaypg@gmail.com
   SMTP_APP_PASSWORD=xxxx xxxx xxxx xxxx
   ```
4. Restart the backend.

The App Password is **never** sent to the React frontend, never stored in SQLite, never logged, and never committed to GitHub. Until SMTP is configured, email sends return a clear "not configured" message and the UI offers **Retry Email** — invoicing, PDF, history and backup are unaffected.

---

## Data, Backup & Safety

- **Database file:** `backend/data/pg_billing.db` — created automatically, git-ignored (`backend/data/`, `*.db`).
- **Recommended backup:** use the app's **Backup & Restore** page → Export JSON (portable, validated on restore, preserves invoice numbering).
- **Manual backup:** you can also simply copy `backend/data/pg_billing.db` somewhere safe while the app is stopped.
- **Restore** merges by invoice number — existing records are skipped, never silently overwritten; a confirmation dialog is shown first.
- **Migration:** upgrading from the old browser-storage (IndexedDB) version — legacy browser data is simply discarded on first load. If you need it, export a JSON backup from the old version first.

## API Overview (local only)

```
GET    /api/invoices?q=&month=&status=&order=     list / search / filter / sort
POST   /api/invoices                              create (atomic sequential number)
GET    /api/invoices/next-number                  preview next number
GET    /api/invoices/overdue                      overdue / due-today / upcoming buckets
GET    /api/invoices/{id}                         fetch one
PUT    /api/invoices/{id}                         update (number never changes)
DELETE /api/invoices/{id}                         delete
GET    /api/tenants  /api/tenants/{id}            list / fetch
PUT    /api/tenants/{id}                          assign room/bed/rent/status
DELETE /api/tenants/{id}                          remove (invoices kept)
GET    /api/billing/preview?month=                per-tenant monthly billing preview
POST   /api/billing/generate                      bulk-generate monthly invoices
GET    /api/food-orders?date=|month=              food orders
POST/PUT/DELETE /api/food-orders[/{id}]           food order CRUD
GET    /api/food-orders/today?date=               today's meals by type
GET    /api/food-orders/summary?month=            monthly food totals per tenant
GET    /api/expenses?month=|dateFrom=|dateTo=     expenses
POST/DELETE /api/expenses[/{id}]                  expense CRUD
GET    /api/reports/monthly                       revenue / expenses / net profit / food
GET    /api/dashboard/stats                       dashboard aggregates
POST   /api/imports/preview                       parse CSV + auto-map + validate
POST   /api/imports/commit                        import with duplicate decisions
GET    /api/imports                               import history
GET    /api/settings   PUT /api/settings          settings in SQLite
GET    /api/backup/export                         full JSON backup download
GET    /api/backup/export.csv                     invoices CSV download
POST   /api/backup/import?mode=merge|overwrite    validated restore
DELETE /api/data                                  wipe all (confirmed in UI)
POST   /api/email/invoice                         Gmail SMTP send with PDF
```

## Project Structure

```
├── backend/
│   ├── server.py            # FastAPI — REST API + Gmail SMTP email
│   ├── database.py          # SQLite layer (schema, CRUD, sequences, backup)
│   ├── data/                # pg_billing.db lives here (git-ignored, auto-created)
│   ├── tests/               # hermetic pytest suite (temp DB)
│   └── .env.example
├── frontend/
│   ├── public/              # sw.js (offline shell), manifest.json, icons
│   └── src/
│       ├── pages/           # Dashboard, CreateInvoice, History, Tenants, Settings, Backup
│       ├── components/      # Layout, InvoicePreview, MigrationPrompt, shadcn ui/
│       ├── lib/             # api.js (REST client), pdf.js, db.js (legacy IDB read for migration)
│       └── fonts/           # subset TTF embedded in PDFs (₹ support)
├── scripts/
│   ├── run-local.sh         # one-command Linux startup
│   └── test_smtp_server.py  # local SMTP sink for email testing
└── README.md
```

## Security & Privacy

- Local-only: backend binds `127.0.0.1`; CORS restricted to `http://localhost:3000`; no public exposure of the API or the SQLite file
- No secrets in frontend code, IndexedDB, SQLite, API responses, logs, or git
- Invoice numbers are allocated inside SQLite transactions — duplicates are impossible even across restarts
- Input validation on both client and server (negative amounts, emails, required fields)
