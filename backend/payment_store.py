"""Payment ledger using the caller's existing SQLite connection and transaction."""
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
import uuid

METHODS = ("Cash", "UPI", "Bank Transfer", "Card", "Other")
SCHEMA = """
CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    receipt_number TEXT NOT NULL UNIQUE,
    payment_date TEXT NOT NULL,
    amount REAL NOT NULL CHECK(amount > 0),
    payment_method TEXT NOT NULL,
    reference TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    date_inferred INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_payments_invoice_date ON payments(invoice_id, payment_date);
"""


def now():
    return datetime.now(timezone.utc).isoformat()


def cents(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError("Amount must be a finite number")
        return int((number * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid payment amount")


def valid_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("Payment date must be a valid YYYY-MM-DD date")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError("Payment date must be a valid YYYY-MM-DD date")
    return value


def decode(row):
    return {"id": row["id"], "invoiceId": row["invoice_id"], "receiptNumber": row["receipt_number"],
            "paymentDate": row["payment_date"], "amount": row["amount"],
            "paymentMethod": row["payment_method"], "reference": row["reference"],
            "notes": row["notes"], "dateInferred": bool(row["date_inferred"]),
            "createdAt": row["created_at"], "updatedAt": row["updated_at"]}


def list_payments(conn, invoice_id=None):
    where, params = (" WHERE invoice_id=?", (invoice_id,)) if invoice_id else ("", ())
    return [decode(r) for r in conn.execute(
        "SELECT * FROM payments" + where + " ORDER BY payment_date DESC, created_at DESC, id DESC", params)]


def paid_cents(conn, invoice_id, exclude=None):
    return sum(cents(r["amount"]) for r in conn.execute(
        "SELECT id, amount FROM payments WHERE invoice_id=?", (invoice_id,)) if r["id"] != exclude)


def summary(total, paid):
    total, paid = cents(total), cents(paid)
    status = "UNPAID" if paid <= 0 else "PAID" if paid >= total else "PARTIALLY PAID"
    return {"invoice_total": total / 100, "total_paid": paid / 100,
            "balance_due": max(0, total - paid) / 100, "payment_status": status,
            "creditBalance": max(0, paid - total) / 100}


def sync_invoice(conn, invoice_id):
    inv = conn.execute("SELECT total FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    if not inv:
        raise LookupError("Invoice not found")
    paid = paid_cents(conn, invoice_id) / 100
    s = summary(inv["total"], paid)
    # Keep legacy fields/status values for existing billing, PDF and filter consumers.
    legacy = {"UNPAID": "Pending", "PAID": "Paid", "PARTIALLY PAID": "Partially Paid"}
    conn.execute("UPDATE invoices SET amount_paid=?, balance_due=?, payment_status=?, updated_at=? WHERE id=?",
                 (paid, s["balance_due"], legacy[s["payment_status"]], now(), invoice_id))
    return s


def insert(conn, invoice_id, data, *, allow_advance=False, restored=False):
    inv = conn.execute("SELECT total FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    if not inv:
        raise LookupError("Invoice not found")
    amount = cents(data.get("amount", 0))
    if amount <= 0:
        raise ValueError("Payment amount must be greater than zero")
    payment_date = valid_date(data.get("paymentDate"))
    method = data.get("paymentMethod") or "Cash"
    if method not in METHODS:
        raise ValueError("Invalid payment method")
    remaining = max(0, cents(inv["total"]) - paid_cents(conn, invoice_id))
    if amount > remaining and not allow_advance:
        raise ValueError(f"Payment cannot exceed the remaining balance of ₹{remaining / 100:g}.")
    pid = data.get("id") if restored else uuid.uuid4().hex
    stamp = now()
    receipt = data.get("receiptNumber") if restored else None
    receipt = receipt or f"RCPT-{payment_date[:4]}-{pid.upper()}"
    created = data.get("createdAt") if restored else None
    conn.execute("""INSERT INTO payments (id, invoice_id, receipt_number, payment_date,
        amount, payment_method, reference, notes, date_inferred, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (pid, invoice_id, receipt, payment_date, amount / 100,
        method, data.get("reference") or "", data.get("notes") or "", int(bool(data.get("dateInferred"))),
        created or stamp, data.get("updatedAt") if restored and data.get("updatedAt") else stamp))
    sync_invoice(conn, invoice_id)
    return decode(conn.execute("SELECT * FROM payments WHERE id=?", (pid,)).fetchone())


def legacy_payment(conn, inv):
    amount = float(inv.get("amountPaid") or 0)
    if cents(amount) <= 0:
        sync_invoice(conn, inv["id"])
        return
    value = inv.get("invoiceDate") or (inv.get("createdAt") or "")[:10]
    try:
        value = valid_date(value)
    except ValueError:
        value = date.today().isoformat()
    insert(conn, inv["id"], {"paymentDate": value, "amount": amount,
        "paymentMethod": inv.get("paymentMode") if inv.get("paymentMode") in METHODS else "Other",
        "reference": inv.get("transactionId") or "", "dateInferred": True,
        "notes": "Migrated existing payment. Payment date inferred from invoice; actual date was not recorded."},
        allow_advance=True)


def initialise(conn):
    conn.executescript(SCHEMA)
    if conn.execute("SELECT 1 FROM meta WHERE key='payments-v1'").fetchone():
        return
    with conn:
        for row in conn.execute("SELECT * FROM invoices").fetchall():
            if not conn.execute("SELECT 1 FROM payments WHERE invoice_id=?", (row["id"],)).fetchone():
                legacy_payment(conn, {"id": row["id"], "amountPaid": row["amount_paid"],
                    "invoiceDate": row["invoice_date"], "createdAt": row["created_at"],
                    "paymentMode": row["payment_mode"], "transactionId": row["transaction_id"]})
        conn.execute("INSERT INTO meta (key,value) VALUES ('payments-v1','1')")


def edit(conn, payment_id, data):
    row = conn.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone()
    if not row:
        raise LookupError("Payment not found")
    old = decode(row)
    amount = cents(data["amount"])
    if amount <= 0:
        raise ValueError("Payment amount must be greater than zero")
    valid_date(data["paymentDate"])
    if data["paymentMethod"] not in METHODS:
        raise ValueError("Invalid payment method")
    inv = conn.execute("SELECT total FROM invoices WHERE id=?", (old["invoiceId"],)).fetchone()
    remaining = max(0, cents(inv["total"]) - paid_cents(conn, old["invoiceId"], payment_id))
    if amount > remaining:
        raise ValueError(f"Payment cannot exceed the remaining balance of ₹{remaining / 100:g}.")
    conn.execute("""UPDATE payments SET payment_date=?,amount=?,payment_method=?,reference=?,notes=?,
        date_inferred=?,updated_at=? WHERE id=?""", (data["paymentDate"], amount / 100,
        data["paymentMethod"], data.get("reference") or "", data.get("notes") or "",
        int(old["dateInferred"] and old["paymentDate"] == data["paymentDate"]), now(), payment_id))
    sync_invoice(conn, old["invoiceId"])
    return decode(conn.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone())


def receipt(conn, payment_id):
    row = conn.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone()
    if not row:
        raise LookupError("Payment not found")
    payment = decode(row)
    inv = conn.execute("SELECT * FROM invoices WHERE id=?", (payment["invoiceId"],)).fetchone()
    previous = 0
    for p in sorted(list_payments(conn, payment["invoiceId"]), key=lambda p: (p["createdAt"], p["id"])):
        if p["id"] == payment_id:
            break
        previous += cents(p["amount"])
    totals = summary(inv["total"], (previous + cents(payment["amount"])) / 100)
    return {"payment": payment, "invoiceNumber": inv["invoice_number"], "tenantName": inv["tenant_name"],
            "previousPaid": previous / 100, **totals}