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

## Backlog / Next Tasks
- P0: none blocking.
- P1: Verify PDF visual layout edge cases (very long tenant names/addresses) with document render check; silence recharts ResponsiveContainer width(-1) warning on first mount.
- P2: Per-year invoice sequence reset UI; GST % field if owner registers GSTIN; tenant ledger view; WhatsApp share of PDF; dark print stylesheet for HTML preview.
