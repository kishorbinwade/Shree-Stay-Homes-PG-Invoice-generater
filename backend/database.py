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
        "version": 3,
        "exportedAt": _now_iso(),
        "invoices": list_invoices(),
        "tenants": list_tenants(),
        "expenses": list_expenses(),
        "foodOrders": list_food_orders(),
        "imports": list_imports(),
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
              "tenants_skipped": 0, "expenses_added": 0, "food_orders_added": 0,
              "imports_added": 0, "settings_imported": False}
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
            for e in data.get("expenses") or []:
                if isinstance(e, dict) and e.get("id"):
                    exists = conn.execute("SELECT 1 FROM expenses WHERE id=?", (e["id"],)).fetchone()
                    if not exists or mode == "overwrite":
                        conn.execute(
                            "INSERT OR REPLACE INTO expenses (id, date, category, description,"
                            " amount, payment_method, reference, created_at) VALUES (?,?,?,?,?,?,?,?)",
                            (e["id"], e.get("date"), e.get("category"), e.get("description"),
                             float(e.get("amount") or 0), e.get("paymentMethod"),
                             e.get("reference"), e.get("createdAt") or _now_iso()))
                        counts["expenses_added"] += 1
            for o in data.get("foodOrders") or []:
                if isinstance(o, dict) and o.get("id"):
                    exists = conn.execute("SELECT 1 FROM food_orders WHERE id=?", (o["id"],)).fetchone()
                    if not exists or mode == "overwrite":
                        conn.execute(
                            "INSERT OR REPLACE INTO food_orders (id, tenant_id, tenant_name, date,"
                            " meal_type, quantity, price_per_meal, total, status, note, created_at)"
                            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (o["id"], o.get("tenantId"), o.get("tenantName"), o.get("date"),
                             o.get("mealType"), float(o.get("quantity") or 1),
                             float(o.get("pricePerMeal") or 0), float(o.get("total") or 0),
                             o.get("status"), o.get("note"), o.get("createdAt") or _now_iso()))
                        counts["food_orders_added"] += 1
            for im in data.get("imports") or []:
                if isinstance(im, dict) and im.get("id"):
                    conn.execute(
                        "INSERT OR IGNORE INTO imports (id, imported_at, filename, total_rows,"
                        " imported, duplicates, invalid, skipped, details) VALUES (?,?,?,?,?,?,?,?,?)",
                        (im["id"], im.get("importedAt"), im.get("filename"),
                         int(im.get("totalRows") or 0), int(im.get("imported") or 0),
                         int(im.get("duplicates") or 0), int(im.get("invalid") or 0),
                         int(im.get("skipped") or 0), json.dumps(im.get("details") or [])))
                    counts["imports_added"] += 1
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
            conn.execute("DELETE FROM expenses")
            conn.execute("DELETE FROM food_orders")
            conn.execute("DELETE FROM imports")
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


# ==========================================================================
# Extended modules: tenant fields, expenses, food orders, imports, billing
# ==========================================================================

EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS expenses (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    amount REAL DEFAULT 0,
    payment_method TEXT,
    reference TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);
