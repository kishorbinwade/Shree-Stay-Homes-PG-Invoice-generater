# Multiple payments / owner + CC implementation

## Scope
Personal, single-owner localhost application. Architecture unchanged: React → FastAPI → existing SQLite file; Gmail SMTP backend-only. No IndexedDB, additional runtime database, authentication service, hosting/deployment checks, or real email sends in tests.

## Database
- `payment_store.py` creates `payments` with `id`, `invoice_id`, unique `receipt_number`, `payment_date`, positive `amount`, `payment_method`, `reference`, `notes`, `date_inferred`, and UTC creation/update timestamps.
- `invoice_id` references existing invoices with `ON DELETE CASCADE`. Each connection enables SQLite foreign keys. Payment writes use `BEGIN IMMEDIATE` and the existing lock; money comparisons/sums use integer paise internally.
- One-time `meta['payments-v1']` migration preserves existing recorded Amount Paid as one labelled migrated payment per paid invoice. Historical payment date is inferred from invoice date (flagged visibly). Unpaid invoices get no synthetic payments. Existing invoice IDs, numbers, and bill amounts remain unchanged.
- Original invoice charge fields cannot be modified via subsequent invoice updates. Legacy API increases to Amount Paid append a payment; decreasing it requires individual payment edit/delete. New Record Payment always rejects overpayment. The existing explicit initial-invoice Allow Advance remains supported, and old credits are retained separately as `creditBalance` rather than a negative balance due.
- `amountPaid`, `balanceDue`, `paymentStatus` remain compatible fields derived from payment records. Responses also add `invoice_total`, `total_paid`, `balance_due`, `payment_status` (UNPAID/PARTIALLY PAID/PAID), and `payments`.
- JSON backup version 4 includes payment records and receipts; legacy backups synthesize labelled prior payments; merge avoids duplicates. Deleting an invoice cascades its payments, not other invoices.

## API
- POST/GET `/api/payments`
- GET `/api/invoices/{invoice_id}/payments`
- PUT/DELETE `/api/payments/{payment_id}`
- GET `/api/payments/{payment_id}/receipt`
- Invoice create/get/list/update/export now integrate the ledger without changing invoice numbering.
- Reports preserve their existing invoice billing-month/date-period definitions; received revenue uses ledger-derived Amount Paid for those invoices. Food profit retains its existing billed-food definition. Overdue and monthly carry-forward use the derived remaining balance. Tenant ledger displays individually dated payments.

## Frontend / receipt
- `pages/InvoiceDetails.jsx`, route `/invoices/:id`: payment summary, record/edit/delete, dated payment history, receipt download, existing invoice preview/PDF/email.
- `components/PaymentForm.jsx`, `components/PaymentHistory.jsx`: validated form, remaining balance, confirmation for deletion, receipt download option; newest payment date first.
- `lib/receipt.js`: separate watermarked A4 payment receipt with unique receipt number, original invoice number/amount, prior/current/total paid, balance, date, method and status. Receipt is never an invoice. Receipt totals are recalculated from surviving records up to that payment's recorded creation order; correcting/deleting earlier payments updates subsequent receipt figures.
- History links and Record Payment action; Payments page lists each receipt/payment rather than one aggregate row per invoice. Create Invoice preserves original charges/total paid after save and links to Payments & Receipts. Initial payment has its own date.

## Owner + tenant CC email work (previous request, also awaiting full tests)
- Existing SMTP/TLS transport sends exactly one MIME message with owner To and invoice-snapshot tenant CC and one original watermarked invoice PDF. No empty CC; one envelope list, deduplicated if owner equals CC.
- Selected tenant ID resolves email from SQLite on new invoice save. Stored `tenantEmail` is immutable for existing invoice updates; resends never fetch mutable tenant profile email.
- Backend records delivery status without rewriting invoices/tenant profiles. Frontend no longer updates complete invoice just to save email status. Read-only recipient panel and checkbox; previous tenant's CC cleared immediately when a different selection is typed. Retry Email retained. SMTP credentials remain absent from frontend/database/responses.

## Files changed
Backend: `database.py`, `server.py`; new `payment_store.py`, `payment_routes.py`; test-only `requirements-test.txt`.
Frontend: `App.js`, `lib/api.js`, `lib/format.js`, `index.css`, `pages/CreateInvoice.jsx`, `pages/History.jsx`, `pages/Payments.jsx`, `pages/Settings.jsx`; new `pages/InvoiceDetails.jsx`, `components/PaymentForm.jsx`, `components/PaymentHistory.jsx`, `components/InvoiceEmailRecipients.jsx`, `lib/receipt.js`, `lib/emailStatus.js`.

## Verification
Pending testing-agent report. Main-agent checks are compilation and browser smoke only, not final verification. Required: all 8 payment scenarios, all 10 owner/CC cases, local SMTP receiver only, complete existing backend suite and affected frontend/regression flows. No real email or hosting-level tests.