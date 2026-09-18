# PRD — Shree Stay Homes & PG: Billing & Invoice Generator

## Original Problem Statement
Production-ready PG Billing & Invoice Generator for "SHREE STAY HOMES & PG" (PG Accommodation & Stay Services). Fully functional app: create invoices, auto-calculate billing, generate secure watermarked A4 PDFs, download/print, store records locally on the owner's device (IndexedDB, no cloud DB), email invoices to owner (default shreehomestaypg@gmail.com) and optionally tenant, invoice history, dashboard stats, backup/restore (JSON/CSV), settings (branding, logo/signature upload, invoice numbering, watermark), offline-first PWA, validation, INR formatting, sequential invoice numbers (SHPG-YYYY-NNNN).

## User Choices
- Email: Resend (Emergent-managed proxy, no user API key) via FastAPI backend `POST /api/email/invoice` with base64 PDF attachment.
- Logo/Signature: owner uploads own images in Settings (FileReader → dataURL → IndexedDB).
- Stack defaults: React + FastAPI + IndexedDB (idb) + jsPDF, offline-first PWA.

## Architecture
- Frontend: React 19 + Tailwind + shadcn/ui, terracotta/stone design system (Manrope + IBM Plex Sans). Service worker (`/sw.js`, network-first) + manifest.json for PWA/offline shell. All data in IndexedDB `shree-stay-pg-db` (stores: invoices, tenants, kv[settings, seq-YYYY]).
- PDF: client-side jsPDF + autotable, embedded subset FreeSans TTFs (incl. ₹ glyph) at `src/fonts/pdfFonts.js`, diagonal low-opacity watermark + footer on every page, multi-page safe. Filename `ShreeStayHomesPG_Invoice_<No>.pdf`.
- Backend: FastAPI, email-only. Managed Resend proxy (EMERGENT_EMAIL_KEY in backend/.env only, never frontend), fixed server-side HTML template, escaped interpolation, guardrail gate (`_assert_safe_email`), per-recipient status. MongoDB connected (platform requirement) but NOT used for tenant data (privacy).
- No authentication — single-owner local app.

## User Personas
- PG Owner (single user): creates monthly invoices, downloads/prints, emails, backs up data.

## Implemented (2026-08-20)
- Dashboard: stat cards (invoices/billed/collected/pending + current-month), 6-month Billed vs Collected chart (recharts), recent invoices, empty states.
- Create Invoice: full form (invoice/tenant/charges/payment), live INR summary + auto payment status, validation (mobile, email, dates, negatives, discount>subtotal, paid>total w/ advance override), duplicate-safe numbering, success panel with per-recipient email status + Retry Email.
- Invoice History: search, month/status filters, sort, view preview modal, download, print, resend email, duplicate, edit (keeps number), delete w/ confirm.
- Tenants: auto-upserted from invoices, aggregates (billed/pending), prefill new invoice, remove tenant.
- Settings: PG info, logo/signature upload+preview, email config (owner email, auto-owner toggle, tenant option toggle), invoice prefix/start number, terms, notes, watermark text.
- Backup & Restore: JSON export/import (merge + seq recompute), CSV export, Delete All Local Data with strong warning dialog.
- Email: owner auto-email on generate; tenant optional; resend from history; verified delivering with PDF attachment.
- Offline: service worker + IndexedDB; offline indicator badge; everything except email works offline.

## Bugs Fixed During Development
- 422 on email when Amount Paid blank → numeric coercion before save/send (CreateInvoice.jsx, lib/api.js).
- Font bloat → subset FreeSans (46KB) embedded for ₹ support in PDF.
- PostHog snippet mis-transcription (`g(u, o[n])`) caused pageerrors → fixed.
- monthLabel hardened for non-string input.

## Implemented (2026-08-20, continued)
- Local/self-hosted readiness: `.env.example` templates (backend + frontend), `scripts/run-local.sh` one-command Linux startup (venv + uvicorn :8001, yarn start :3000), `REACT_APP_BACKEND_URL` falls back to `http://localhost:8001` when unset, README with full local setup guide. App runs fully on localhost without public hosting; email is the only internet-dependent feature and fails gracefully with Retry.

- GitHub-ready README.md: features, tech stack table, one-command + manual local run steps, config tables, project structure, security/privacy notes.

