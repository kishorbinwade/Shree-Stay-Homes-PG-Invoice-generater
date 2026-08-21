"""SQLite storage layer for Shree Stay Homes & PG Billing.

Single local database file (default: backend/data/pg_billing.db). No database
server, no cloud — the file can be backed up by simply copying it.
"""
import json
import os
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = os.environ.get("DB_PATH", str(Path(__file__).parent / "data" / "pg_billing.db"))

_lock = threading.RLock()
_conn = None

DEFAULT_SETTINGS = {
    "businessName": "SHREE STAY HOMES & PG",
    "subtitle": "PG Accommodation & Stay Services",
    "address": "",
    "mobile": "",
    "email": "shreehomestaypg@gmail.com",
    "gstin": "",
    "logo": "",
    "signature": "",
    "ownerEmail": "shreehomestaypg@gmail.com",
    "autoOwnerEmail": True,
    "tenantEmailEnabled": True,
    "invoicePrefix": "SHPG",
    "startingNumber": 1,
    "paymentTerms": "Payment due within 7 days of invoice date.",
    "notes": "Thank you for staying with Shree Stay Homes & PG.",
    "watermarkText": "SHREE STAY HOMES & PG",
}

FIELD_MAP = {
    "id": "id",
    "invoiceNumber": "invoice_number",
    "invoiceDate": "invoice_date",
    "billingMonth": "billing_month",
    "dueDate": "due_date",
    "tenantName": "tenant_name",
    "tenantEmail": "tenant_email",
    "tenantMobile": "tenant_mobile",
    "roomNumber": "room_number",
    "bedNumber": "bed_number",
    "checkIn": "check_in",
    "checkOut": "check_out",
    "occupation": "occupation",
    "emergencyContact": "emergency_contact",
    "rent": "rent",
    "securityDeposit": "security_deposit",
    "electricity": "electricity",
    "food": "food",
    "maintenance": "maintenance",
    "otherCharges": "other_charges",
    "discount": "discount",
    "previousBalance": "previous_balance",
    "subtotal": "subtotal",
    "total": "total",
    "amountPaid": "amount_paid",
    "balanceDue": "balance_due",
    "paymentMode": "payment_mode",
    "transactionId": "transaction_id",
    "paymentStatus": "payment_status",
    "sendToTenant": "send_to_tenant",
    "emailStatus": "email_status",
    "notes": "notes",
    "createdAt": "created_at",
    "updatedAt": "updated_at",
}

NUMERIC_FIELDS = {
    "rent", "securityDeposit", "electricity", "food", "maintenance",
    "otherCharges", "discount", "previousBalance", "subtotal", "total",
    "amountPaid", "balanceDue",
}