CREATE TABLE IF NOT EXISTS food_orders (
    id TEXT PRIMARY KEY,
    tenant_id TEXT,
    tenant_name TEXT NOT NULL,
    date TEXT NOT NULL,
    meal_type TEXT NOT NULL,
    quantity REAL DEFAULT 1,
    price_per_meal REAL DEFAULT 0,
    total REAL DEFAULT 0,
    status TEXT DEFAULT 'Ordered',
    note TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_food_date ON food_orders(date);
CREATE INDEX IF NOT EXISTS idx_food_tenant ON food_orders(tenant_id);
CREATE TABLE IF NOT EXISTS imports (
    id TEXT PRIMARY KEY,
    imported_at TEXT,
    filename TEXT,
    total_rows INTEGER DEFAULT 0,
    imported INTEGER DEFAULT 0,
    duplicates INTEGER DEFAULT 0,
    invalid INTEGER DEFAULT 0,
    skipped INTEGER DEFAULT 0,
    details TEXT
);
"""

NEW_TENANT_COLUMNS = {
    "company": "TEXT",
    "permanent_address": "TEXT",
    "id_type": "TEXT",
    "id_number": "TEXT",
    "date_of_birth": "TEXT",
    "joining_date": "TEXT",
    "emergency_contact_relationship": "TEXT",
    "status": "TEXT DEFAULT 'Active'",
    "rent": "REAL DEFAULT 0",
    "deposit": "REAL DEFAULT 0",
}

TENANT_MAP.update({
    "company": "company",
    "permanentAddress": "permanent_address",
    "idType": "id_type",
    "idNumber": "id_number",
    "dateOfBirth": "date_of_birth",
    "joiningDate": "joining_date",
    "emergencyContactRelationship": "emergency_contact_relationship",
    "status": "status",
    "rent": "rent",
    "deposit": "deposit",
})

EXPENSE_CATEGORIES = ["Electricity", "Food ingredients", "Internet", "Cleaning",
                      "Maintenance", "Repairs", "Staff", "Rent/property expense", "Other"]
MEAL_TYPES = ["Breakfast", "Lunch", "Dinner"]


def _migrate_tenants_table(conn) -> None:
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(tenants)").fetchall()}
    for col, typ in NEW_TENANT_COLUMNS.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE tenants ADD COLUMN {col} {typ}")


_orig_get_conn = get_conn


def get_conn() -> sqlite3.Connection:  # noqa: F811 — extends base with extra schema
    conn = _orig_get_conn()
    if not getattr(get_conn, "_extra_done", False):
        with _lock:
            conn.executescript(EXTRA_SCHEMA)
            _migrate_tenants_table(conn)
            conn.commit()
        get_conn._extra_done = True
    return conn


def _tenant_key(name: str = "", mobile: str = "") -> str:
    return (mobile or name or "").lower().strip()


# ---------- tenants (extended update) ----------

def update_tenant(tid: str, data: dict):
    with _lock:
        conn = get_conn()
        row = conn.execute("SELECT * FROM tenants WHERE id=?", (tid,)).fetchone()
        if not row:
            return None
        cur = _row_to_tenant(row)
        merged = {**cur, **{k: v for k, v in data.items() if k in TENANT_MAP}}
        merged["id"] = tid
        merged["updatedAt"] = _now_iso()
        sets = ", ".join(f"{snake}=?" for camel, snake in TENANT_MAP.items() if camel != "id")
        vals = [merged.get(camel) for camel, snake in TENANT_MAP.items() if camel != "id"]
        with conn:
            conn.execute(f"UPDATE tenants SET {sets} WHERE id=?", (*vals, tid))
        return merged


def insert_tenant(t: dict) -> dict:
    with _lock:
        conn = get_conn()
        now = _now_iso()
        rec = {k: t.get(k) for k in TENANT_MAP}
        if not rec.get("status"):
            rec["status"] = "Active" if rec.get("roomNumber") else "Pending Admission"
        rec["createdAt"] = rec.get("createdAt") or now
        rec["updatedAt"] = now
        cols = list(TENANT_MAP.values())
        with conn:
            conn.execute(
                f"INSERT INTO tenants ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                tuple(rec.get(c) for c in TENANT_MAP),
            )
        return rec


# ---------- expenses ----------

def _row_to_expense(row) -> dict:
    return {"id": row["id"], "date": row["date"], "category": row["category"],
            "description": row["description"], "amount": row["amount"],
            "paymentMethod": row["payment_method"], "reference": row["reference"],
            "createdAt": row["created_at"]}


def list_expenses(month: str = None, date_from: str = None, date_to: str = None):
    sql, params = "SELECT * FROM expenses", []
    where = []
    if month:
        where.append("date LIKE ?")
        params.append(f"{month}%")
    if date_from:
        where.append("date >= ?")
        params.append(date_from)
    if date_to:
        where.append("date <= ?")
        params.append(date_to)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY date DESC, created_at DESC"
    with _lock:
        rows = get_conn().execute(sql, params).fetchall()
    return [_row_to_expense(r) for r in rows]


def create_expense(d: dict) -> dict:
    rec = {"id": uuid.uuid4().hex, "date": d.get("date") or _now_iso()[:10],
           "category": d.get("category") or "Other", "description": d.get("description") or "",
           "amount": float(d.get("amount") or 0), "paymentMethod": d.get("paymentMethod") or "Cash",
           "reference": d.get("reference") or "", "createdAt": _now_iso()}
    with _lock:
        conn = get_conn()
        with conn:
            conn.execute(
                "INSERT INTO expenses (id, date, category, description, amount, payment_method, reference, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (rec["id"], rec["date"], rec["category"], rec["description"], rec["amount"],
                 rec["paymentMethod"], rec["reference"], rec["createdAt"]))
    return rec


def delete_expense(eid: str) -> bool:
    with _lock:
        conn = get_conn()
        with conn:
            cur = conn.execute("DELETE FROM expenses WHERE id=?", (eid,))
    return cur.rowcount > 0


# ---------- food orders ----------

def _row_to_food(row) -> dict:
    return {"id": row["id"], "tenantId": row["tenant_id"], "tenantName": row["tenant_name"],
            "date": row["date"], "mealType": row["meal_type"], "quantity": row["quantity"],
            "pricePerMeal": row["price_per_meal"], "total": row["total"],
            "status": row["status"], "note": row["note"], "createdAt": row["created_at"]}


def list_food_orders(date: str = None, month: str = None):
    sql, params = "SELECT * FROM food_orders", []
    if date:
        sql += " WHERE date=?"
        params.append(date)
    elif month:
        sql += " WHERE date LIKE ?"
        params.append(f"{month}%")
    sql += " ORDER BY date DESC, created_at DESC"
    with _lock:
        rows = get_conn().execute(sql, params).fetchall()
    return [_row_to_food(r) for r in rows]


def create_food_order(d: dict) -> dict:
    qty = float(d.get("quantity") or 1)
    price = float(d.get("pricePerMeal") or 0)
    rec = {"id": uuid.uuid4().hex, "tenantId": d.get("tenantId") or "",
           "tenantName": d.get("tenantName") or "", "date": d.get("date") or _now_iso()[:10],
           "mealType": d.get("mealType") or "Lunch", "quantity": qty, "pricePerMeal": price,
           "total": round(qty * price, 2), "status": d.get("status") or "Ordered",
           "note": d.get("note") or "", "createdAt": _now_iso()}
    with _lock:
        conn = get_conn()
        with conn:
            conn.execute(
                "INSERT INTO food_orders (id, tenant_id, tenant_name, date, meal_type, quantity,"
                " price_per_meal, total, status, note, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (rec["id"], rec["tenantId"], rec["tenantName"], rec["date"], rec["mealType"],
                 rec["quantity"], rec["pricePerMeal"], rec["total"], rec["status"],
                 rec["note"], rec["createdAt"]))
    return rec


def update_food_order(fid: str, d: dict):
    with _lock:
        conn = get_conn()
        row = conn.execute("SELECT * FROM food_orders WHERE id=?", (fid,)).fetchone()
        if not row:
            return None
        cur = _row_to_food(row)
        merged = {**cur, **{k: v for k, v in d.items() if k in cur}}
        merged["id"] = fid
        merged["quantity"] = float(merged.get("quantity") or 1)
        merged["pricePerMeal"] = float(merged.get("pricePerMeal") or 0)
        merged["total"] = round(merged["quantity"] * merged["pricePerMeal"], 2)
        with conn:
            conn.execute(
                "UPDATE food_orders SET tenant_id=?, tenant_name=?, date=?, meal_type=?, quantity=?,"
                " price_per_meal=?, total=?, status=?, note=? WHERE id=?",
                (merged["tenantId"], merged["tenantName"], merged["date"], merged["mealType"],
                 merged["quantity"], merged["pricePerMeal"], merged["total"], merged["status"],
                 merged["note"], fid))
        return merged


def delete_food_order(fid: str) -> bool:
    with _lock:
        conn = get_conn()
        with conn:
            cur = conn.execute("DELETE FROM food_orders WHERE id=?", (fid,))
    return cur.rowcount > 0


def food_today(date: str) -> dict:
    orders = [o for o in list_food_orders(date=date) if o["status"] != "Cancelled"]
    by_meal = {m: [] for m in MEAL_TYPES}
    for o in orders:
        if o["mealType"] in by_meal:
            by_meal[o["mealType"]].append(o)
    return {"date": date, "meals": by_meal,
            "totalMeals": sum(o["quantity"] for o in orders),
            "totalAmount": round(sum(o["total"] for o in orders), 2)}


def food_summary(month: str) -> dict:
    orders = [o for o in list_food_orders(month=month) if o["status"] != "Cancelled"]
    per_tenant = {}
    meal_counts = {m: 0 for m in MEAL_TYPES}
    for o in orders:
        key = o["tenantId"] or o["tenantName"].lower().strip()
        t = per_tenant.setdefault(key, {"tenantId": o["tenantId"], "tenantName": o["tenantName"],
                                        "meals": 0, "total": 0.0,
                                        "Breakfast": 0.0, "Lunch": 0.0, "Dinner": 0.0})
        t["meals"] += o["quantity"]
        t["total"] = round(t["total"] + o["total"], 2)
        if o["mealType"] in meal_counts:
            meal_counts[o["mealType"]] += o["quantity"]
            t[o["mealType"]] = round(t[o["mealType"]] + o["total"], 2)
    return {"month": month, "perTenant": list(per_tenant.values()),
            "mealCounts": meal_counts,
            "totalMeals": sum(meal_counts.values()),
            "foodRevenue": round(sum(o["total"] for o in orders), 2)}


def food_month_total_for_tenant(month: str, name: str, mobile: str) -> float:
    orders = [o for o in list_food_orders(month=month) if o["status"] != "Cancelled"]
    key = _tenant_key(name, mobile)
    total = 0.0
    for o in orders:
        okey = o["tenantId"] or o["tenantName"].lower().strip()
        if okey == key or o["tenantName"].lower().strip() == (name or "").lower().strip():
            total += o["total"]
    return round(total, 2)


# ---------- monthly billing ----------

def tenant_ledger(tid: str):
    tenant = get_tenant(tid)
    invs = [i for i in list_invoices(order="asc")
            if _tenant_key(i.get("tenantName"), i.get("tenantMobile")) == tid]
    if not tenant and not invs:
        return None
    invs.sort(key=lambda i: ((i.get("invoiceDate") or ""), (i.get("createdAt") or "")))
    if not tenant:
        last = invs[-1]
        tenant = {"id": tid, "name": last.get("tenantName"), "mobile": last.get("tenantMobile"),
                  "email": last.get("tenantEmail"), "roomNumber": last.get("roomNumber"),
                  "bedNumber": last.get("bedNumber"), "deleted": True}
    rows, balance, billed, paid = [], 0.0, 0.0, 0.0
    for idx, inv in enumerate(invs):
        date = inv.get("invoiceDate") or (inv.get("createdAt") or "")[:10]
        prev = float(inv.get("previousBalance") or 0)
        total = float(inv.get("total") or 0)
        if idx == 0 and prev > 0:
            balance += prev
            billed += prev
            rows.append({"date": date, "type": "opening", "invoiceId": inv["id"],
                         "invoiceNumber": inv["invoiceNumber"], "billingMonth": inv.get("billingMonth"),
                         "description": "Opening balance (carried forward)", "debit": round(prev, 2),
                         "credit": 0, "balance": round(balance, 2)})
        charge = round(max(total - prev, 0.0), 2)
        balance += charge
        billed += charge
        rows.append({"date": date, "type": "invoice", "invoiceId": inv["id"],
                     "invoiceNumber": inv["invoiceNumber"], "billingMonth": inv.get("billingMonth"),
                     "description": f"Invoice for {inv.get('billingMonth') or ''}".strip(),
                     "debit": charge, "credit": 0, "balance": round(balance, 2),
                     "previousBalance": round(prev, 2), "invoiceTotal": round(total, 2)})
        amt = float(inv.get("amountPaid") or 0)
        if amt > 0:
            balance -= amt
            paid += amt
            rows.append({"date": date, "type": "payment", "invoiceId": inv["id"],
                         "invoiceNumber": inv["invoiceNumber"], "billingMonth": inv.get("billingMonth"),
                         "description": f"Payment ({inv.get('paymentMode') or 'Cash'})",
                         "paymentMode": inv.get("paymentMode"), "transactionId": inv.get("transactionId"),
                         "debit": 0, "credit": round(amt, 2), "balance": round(balance, 2)})
    return {
        "tenant": tenant,
        "rows": rows,
        "summary": {"totalBilled": round(billed, 2), "totalPaid": round(paid, 2),
                    "outstanding": round(billed - paid, 2), "invoiceCount": len(invs)},
    }


def _previous_balance_for_tenant(month: str, name: str, mobile: str) -> float:
    key = _tenant_key(name, mobile)
    total = 0.0
    for inv in list_invoices():
        ikey = _tenant_key(inv.get("tenantName"), inv.get("tenantMobile"))
        if ikey == key and (inv.get("billingMonth") or "") < month and (inv.get("balanceDue") or 0) > 0:
            total += inv["balanceDue"]
    return round(total, 2)


def _tenant_invoice_for_month(month: str, name: str, mobile: str):
    key = _tenant_key(name, mobile)
    for inv in list_invoices(month=month):
        if _tenant_key(inv.get("tenantName"), inv.get("tenantMobile")) == key:
            return inv
    return None


def billing_preview(month: str) -> dict:
    rows = []
    for t in list_tenants():
        if t.get("status") == "Pending Admission":
            continue
        name, mobile = t.get("name") or "", t.get("mobile") or ""
        existing = _tenant_invoice_for_month(month, name, mobile)
        rows.append({
            "tenantId": t["id"], "tenantName": name, "tenantMobile": mobile,
            "tenantEmail": t.get("email") or "",
            "roomNumber": t.get("roomNumber") or "", "bedNumber": t.get("bedNumber") or "",
            "checkIn": t.get("joiningDate") or t.get("checkIn") or "",
            "occupation": t.get("occupation") or "",
            "rent": float(t.get("rent") or 0),
            "food": food_month_total_for_tenant(month, name, mobile),
            "electricity": 0.0, "maintenance": 0.0, "otherCharges": 0.0, "discount": 0.0,
            "previousBalance": _previous_balance_for_tenant(month, name, mobile),
            "amountPaid": 0.0, "paymentMode": "Cash", "dueDate": "",
            "alreadyBilled": existing is not None,
            "existingInvoiceNumber": existing["invoiceNumber"] if existing else None,
        })
    return {"month": month, "rows": rows}


def billing_generate(month: str, rows: list, due_date: str = "") -> dict:
    created, skipped = [], []
    for row in rows:
        if row.get("alreadyBilled") or _tenant_invoice_for_month(
                month, row.get("tenantName") or "", row.get("tenantMobile") or ""):
            skipped.append(row.get("tenantName"))
            continue
        inv = create_invoice({
            "tenantName": row.get("tenantName"), "tenantEmail": row.get("tenantEmail") or "",
            "tenantMobile": row.get("tenantMobile") or "",
            "roomNumber": row.get("roomNumber") or "", "bedNumber": row.get("bedNumber") or "",
            "checkIn": row.get("checkIn") or "", "occupation": row.get("occupation") or "",
            "billingMonth": month, "dueDate": row.get("dueDate") or due_date,
            "rent": row.get("rent") or 0, "food": row.get("food") or 0,
            "electricity": row.get("electricity") or 0, "maintenance": row.get("maintenance") or 0,
            "otherCharges": row.get("otherCharges") or 0, "discount": row.get("discount") or 0,
            "previousBalance": row.get("previousBalance") or 0,
            "amountPaid": row.get("amountPaid") or 0,
            "paymentMode": row.get("paymentMode") or "Cash",
        })
        created.append(inv)
    return {"created": created, "skipped": skipped}


# ---------- overdue ----------

def overdue_invoices() -> dict:
    today = _now_iso()[:10]
    overdue, due_today, upcoming = [], [], []
    for inv in list_invoices():
        if (inv.get("balanceDue") or 0) <= 0 or not inv.get("dueDate"):
            continue
        days = (datetime.now(timezone.utc).date()
                - datetime.fromisoformat(inv["dueDate"]).date()).days
        entry = {**inv, "daysOverdue": days,
                 "effectiveStatus": "Overdue" if days > 0 else inv["paymentStatus"]}
        if days > 0:
            overdue.append(entry)
        elif days == 0:
            due_today.append(entry)
        else:
            upcoming.append(entry)
    overdue.sort(key=lambda i: -i["daysOverdue"])
    upcoming.sort(key=lambda i: i["dueDate"])
    return {
        "overdue": overdue, "dueToday": due_today, "upcoming": upcoming,
        "summary": {
            "overdueCount": len(overdue),
            "overdueAmount": round(sum(i["balanceDue"] for i in overdue), 2),
            "dueTodayCount": len(due_today),
            "dueTodayAmount": round(sum(i["balanceDue"] for i in due_today), 2),
            "upcomingCount": len(upcoming),
            "upcomingAmount": round(sum(i["balanceDue"] for i in upcoming), 2),
        },
    }


# ---------- reports / dashboard ----------

def monthly_report(month: str = None, date_from: str = None, date_to: str = None) -> dict:
    invs = list_invoices(month=month) if month else list_invoices()
    if date_from or date_to:
        invs = [i for i in invs
                if (not date_from or (i.get("invoiceDate") or "") >= date_from)
                and (not date_to or (i.get("invoiceDate") or "") <= date_to)]
    exps = list_expenses(month=month, date_from=date_from, date_to=date_to)
    revenue = round(sum(min(i.get("amountPaid") or 0, i.get("total") or 0) for i in invs), 2)
    billed = round(sum(i.get("total") or 0 for i in invs), 2)
    expenses_total = round(sum(e["amount"] for e in exps), 2)
    food_rev = round(sum((i.get("food") or 0) for i in invs), 2)
    food_exp = round(sum(e["amount"] for e in exps if e["category"] == "Food ingredients"), 2)
    return {
        "billed": billed, "revenue": revenue, "expenses": expenses_total,
        "netProfit": round(revenue - expenses_total, 2),
        "pending": round(sum(max(i.get("balanceDue") or 0, 0) for i in invs), 2),
        "foodRevenue": food_rev, "foodExpenses": food_exp,
        "foodProfit": round(food_rev - food_exp, 2),
        "invoiceCount": len(invs), "expenseCount": len(exps),
    }


def dashboard_stats() -> dict:
    month = _now_iso()[:7]
    today = _now_iso()[:10]
    invs = list_invoices()
    cm = [i for i in invs if i.get("billingMonth") == month]
    od = overdue_invoices()
    ft = food_today(today)
    fs = food_summary(month)
    tenants = list_tenants()
    exp_month = round(sum(e["amount"] for e in list_expenses(month=month)), 2)
    month_collected = round(sum(min(i.get("amountPaid") or 0, i.get("total") or 0) for i in cm), 2)
    return {
        "totalInvoices": len(invs),
        "totalBilled": round(sum(i.get("total") or 0 for i in invs), 2),
        "totalCollected": round(sum(min(i.get("amountPaid") or 0, i.get("total") or 0) for i in invs), 2),
        "totalPending": round(sum(max(i.get("balanceDue") or 0, 0) for i in invs), 2),
        "monthCollected": month_collected,
        "monthPending": round(sum(max(i.get("balanceDue") or 0, 0) for i in cm), 2),
        "monthBilled": round(sum(i.get("total") or 0 for i in cm), 2),
        "overdueAmount": od["summary"]["overdueAmount"],
        "overdueCount": od["summary"]["overdueCount"],
        "activeTenants": sum(1 for t in tenants if t.get("status") != "Pending Admission"),
        "occupiedRooms": sum(1 for t in tenants if t.get("roomNumber")),
        "foodOrdersToday": int(ft["totalMeals"]),
        "foodRevenueMonth": fs["foodRevenue"],
        "expensesMonth": exp_month,
        "netProfitMonth": round(month_collected - exp_month, 2),
    }


# ---------- Google Forms CSV import ----------

def _norm_header(h: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (h or "").lower())


CSV_AUTO_MAP = {
    "fullname": "name", "name": "name", "tenantname": "name", "guestname": "name",
    "yourname": "name", "applicantname": "name",
    "mobile": "mobile", "mobilenumber": "mobile", "mobileno": "mobile",
    "phone": "mobile", "phonenumber": "mobile", "contactnumber": "mobile",
    "whatsappnumber": "mobile", "contactno": "mobile",
    "email": "email", "emailaddress": "email", "emailid": "email",
    "emergencycontact": "emergencyContact", "emergencycontactnumber": "emergencyContact",
    "emergencycontactno": "emergencyContact",
    "emergencycontactrelationship": "emergencyContactRelationship",
    "relationship": "emergencyContactRelationship", "relation": "emergencyContactRelationship",
    "occupation": "occupation", "profession": "occupation",
    "company": "company", "companyname": "company", "workplace": "company",
    "wheredoyoucurrentlywork": "company", "collegename": "company",
    "college": "company", "organization": "company", "organisation": "company",
    "permanentaddress": "permanentAddress", "address": "permanentAddress",
    "homeaddress": "permanentAddress", "currentaddress": "permanentAddress",
    "idtype": "idType", "idprooftype": "idType", "idproof": "idType",
    "idnumber": "idNumber", "idproofnumber": "idNumber", "aadhaarnumber": "idNumber",
    "aadhaar": "idNumber", "aadharnumber": "idNumber", "govtid": "idNumber",
    "dateofbirth": "dateOfBirth", "dob": "dateOfBirth", "birthdate": "dateOfBirth",
    "checkindate": "joiningDate", "joiningdate": "joiningDate",
    "dateofjoining": "joiningDate", "checkin": "joiningDate",
    "room": "roomNumber", "roomnumber": "roomNumber", "roomno": "roomNumber",
    "bed": "bedNumber", "bednumber": "bedNumber", "bedno": "bedNumber",
    "monthlyrent": "rent", "rent": "rent", "rentamount": "rent",
    "securitydeposit": "deposit", "deposit": "deposit", "depositamount": "deposit",
    # Real-world Google Forms PG admission variants
    "roombednumber": "roomNumber", "roombed": "roomNumber",
    "guestmobilenumber": "mobile", "guestmobile": "mobile", "whatsappno": "mobile",
    "currentoccupation": "occupation",
    "companycollegeorganizationname": "company", "companycollegename": "company",
    "identitydocumenttype": "idType", "iddocumenttype": "idType",
    "iddocumentnumber": "idNumber", "identitydocumentnumber": "idNumber",
    "emergencycontactmobile": "emergencyContact", "emergencycontactmobilenumber": "emergencyContact",
    "expectedcheckoutdate": "", "timestamp": "", "username": "",
}

CSV_IMPORT_FIELDS = ["name", "mobile", "email", "emergencyContact",
                     "emergencyContactRelationship", "occupation", "company",
                     "permanentAddress", "idType", "idNumber", "dateOfBirth",
                     "joiningDate", "roomNumber", "bedNumber", "rent", "deposit"]


def parse_csv_text(csv_text: str):
    import csv
    import io
    sample = csv_text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(csv_text), dialect)
    rows = [r for r in reader if any((c or "").strip() for c in r)]
    if not rows:
        raise ValueError("The CSV file is empty")
    return rows[0], rows[1:]


def _mapped_row(headers, mapping, raw):
    rec = {f: "" for f in CSV_IMPORT_FIELDS}
    for idx, h in enumerate(headers):
        field = mapping.get(str(idx))
        if field and field in rec and idx < len(raw):
            v = (raw[idx] or "").strip()
            if v and not rec[field]:  # first non-empty mapped column wins
                rec[field] = v
    for f in ("rent", "deposit"):
        v = re.sub(r"[^\d.]", "", rec.get(f) or "")
        rec[f] = float(v) if v else 0.0
    return rec


def _find_duplicate(rec):
    mobile, email = (rec.get("mobile") or "").strip(), (rec.get("email") or "").strip().lower()
    for t in list_tenants():
        if mobile and (t.get("mobile") or "").strip() == mobile:
            return t
        if email and (t.get("email") or "").strip().lower() == email:
            return t
    return None


def _diff_changes(existing, rec):
    changes = {}
    for f in CSV_IMPORT_FIELDS:
        new_v = rec.get(f)
        if new_v in (None, "", 0, 0.0):
            continue
        old_v = existing.get(f if f != "name" else "name")
        if f in ("rent", "deposit"):
            old_v = float(old_v or 0)
            if abs(float(new_v) - old_v) > 0.001:
                changes[f] = {"from": old_v, "to": new_v}
        elif str(old_v or "") != str(new_v):
            changes[f] = {"from": old_v or "", "to": new_v}
    return changes


def csv_preview(filename: str, csv_text: str) -> dict:
    headers, raw_rows = parse_csv_text(csv_text)
    mapping = {}
    for idx, h in enumerate(headers):
        field = CSV_AUTO_MAP.get(_norm_header(h))
        if field:
            mapping[str(idx)] = field
    used = set(mapping.values())
    if "name" not in used:
        for idx, h in enumerate(headers):
            if str(idx) not in mapping and "name" in (h or "").lower():
                mapping[str(idx)] = "name"
                break
    rows, summary = [], {"total": 0, "new": 0, "duplicates": 0, "invalid": 0}
    for i, raw in enumerate(raw_rows):
        rec = _mapped_row(headers, mapping, raw)
        entry = {"rowIndex": i, "data": rec, "raw": raw}
        if not rec.get("name"):
            entry["status"] = "invalid"
            entry["errors"] = ["Missing name"]
            summary["invalid"] += 1
        else:
            dup = _find_duplicate(rec)
            if dup:
                entry["status"] = "duplicate"
                entry["existing"] = dup
                entry["changes"] = _diff_changes(dup, rec)
                summary["duplicates"] += 1
            else:
                entry["status"] = "new"
                summary["new"] += 1
        summary["total"] += 1
        rows.append(entry)
    return {"filename": filename, "columns": headers, "mapping": mapping,
            "importableFields": CSV_IMPORT_FIELDS, "rows": rows, "summary": summary}


def csv_commit(filename: str, csv_text: str, mapping: dict, decisions: dict) -> dict:
    headers, raw_rows = parse_csv_text(csv_text)
    stats = {"total": 0, "imported": 0, "duplicates": 0, "invalid": 0, "skipped": 0}
    details = []
    for i, raw in enumerate(raw_rows):
        stats["total"] += 1
        rec = _mapped_row(headers, mapping, raw)
        name = rec.get("name") or "(no name)"
        if not rec.get("name"):
            stats["invalid"] += 1
            details.append({"row": i + 1, "name": name, "result": "invalid"})
            continue
        dup = _find_duplicate(rec)
        decision = (decisions or {}).get(str(i), "skip")
        if dup:
            if decision == "update":
                changes = _diff_changes(dup, rec)
                if changes:
                    update_tenant(dup["id"], {f: c["to"] for f, c in changes.items()})
                stats["duplicates"] += 1
                details.append({"row": i + 1, "name": name, "result": "updated",
                                "fields": list(changes.keys())})
            else:
                stats["skipped"] += 1
                details.append({"row": i + 1, "name": name, "result": "skipped"})
            continue
        rec["id"] = _tenant_key(rec.get("name"), rec.get("mobile")) or uuid.uuid4().hex
        rec["status"] = "Active" if rec.get("roomNumber") else "Pending Admission"
        insert_tenant(rec)
        stats["imported"] += 1
        details.append({"row": i + 1, "name": name, "result": "imported"})
    imp = {"id": uuid.uuid4().hex, "imported_at": _now_iso(), "filename": filename,
           "total_rows": stats["total"], "imported": stats["imported"],
           "duplicates": stats["duplicates"], "invalid": stats["invalid"],
           "skipped": stats["skipped"], "details": json.dumps(details)}
    with _lock:
        conn = get_conn()
        with conn:
            conn.execute(
                "INSERT INTO imports (id, imported_at, filename, total_rows, imported,"
                " duplicates, invalid, skipped, details) VALUES (?,?,?,?,?,?,?,?,?)",
                (imp["id"], imp["imported_at"], imp["filename"], imp["total_rows"],
                 imp["imported"], imp["duplicates"], imp["invalid"], imp["skipped"],
                 imp["details"]))
    return {**stats, "importId": imp["id"]}


def list_imports():
    with _lock:
        rows = get_conn().execute(
            "SELECT * FROM imports ORDER BY imported_at DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["details"] = json.loads(d.get("details") or "[]")
        except Exception:
            d["details"] = []
        d["importedAt"] = d.pop("imported_at")
        d["totalRows"] = d.pop("total_rows")
        out.append(d)
    return out


SEED_PATH = Path(__file__).parent / "seed_data.json"


def seed_if_empty() -> dict:
    """Populate the DB with bundled sample data if it is completely empty.

    Runs on startup so both the hosted preview and a freshly-pulled local copy
    show the same demo invoices/tenants/expenses/food orders. No-op once data
    exists, so it never overwrites real records.
    """
    get_conn()
    c = counts()
    if c.get("invoices") or c.get("tenants"):
        return {"seeded": False, "reason": "data already present"}
    if not SEED_PATH.exists():
        return {"seeded": False, "reason": "seed_data.json missing"}
    try:
        with open(SEED_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        result = import_data(data, mode="merge")
        return {"seeded": True, **result}
    except Exception as exc:  # pragma: no cover
        return {"seeded": False, "reason": str(exc)}
