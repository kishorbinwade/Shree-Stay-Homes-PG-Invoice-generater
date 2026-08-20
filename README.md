# Shree Stay Homes & PG — Billing & Invoice Generator

A complete, **offline-first**, **privacy-first** PG billing & invoicing application for **SHREE STAY HOMES & PG** (PG Accommodation & Stay Services).

Create invoices → automatic billing calculations in ₹ INR → watermarked A4 PDF → download / print → email to owner (and optionally tenant) → invoice history → backup & restore.

> **MongoDB is not required. Billing and tenant data are stored locally in IndexedDB.** The app is 100% local: the React frontend + browser IndexedDB hold all invoices, tenants, settings and history. The small FastAPI backend exists **only** for secure email delivery — it stores nothing.

---

## Architecture

```
Linux Computer
      │
      ├── React frontend  (http://localhost:3000)
      │      │
      │      └── IndexedDB  →  invoices / tenants / settings / history
      │
      └── FastAPI  (http://localhost:8001)
             │
             └── Internet
                   │
                   └── Email service (managed proxy, or your Gmail SMTP)
```

No cloud database. No public hosting required. Works offline for everything except sending email.

---

## Features

- **Dashboard** — total invoices, total billed, collected, pending; current-month collection & pending; 6-month billed-vs-collected chart; recent invoices
- **Create Invoice** — tenant details, room/bed, check-in/out, itemized charges (rent, deposit, electricity, food, maintenance, other, discount, previous balance); instant Subtotal → Discount → Total → Paid → Balance; auto payment status (Paid / Partially Paid / Pending); advance-payment guard
- **Sequential invoice numbers** — `SHPG-2026-0001`, `SHPG-2026-0002`, … auto-generated, never duplicated, sequence survives restarts
- **Watermarked PDF** — professional A4 invoice (logo, address, GSTIN, itemized charges, payment details, authorized signature) with an embedded diagonal `SHREE STAY HOMES & PG` watermark and footer on every page; multi-page support; ₹ glyph embedded in the PDF font
- **Email invoices** — PDF emailed to the owner (default `shreehomestaypg@gmail.com`); optional tenant copy via checkbox; per-recipient status (Sent / Failed / not provided) with retry; resend anytime from History
- **Invoice History** — search (tenant / invoice no), filter by month & payment status, sort by date; view, download, print, resend email, duplicate, edit (keeps the same number), delete with confirmation
- **Tenants** — auto-built from invoices with billed/pending aggregates; one-click prefilled new invoice
- **Settings** — business name, address, mobile, email, GSTIN, logo & signature upload, owner email, email toggles, invoice prefix & starting number, default terms/notes, watermark text
- **Backup & Restore** — export all data as JSON, invoices as CSV; import/merge a backup on another device; Delete All Local Data behind a strong confirmation dialog
- **PWA / Offline** — installable app shell, service-worker caching, offline indicator; works offline for everything except email

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, Tailwind CSS, shadcn/ui, recharts, framer-motion |
| Local DB | IndexedDB via `idb` (stores: invoices, tenants, settings, sequences) |
| PDF | jsPDF + jspdf-autotable (embedded subset font with ₹ glyph) |
| Backend | FastAPI (email delivery only — no database) |
| Email | Your own Gmail via SMTP (App Password) — real PDF attachment |

---

## Run Locally (Linux)

### Prerequisites

- **Python 3.10+** with venv support (`sudo apt install python3 python3-venv`)
- **Node.js 18+** and **yarn** (`npm install -g yarn`) — or npm
- **MongoDB is NOT required** — there is no database to install

### Option A — One command

```bash
git clone <your-repo-url> shree-stay-pg
cd shree-stay-pg
./scripts/run-local.sh
```

Then open **http://localhost:3000**

The script automatically:
1. Creates `backend/.env` and `frontend/.env` from the `.env.example` templates (first run only)
2. Creates a Python virtual environment and installs backend dependencies
3. Starts the FastAPI email API on **port 8001**
4. Installs frontend dependencies and starts the React app on **port 3000**

Stop everything with `Ctrl+C`.

### Option B — Manual (two terminals)