TENANT_MAP = {
    "id": "id",
    "name": "name",
    "mobile": "mobile",
    "email": "email",
    "occupation": "occupation",
    "emergencyContact": "emergency_contact",
    "roomNumber": "room_number",
    "bedNumber": "bed_number",
    "checkIn": "check_in",
    "checkOut": "check_out",
    "createdAt": "created_at",
    "updatedAt": "updated_at",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    invoice_number TEXT UNIQUE NOT NULL,
    invoice_date TEXT,
    billing_month TEXT,
    due_date TEXT,
    tenant_name TEXT NOT NULL,
    tenant_email TEXT,
    tenant_mobile TEXT,
    room_number TEXT,
    bed_number TEXT,
    check_in TEXT,
    check_out TEXT,
    occupation TEXT,
    emergency_contact TEXT,
    rent REAL DEFAULT 0,
    security_deposit REAL DEFAULT 0,
    electricity REAL DEFAULT 0,
    food REAL DEFAULT 0,
    maintenance REAL DEFAULT 0,
    other_charges REAL DEFAULT 0,
    discount REAL DEFAULT 0,
    previous_balance REAL DEFAULT 0,
    subtotal REAL DEFAULT 0,
    total REAL DEFAULT 0,
    amount_paid REAL DEFAULT 0,
    balance_due REAL DEFAULT 0,
    payment_mode TEXT,
    transaction_id TEXT,
    payment_status TEXT,
    send_to_tenant INTEGER DEFAULT 0,
    email_status TEXT,
    notes TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_invoices_number ON invoices(invoice_number);
CREATE INDEX IF NOT EXISTS idx_invoices_month ON invoices(billing_month);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(payment_status);
CREATE TABLE IF NOT EXISTS tenants (
    id TEXT PRIMARY KEY,
    name TEXT,
    mobile TEXT,
    email TEXT,
    occupation TEXT,
    emergency_contact TEXT,
    room_number TEXT,
    bed_number TEXT,
    check_in TEXT,
    check_out TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.executescript(SCHEMA)
    return _conn


def compute_totals(d: dict):
    subtotal = sum(float(d.get(k) or 0) for k in (
        "rent", "securityDeposit", "electricity", "food", "maintenance",
        "otherCharges", "previousBalance"))
    total = max(0.0, subtotal - float(d.get("discount") or 0))
    paid = float(d.get("amountPaid") or 0)
    balance = total - paid
    if paid <= 0:
        status = "Pending"
    elif paid >= total and total > 0:
        status = "Paid"
    else:
        status = "Partially Paid"
    return subtotal, total, balance, status


def _row_to_invoice(row: sqlite3.Row) -> dict:
    inv = {}
    for camel, snake in FIELD_MAP.items():
        v = row[snake]
        if camel == "sendToTenant":
            v = bool(v)
        elif camel == "emailStatus":
            try:
                v = json.loads(v) if v else {}
            except Exception:
                v = {}
        inv[camel] = v
    return inv


def _normalize_invoice(d: dict, keep_created: str = None) -> dict:
    inv = {k: v for k, v in d.items() if k in FIELD_MAP}
    for k in NUMERIC_FIELDS:
        try:
            inv[k] = float(inv.get(k) or 0)
        except (TypeError, ValueError):
            inv[k] = 0.0
    for k in ("tenantName", "tenantEmail", "tenantMobile", "roomNumber", "bedNumber",
              "checkIn", "checkOut", "occupation", "emergencyContact", "billingMonth",
              "dueDate", "paymentMode", "transactionId", "notes"):
        inv[k] = inv.get(k) or ""
    subtotal, total, balance, status = compute_totals(inv)
    inv["subtotal"] = subtotal
    inv["total"] = total
    inv["balanceDue"] = balance
    inv["paymentStatus"] = status
    now = _now_iso()
    if not inv.get("id"):
        inv["id"] = uuid.uuid4().hex
    if not inv.get("invoiceDate"):
        inv["invoiceDate"] = now[:10]
    inv["createdAt"] = keep_created or inv.get("createdAt") or now
    inv["updatedAt"] = now
    inv["sendToTenant"] = bool(inv.get("sendToTenant"))
    if not isinstance(inv.get("emailStatus"), dict):
        inv["emailStatus"] = {"owner": "pending", "tenant": "pending" if inv["sendToTenant"] else "skipped"}
    return inv


def _params(inv: dict) -> dict:
    p = {}
    for camel, snake in FIELD_MAP.items():
        v = inv.get(camel)
        if camel == "sendToTenant":
            v = 1 if v else 0
        elif camel == "emailStatus":
            v = json.dumps(v or {})
        p[snake] = v
    return p


def _insert_sql() -> str:
    cols = list(FIELD_MAP.values())
    return f"INSERT INTO invoices ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"


# ---------- invoices ----------

def list_invoices(q: str = None, month: str = None, status: str = None, order: str = "desc"):
    sql = "SELECT * FROM invoices"
    where, params = [], []
    if q:
        where.append("(tenant_name LIKE ? OR invoice_number LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if month:
        where.append("billing_month = ?")
        params.append(month)
    if status:
        where.append("payment_status = ?")
        params.append(status)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at " + ("ASC" if order == "asc" else "DESC")
    with _lock:
        rows = get_conn().execute(sql, params).fetchall()
    return [_row_to_invoice(r) for r in rows]


def get_invoice(inv_id: str):
    with _lock:
        row = get_conn().execute("SELECT * FROM invoices WHERE id=?", (inv_id,)).fetchone()
    return _row_to_invoice(row) if row else None


def delete_invoice(inv_id: str) -> bool:
    with _lock:
        conn = get_conn()
        with conn:
            cur = conn.execute("DELETE FROM invoices WHERE id=?", (inv_id,))
    return cur.rowcount > 0


def _get_seq(conn, year: int) -> int:
    row = conn.execute("SELECT value FROM meta WHERE key=?", (f"seq-{year}",)).fetchone()
    return int(row["value"]) if row and row["value"] else 0


def peek_next_number() -> str:
    s = get_settings()
    year = datetime.now().year
    with _lock:
        seq = _get_seq(get_conn(), year)
    nxt = max(seq + 1, int(s.get("startingNumber") or 1))
    return f"{s.get('invoicePrefix') or 'SHPG'}-{year}-{nxt:04d}"


def create_invoice(data: dict) -> dict:
    with _lock:
        conn = get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            s = get_settings()
            year = datetime.now().year
            key = f"seq-{year}"
            nxt = max(_get_seq(conn, year) + 1, int(s.get("startingNumber") or 1))
            number = f"{s.get('invoicePrefix') or 'SHPG'}-{year}-{nxt:04d}"
            conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(nxt)),
            )
            inv = _normalize_invoice(data)
            inv["id"] = uuid.uuid4().hex
            inv["invoiceNumber"] = number
            conn.execute(_insert_sql(), tuple(_params(inv).values()))
            _upsert_tenant(conn, inv)
            conn.commit()
            return inv
        except Exception:
            conn.rollback()
            raise


def update_invoice(inv_id: str, data: dict):
    with _lock:
        conn = get_conn()
        row = conn.execute("SELECT * FROM invoices WHERE id=?", (inv_id,)).fetchone()
        if not row:
            return None
        ex = _row_to_invoice(row)
        merged = {**ex, **{k: v for k, v in data.items() if k in FIELD_MAP}}
        merged["id"] = inv_id
        merged["invoiceNumber"] = ex["invoiceNumber"]
        inv = _normalize_invoice(merged, keep_created=ex["createdAt"])
        sets = ", ".join(f"{snake}=?" for camel, snake in FIELD_MAP.items() if camel != "id")
        vals = [_params(inv)[snake] for camel, snake in FIELD_MAP.items() if camel != "id"]
        with conn:
            conn.execute(f"UPDATE invoices SET {sets} WHERE id=?", (*vals, inv_id))
            _upsert_tenant(conn, inv)
        return inv


# ---------- tenants ----------

def _row_to_tenant(row: sqlite3.Row) -> dict:
    return {camel: row[snake] for camel, snake in TENANT_MAP.items()}


def _upsert_tenant(conn, inv: dict) -> None:
    key = ((inv.get("tenantMobile") or inv.get("tenantName") or "")).lower().strip()
    if not key:
        return
    now = _now_iso()
    conn.execute(
        """INSERT INTO tenants (id, name, mobile, email, occupation, emergency_contact,
               room_number, bed_number, check_in, check_out, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET
               name=excluded.name, mobile=excluded.mobile, email=excluded.email,
               occupation=excluded.occupation, emergency_contact=excluded.emergency_contact,
               room_number=excluded.room_number, bed_number=excluded.bed_number,
               check_in=excluded.check_in, check_out=excluded.check_out,
               updated_at=excluded.updated_at""",
        (key, inv.get("tenantName"), inv.get("tenantMobile"), inv.get("tenantEmail"),
         inv.get("occupation"), inv.get("emergencyContact"), inv.get("roomNumber"),
         inv.get("bedNumber"), inv.get("checkIn"), inv.get("checkOut"), now, now),
    )


def list_tenants():
    with _lock:
        rows = get_conn().execute("SELECT * FROM tenants ORDER BY updated_at DESC").fetchall()
    return [_row_to_tenant(r) for r in rows]


def get_tenant(tid: str):
    with _lock:
        row = get_conn().execute("SELECT * FROM tenants WHERE id=?", (tid,)).fetchone()
    return _row_to_tenant(row) if row else None


def delete_tenant(tid: str) -> bool:
    with _lock:
        conn = get_conn()
        with conn:
            cur = conn.execute("DELETE FROM tenants WHERE id=?", (tid,))
    return cur.rowcount > 0


# ---------- settings ----------

def get_settings() -> dict:
    with _lock:
        row = get_conn().execute("SELECT data FROM settings WHERE id=1").fetchone()
    data = {}
    if row:
        try:
            data = json.loads(row["data"])
        except Exception:
            data = {}
    return {**DEFAULT_SETTINGS, **data}


def save_settings(d: dict) -> dict:
    merged = {**get_settings(), **{k: v for k, v in d.items() if k in DEFAULT_SETTINGS}}
    with _lock:
        conn = get_conn()
        with conn:
            conn.execute("INSERT OR REPLACE INTO settings (id, data) VALUES (1, ?)", (json.dumps(merged),))
    return merged


# ---------- backup / restore / migration ----------

def export_data() -> dict:
    with _lock:
        seqs = {r["key"]: int(r["value"]) for r in get_conn().execute(
            "SELECT key, value FROM meta WHERE key LIKE 'seq-%'").fetchall()}
    return {
        "app": "Shree Stay Homes & PG Billing",
        "version": 2,
        "exportedAt": _now_iso(),
        "invoices": list_invoices(),
        "tenants": list_tenants(),
        "settings": get_settings(),
        "sequences": seqs,
    }


def _recompute_sequences(conn) -> None:
    best = {}
    for (num,) in conn.execute("SELECT invoice_number FROM invoices").fetchall():
        m = re.search(r"-(\d{4})-(\d+)$", num or "")
        if m:
            yr, n = m.group(1), int(m.group(2))
            if n > best.get(yr, 0):
                best[yr] = n
    for yr, n in best.items():
        key = f"seq-{yr}"
        if n > _get_seq(conn, int(yr)):
            conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(n)),
            )