## Implemented (2026-08-20, MongoDB removal + email attachment fix)
- MongoDB fully removed: server.py has no motor/pymongo/MONGO_URL/DB_NAME; requirements.txt minimized (fastapi, uvicorn, httpx, python-dotenv, pydantic, email-validator); backend/.env and .env.example contain only email/CORS/SMTP keys; .gitignore ignores .env* but commits .env.example (`!.env.example`). Backend verified to import/start with no Mongo env or process.
- Email attachment bug root cause: managed proxy silently drops `attachments` (invalid base64 still 202). Fix: Gmail SMTP path (SMTP_USER/SMTP_APP_PASSWORD in backend/.env, stdlib smtplib + STARTTLS, PDF attached via MIMEApplication, run in asyncio.to_thread) used when configured; managed proxy otherwise with response `attachment:false`; frontend shows a warning toast when an email goes without the PDF. SMTP not configured in this pod (needs user's Gmail App Password).

- Stopped the leftover `mongod` supervisor process; backend + frontend + email all verified working with no MongoDB running. Testing agent iteration_2: all flows pass (7/7 backend tests; only env-level note is managed-proxy 429 rate limiting under rapid repeated sends, surfaced correctly via Retry Email).

- Git fix (commit 2848fae): backend/.env.example + frontend/.env.example committed; .gitignore ignores real .env but tracks .env.example (`!.env.example`); no secrets in history (testing agent iteration_3 verified: fresh-clone cp steps work, ls-tree shows only the two example files, ek_ key absent from history). Push to GitHub (github.com/kishorbinwade/Shree-Stay-Homes-PG-Invoice-generater) must be done by the user via Emergent UI: Save → Save to GitHub (pod has no git credentials; origin remote already added).

- Gmail SMTP became the ONLY email path (managed proxy removed entirely). Fixed two real bugs found via a local aiosmtpd sink: (1) `starttls(context)` positional → `starttls(context=context)` (the reported crash); (2) single-line HTML template exceeded RFC5321 998-char line limit → SMTPDataError "Line too long" — fixed with `MIMEText(html, "html", "utf-8")` (base64 CTE). Verified end-to-end against the sink: owner+tenant messages received with byte-identical PDF attachments; auth/connection errors map to clear messages (smtp_error_message); SMTP_TLS flag added for local testing; 503 with clear detail when SMTP not configured. scripts/test_smtp_server.py kept as a reusable local test harness.

- SMTP fix committed as c3fee10; testing agent iteration_4 passed 100% (starttls keyword fix, utf-8 MIMEText, 503-when-unconfigured, error mapping, invoice-save-unaffected-by-email-failure, zero pageerrors). Push to GitHub pending user action via Emergent Save → Save to GitHub (pod holds no git credentials).

## Implemented (2026-08-21, IndexedDB → SQLite migration)
- Primary storage is now SQLite (`backend/data/pg_billing.db`, WAL) via `backend/database.py`; FastAPI REST API for invoices/tenants/settings/backup/migrate; invoice numbers allocated atomically server-side (BEGIN IMMEDIATE). Frontend `lib/api.js` replaces IndexedDB; legacy IndexedDB is auto-deleted on first load (owner-approved, no migration prompt). run-local.sh binds 127.0.0.1; .gitignore covers backend/data/ and *.db. Backend pytest: 16 hermetic tests pass. Committed as c3fee10→(sqlite commit).

## Implemented (2026-08-21, feature modules)
- Monthly Billing (bulk preview/generate, food-order totals, carried previous balance, tenant+month duplicate prevention), Overdue tracking (buckets + days overdue), WhatsApp wa.me reminders (no API), Expenses + monthly/date-range reports (net profit, food profit), on-demand Food Orders (today dashboard, monthly aggregation → billing), Google Forms CSV import (auto-map incl. owner's real form columns, preview, duplicate Skip/Update with field diff, import history), Rooms & Beds assignment (Pending Admission default), Payments ledger, extended dashboard stats. Backup JSON now includes expenses/foodOrders/imports. 24 backend tests pass; committed 7c02043.

- Testing agent iteration_6: 100% pass on all new modules (billing bulk-generate + duplicate prevention, food cancel exclusion, CSV import/duplicate/update flows, reports math, WhatsApp link format, backup keys, dashboard cards, 0 pageerrors on 14 routes). Push to GitHub pending user action (Emergent Save → Save to GitHub).

## Backlog / Next Tasks
- P0: none blocking.
- P1: Verify PDF visual layout edge cases (very long tenant names/addresses) with document render check; silence recharts ResponsiveContainer width(-1) warning on first mount.
- P2: Per-year invoice sequence reset UI; GST % field if owner registers GSTIN; tenant ledger view; WhatsApp share of PDF; dark print stylesheet for HTML preview.

## 2026-06 (fork) — Preview backend connectivity fix
- Root cause of "Cannot reach the local backend (http://localhost:8001)" banner in the preview: `frontend/.env` and `backend/.env` were absent in the pod (gitignored), so the browser fell back to `localhost:8001` (unreachable from the preview URL) and CORS only allowed `http://localhost:3000`.
- Fix: created `frontend/.env` (REACT_APP_BACKEND_URL = preview URL) and `backend/.env` from the examples with the preview origin added to CORS_ORIGINS. No source code changed. Verified: banner gone on Dashboard/History, GET+PUT via preview return 200.
- Note: .env files are gitignored; on a fresh pod they must be recreated from `.env.example`. Local runs still use `http://localhost:8001` fallback.