**Terminal 1 — backend:**
```bash
cd backend
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001
```

**Terminal 2 — frontend:**
```bash
cd frontend
cp .env.example .env      # points REACT_APP_BACKEND_URL to http://localhost:8001
yarn install              # or: npm install
yarn start                # or: npm start  →  http://localhost:3000
```

---

## Configuration

### `frontend/.env`

| Key | Purpose | Local value |
|---|---|---|
| `REACT_APP_BACKEND_URL` | Where the email API is reachable | `http://localhost:8001` |

### `backend/.env`

| Key | Purpose |
|---|---|
| `SMTP_USER` | Your Gmail address (e.g. `shreehomestaypg@gmail.com`) — **required for email** |
| `SMTP_APP_PASSWORD` | Gmail **App Password** — see below — **required for email** |
| `SMTP_HOST` / `SMTP_PORT` | Gmail SMTP server (`smtp.gmail.com` / `587`) |
| `EMAIL_FROM_NAME` | Sender display name (`Shree Stay Homes & PG`) |
| `EMAIL_REPLY_TO` | Reply-to inbox (default `shreehomestaypg@gmail.com`) |
| `CORS_ORIGINS` | Allowed frontend origin (`http://localhost:3000` locally) |

### Email configuration (Gmail SMTP)

Invoice emails are sent from **your own Gmail account** via SMTP, with the **invoice PDF attached** to every email:

1. On the Google account `shreehomestaypg@gmail.com`, turn on **2-Step Verification**: https://myaccount.google.com/security
2. Create an **App Password**: https://myaccount.google.com/apppasswords (name it e.g. "PG Billing")
3. Put both values in `backend/.env`:
   ```
   SMTP_USER=shreehomestaypg@gmail.com
   SMTP_APP_PASSWORD=xxxx xxxx xxxx xxxx
   ```
4. Restart the backend.

Until SMTP is configured, the email endpoint returns "not configured" and the app shows **Email failed** with a **Retry Email** button — invoice creation, PDF download and printing are never affected. The App Password stays only in `backend/.env` on your computer — never in the browser, IndexedDB, or git.

> **Email note:** sending email requires internet. Everything else (invoices, PDF, history, backup) works fully offline.

---

## Project Structure

```
├── backend/
│   ├── server.py            # FastAPI — POST /api/email/invoice (email only, no DB)
│   ├── requirements.txt     # fastapi, uvicorn, httpx, pydantic — that's all
│   └── .env.example
├── frontend/
│   ├── public/
│   │   ├── sw.js            # service worker (offline shell)
│   │   ├── manifest.json    # PWA manifest
│   │   └── icons/
│   ├── src/
│   │   ├── pages/           # Dashboard, CreateInvoice, History, Tenants, Settings, Backup
│   │   ├── components/      # Layout (sidebar), InvoicePreview, shadcn ui/
│   │   ├── lib/             # db.js (IndexedDB), pdf.js, api.js, backup.js, format.js
│   │   ├── context/         # SettingsContext
│   │   └── fonts/           # subset TTF embedded in PDFs (₹ support)
│   └── .env.example
├── scripts/
│   └── run-local.sh         # one-command Linux startup
└── README.md
```

## How It Works

1. Owner fills tenant details + charges → totals update instantly (₹ INR formatting)
2. **Generate Invoice** → unique number assigned → saved to IndexedDB → watermarked PDF built in the browser
3. PDF emailed to the owner; tenant copy if the checkbox is ticked
4. Owner can **Download** / **Print** the PDF anytime — fully offline
5. Everything is searchable in **Invoice History**; export JSON/CSV backups from **Backup & Restore**

## Security & Privacy

- No authentication needed — it's a single-owner local app
- No credentials, API keys or passwords in frontend code or browser storage; `.env` is git-ignored, only `.env.example` templates are committed
- Tenant data is never uploaded anywhere; it leaves the device only as an invoice email when the owner explicitly sends it
- No billing data is sent to or stored by the backend — it only relays the email
- Form validation, negative-amount prevention, duplicate-invoice-number protection, and confirmation dialogs for destructive actions
