# Shree Stay Homes & PG — Billing & Invoice Generator

A complete, offline-first PG billing application for **SHREE STAY HOMES & PG** (PG Accommodation & Stay Services).

Create invoices → automatic billing calculations (₹ INR) → watermarked A4 PDF → download/print → emailed to the owner (and optionally the tenant) → stored in Invoice History → backup/restore.

## Privacy-first, local-first

- All invoices, tenants and settings are stored in the **browser's IndexedDB on the owner's device** — never in a cloud database.
- Works **offline** for everything except sending email (create/edit invoices, calculations, history, PDF generation, download, print).
- The backend is used **only** for delivering invoice emails.

## Run locally on Linux (no public hosting required)

### Prerequisites
- Python 3.10+ with `python3-venv`
- Node.js 18+ and yarn (or npm)

### Quick start

```bash
./scripts/run-local.sh
```

Then open **http://localhost:3000**

The script creates `.env` files from the provided templates on first run, installs dependencies, starts the API on port **8001** and the web app on port **3000**. Stop with `Ctrl+C`.

### Manual start (alternative)

```bash
# Backend (terminal 1)
cd backend
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001

# Frontend (terminal 2)
cd frontend
cp .env.example .env        # points REACT_APP_BACKEND_URL to http://localhost:8001
yarn install
yarn start                  # serves http://localhost:3000
```

## Configuration

### `frontend/.env`
| Key | Purpose | Local value |
|---|---|---|
| `REACT_APP_BACKEND_URL` | Where the email API lives | `http://localhost:8001` |

### `backend/.env`
| Key | Purpose |
|---|---|
| `EMERGENT_EMAIL_KEY` | Managed email delivery key (keep the value shipped in the deployed `.env`; email needs internet) |
| `EMAIL_FROM_NAME` | Sender display name: `Shree Stay Homes & PG` |
| `EMAIL_REPLY_TO` | Reply-to inbox (default `shreehomestaypg@gmail.com`) |
| `MONGO_URL` / `DB_NAME` | Not used for billing data (privacy); the backend starts fine even if MongoDB is not running |

**Email note:** invoice emails are sent through a managed email proxy and require an internet connection. Without it (or without a key), everything else works — the app shows "Email failed" with a **Retry Email** button, and PDF download/print is unaffected.

## Features

- **Dashboard** — total invoices, billed, collected, pending; current-month collection/pending; 6-month billed-vs-collected chart; recent invoices.
- **Create Invoice** — invoice/tenant/charges/payment sections; instant Subtotal → Discount → Total → Paid → Balance; auto payment status (Paid / Partially Paid / Pending); full validation (mobile, email, dates, negatives, advance-payment guard); sequential invoice numbers (`SHPG-2026-0001`, …) that never repeat and survive restarts.
- **PDF** — professional A4 invoice with logo, address, GSTIN, itemized charges, payment details, authorized signature; embedded diagonal `SHREE STAY HOMES & PG` watermark and footer on every page; multi-page support; filename `ShreeStayHomesPG_Invoice_<number>.pdf`.
- **Email** — owner receives every invoice PDF automatically; optional tenant copy via checkbox; per-recipient status (Sent / Failed / Tenant email not provided) with retry.
- **Invoice History** — search by tenant/invoice no, filter by month/status, sort by date; view, download, print, resend email, duplicate, edit (keeps the same invoice number), delete with confirmation.
- **Tenants** — auto-built from invoices with billed/pending aggregates; one-click new invoice prefilled for a tenant.
- **Settings** — business name/address/mobile/email/GSTIN, logo & signature upload, owner email, email toggles, invoice prefix & starting number, default terms/notes, watermark text. Stored locally.
- **Backup & Restore** — export everything as JSON, invoices as CSV; import/merge a JSON backup on another device; Delete All Local Data behind a strong confirmation dialog.
- **Offline/PWA** — installable app shell, service-worker caching, offline indicator.

## Tech stack

React 19 · Tailwind CSS · shadcn/ui · IndexedDB (`idb`) · jsPDF (embedded font with ₹ glyph) · FastAPI · managed email proxy (Resend)

## Project structure

```
backend/    FastAPI email API (server.py), requirements.txt, .env(.example)
frontend/   React app (src/pages, src/lib, src/components), PWA (public/sw.js, manifest.json)
scripts/    run-local.sh — one-command Linux startup
```