def import_data(data, mode: str = "merge") -> dict:
    if isinstance(data, list):
        data = {"invoices": data}
    if not isinstance(data, dict):
        raise ValueError("Invalid backup file — expected a JSON object with an 'invoices' list")
    invoices = data.get("invoices") or []
    tenants = data.get("tenants") or []
    settings = data.get("settings")
    counts = {"invoices_added": 0, "invoices_skipped": 0, "tenants_added": 0,
              "tenants_skipped": 0, "settings_imported": False}
    valid = [i for i in invoices if isinstance(i, dict) and i.get("invoiceNumber")]
    with _lock:
        conn = get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            for raw in valid:
                inv = _normalize_invoice(raw)
                exists = conn.execute(
                    "SELECT 1 FROM invoices WHERE id=? OR invoice_number=?",
                    (inv["id"], inv["invoiceNumber"])).fetchone()
                if exists and mode != "overwrite":
                    counts["invoices_skipped"] += 1
                    continue
                conn.execute("INSERT OR " + ("REPLACE" if mode == "overwrite" else "IGNORE")
                             + _insert_sql()[len("INSERT"):], tuple(_params(inv).values()))
                counts["invoices_added"] += 1
            for t in tenants:
                if not isinstance(t, dict) or not t.get("id"):
                    continue
                exists = conn.execute("SELECT 1 FROM tenants WHERE id=?", (t["id"],)).fetchone()
                if exists and mode != "overwrite":
                    counts["tenants_skipped"] += 1
                    continue
                now = _now_iso()
                conn.execute(
                    "INSERT OR REPLACE INTO tenants (id, name, mobile, email, occupation,"
                    " emergency_contact, room_number, bed_number, check_in, check_out,"
                    " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (t["id"], t.get("name"), t.get("mobile"), t.get("email"),
                     t.get("occupation"), t.get("emergencyContact"), t.get("roomNumber"),
                     t.get("bedNumber"), t.get("checkIn"), t.get("checkOut"),
                     t.get("createdAt") or now, t.get("updatedAt") or now))
                counts["tenants_added"] += 1
            if isinstance(settings, dict):
                cur = conn.execute("SELECT 1 FROM settings WHERE id=1").fetchone()
                if mode == "overwrite" or not cur:
                    merged = {**DEFAULT_SETTINGS,
                              **{k: v for k, v in settings.items() if k in DEFAULT_SETTINGS}}
                    conn.execute("INSERT OR REPLACE INTO settings (id, data) VALUES (1, ?)",
                                 (json.dumps(merged),))
                    counts["settings_imported"] = True
            _recompute_sequences(conn)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return counts


def clear_all() -> dict:
    with _lock:
        conn = get_conn()
        before = {"invoices": conn.execute("SELECT COUNT(*) c FROM invoices").fetchone()["c"],
                  "tenants": conn.execute("SELECT COUNT(*) c FROM tenants").fetchone()["c"]}
        with conn:
            conn.execute("DELETE FROM invoices")
            conn.execute("DELETE FROM tenants")
            conn.execute("DELETE FROM settings")
            conn.execute("DELETE FROM meta")
    return before


def counts() -> dict:
    with _lock:
        conn = get_conn()
        return {
            "invoices": conn.execute("SELECT COUNT(*) c FROM invoices").fetchone()["c"],
            "tenants": conn.execute("SELECT COUNT(*) c FROM tenants").fetchone()["c"],
        }
