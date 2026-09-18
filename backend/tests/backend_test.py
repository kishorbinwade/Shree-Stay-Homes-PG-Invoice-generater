"""SQLite-backed API tests — hermetic: runs against a temporary database
(DB_PATH) and never touches the real backend/data/pg_billing.db."""
import os
import sys
import tempfile
from pathlib import Path
import base64
import socket
from email import policy
from email.parser import BytesParser

import pytest

_TMP = tempfile.mkdtemp(prefix="shpg-test-")
os.environ["DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ["SMTP_USER"] = ""
os.environ["SMTP_APP_PASSWORD"] = ""

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402
# Keep hermetic DB empty for deterministic sequence assertions.
database.SEED_PATH = Path(_TMP) / "seed_disabled_for_tests.json"
import server  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

try:
    from aiosmtpd.controller import Controller  # noqa: E402
    from aiosmtpd.smtp import AuthResult, LoginPassword  # noqa: E402
except Exception:  # pragma: no cover
    Controller = None
    AuthResult = None
    LoginPassword = None

client = TestClient(server.app)

INV = {
    "tenantName": "Test Tenant", "tenantMobile": "9876543210", "tenantEmail": "t@example.com",
    "roomNumber": "101", "bedNumber": "A", "billingMonth": "2026-08",
    "rent": 8000, "electricity": 500, "amountPaid": 4000, "paymentMode": "UPI",
}
_MIN_PDF = "JVBERi0xLjQgMSAwIG9iajw8L1R5cGUvQ2F0YWxvZy9QYWdlcyAyIDAgUj4+ZW5kb2J9"


def test_database_file_created():
    database.get_conn()
    assert os.path.exists(os.environ["DB_PATH"])


def test_health():
    r = client.get("/api/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_settings_roundtrip():
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert r.json()["invoicePrefix"] == "SHPG"
    r = client.put("/api/settings", json={"address": "12 MG Road, Pune", "invoicePrefix": "SHPG"})
    assert r.status_code == 200
    assert client.get("/api/settings").json()["address"] == "12 MG Road, Pune"


def test_create_invoice_assigns_sequential_number_and_totals():
    r = client.post("/api/invoices", json=INV)
    assert r.status_code == 201, r.text
    inv = r.json()
    assert inv["invoiceNumber"].endswith("-0001")
    assert inv["subtotal"] == 8500 and inv["total"] == 8500
    assert inv["balanceDue"] == 4500 and inv["paymentStatus"] == "Partially Paid"
    r2 = client.post("/api/invoices", json={**INV, "tenantName": "Second Tenant"})
    assert r2.status_code == 201
    assert r2.json()["invoiceNumber"].endswith("-0002")
    assert r2.json()["invoiceNumber"] != inv["invoiceNumber"]


def test_tenant_auto_created():
    client.post("/api/invoices", json={**INV, "tenantName": "Test Tenant", "tenantMobile": "9000000001"})
    client.post("/api/invoices", json={**INV, "tenantName": "Second Tenant", "tenantMobile": "9000000002"})
    tenants = client.get("/api/tenants").json()
    names = [t["name"] for t in tenants]
    assert "Test Tenant" in names and "Second Tenant" in names


def test_peek_next_number_does_not_consume():
    client.post("/api/invoices", json={**INV, "tenantName": "Peek A", "tenantMobile": "9000000021"})
    client.post("/api/invoices", json={**INV, "tenantName": "Peek B", "tenantMobile": "9000000022"})
    last = client.get("/api/invoices", params={"order": "desc"}).json()[0]["invoiceNumber"]
    last_seq = int(last.rsplit("-", 1)[1])
    a = client.get("/api/invoices/next-number").json()["nextNumber"]
    b = client.get("/api/invoices/next-number").json()["nextNumber"]
    assert a == b
    assert int(a.rsplit("-", 1)[1]) == last_seq + 1


def test_sequence_survives_reconnect():
    client.post("/api/invoices", json={**INV, "tenantName": "Restart A", "tenantMobile": "9000000031"})
    before = client.get("/api/invoices/next-number").json()["nextNumber"]
    database._conn = None  # simulate application restart
    after = client.get("/api/invoices/next-number").json()["nextNumber"]
    assert after == before
    new_inv = client.post("/api/invoices", json={**INV, "tenantName": "Restart B", "tenantMobile": "9000000032"}).json()
    assert new_inv["invoiceNumber"] == before


def test_get_update_delete_invoice():
    inv = client.post("/api/invoices", json={**INV, "tenantName": "Edit Me"}).json()
    got = client.get(f"/api/invoices/{inv['id']}").json()
    assert got["invoiceNumber"] == inv["invoiceNumber"]
    upd = client.put(f"/api/invoices/{inv['id']}", json={**INV, "tenantName": "Edited", "amountPaid": 8500})
    assert upd.status_code == 200
    assert upd.json()["invoiceNumber"] == inv["invoiceNumber"]  # number never changes
    assert upd.json()["paymentStatus"] == "Paid"
    assert upd.json()["balanceDue"] == 0
    assert client.delete(f"/api/invoices/{inv['id']}").json()["deleted"] is True
    assert client.get(f"/api/invoices/{inv['id']}").status_code == 404


def test_search_and_filters():
    r = client.get("/api/invoices", params={"q": "Second"})
    assert all("Second" in i["tenantName"] for i in r.json())
    r = client.get("/api/invoices", params={"q": "SHPG"})
    assert len(r.json()) >= 2
    r = client.get("/api/invoices", params={"month": "2026-08"})
    assert all(i["billingMonth"] == "2026-08" for i in r.json())
    r = client.get("/api/invoices", params={"status": "Partially Paid"})
    assert all(i["paymentStatus"] == "Partially Paid" for i in r.json())
    r = client.get("/api/invoices", params={"month": "1999-01"})
    assert r.json() == []


def test_validation_errors():
    assert client.post("/api/invoices", json={**INV, "tenantName": "  "}).status_code == 422
    assert client.post("/api/invoices", json={**INV, "rent": -5}).status_code == 422
    assert client.post("/api/invoices", json={**INV, "tenantEmail": "bad-email"}).status_code == 422
    assert client.get("/api/invoices/does-not-exist").status_code == 404


def test_backup_export_import_merge_and_sequence_preserved():
    client.post("/api/invoices", json={**INV, "tenantName": "Backup A", "tenantMobile": "9000000011"})
    client.post("/api/invoices", json={**INV, "tenantName": "Backup B", "tenantMobile": "9000000012"})
    backup = client.get("/api/backup/export").json()
    n_before = len(backup["invoices"])
    assert n_before >= 2
    next_before = client.get("/api/invoices/next-number").json()["nextNumber"]
    # merge import of the same backup: everything skipped, nothing duplicated
    res = client.post("/api/backup/import?mode=merge", json=backup).json()
    assert res["invoices_added"] == 0 and res["invoices_skipped"] == n_before
    # wipe and restore: data comes back and numbering continues (no reset to 0001)
    client.delete("/api/data")
    assert client.get("/api/invoices").json() == []
    res = client.post("/api/backup/import?mode=merge", json=backup).json()
    assert res["invoices_added"] == n_before
    assert client.get("/api/invoices/next-number").json()["nextNumber"] == next_before
    new_inv = client.post("/api/invoices", json=INV).json()
    assert new_inv["invoiceNumber"] == next_before


def test_import_rejects_garbage():
    assert client.post("/api/backup/import", json={"junk": True}).status_code == 200  # valid shape, nothing to import
    r = client.post("/api/backup/import", json={"junk": True})
    assert r.json()["invoices_added"] == 0


def test_migration_endpoint_counts_and_idempotent():
    payload = {
        "invoices": [dict(INV, id="legacy-1", invoiceNumber="SHPG-2025-0099",
                          subtotal=8500, total=8500, balanceDue=8500, paymentStatus="Pending",
                          invoiceDate="2025-12-01", createdAt="2025-12-01T00:00:00")],
        "tenants": [{"id": "legacy-t", "name": "Legacy Tenant"}],
        "settings": {"notes": "Migrated note"},
    }
    res = client.post("/api/migrate", json=payload).json()
    assert res["invoices_added"] == 1
    assert res["invoices"] >= 1
    res2 = client.post("/api/migrate", json=payload).json()
    assert res2["invoices_added"] == 0 and res2["invoices_skipped"] == 1
    assert client.get("/api/invoices/legacy-1").json()["invoiceNumber"] == "SHPG-2025-0099"


def test_csv_export():
    r = client.get("/api/backup/export.csv")
    assert r.status_code == 200
    assert "Invoice Number" in r.text and "SHPG-" in r.text


def test_email_503_when_smtp_not_configured():
    r = client.post("/api/email/invoice", json={
        "invoiceNumber": "SHPG-2026-0001", "tenantName": "T", "billingMonth": "2026-08",
        "total": 100, "amountPaid": 0, "balanceDue": 100, "paymentStatus": "Pending",
        "ownerEmail": "shreehomestaypg@gmail.com", "sendToTenant": False,
        "pdfBase64": _MIN_PDF, "pdfFilename": "x.pdf",
    })
    assert r.status_code == 503
    assert "SMTP" in r.json()["detail"]


def test_no_secrets_in_api_responses():
    for path in ("/api/settings", "/api/invoices", "/api/backup/export"):
        body = client.get(path).text
        assert "APP_PASSWORD" not in body


# ---------- new modules: expenses / food / billing / overdue / import ----------

def test_expense_crud_and_profit():
    e = client.post("/api/expenses", json={
        "date": "2026-08-10", "category": "Food ingredients", "description": "Rice", "amount": 1000})
    assert e.status_code == 201, e.text
    eid = e.json()["id"]
    client.post("/api/expenses", json={"date": "2026-08-11", "category": "Repairs", "amount": 500})
    assert client.post("/api/expenses", json={"amount": -5}).status_code == 422
    exps = client.get("/api/expenses", params={"month": "2026-08"}).json()
    assert any(x["id"] == eid for x in exps)
    rep = client.get("/api/reports/monthly", params={"month": "2026-08"}).json()
    assert rep["expenses"] >= 1500
    assert rep["netProfit"] == round(rep["revenue"] - rep["expenses"], 2)
    assert rep["foodExpenses"] >= 1000
    assert client.delete(f"/api/expenses/{eid}").json()["deleted"] is True


def test_food_order_flow_and_monthly_aggregation():
    o1 = client.post("/api/food-orders", json={
        "tenantId": "9111111111", "tenantName": "Foodie", "date": "2026-08-05",
        "mealType": "Lunch", "quantity": 1, "pricePerMeal": 80}).json()
    client.post("/api/food-orders", json={
        "tenantId": "9111111111", "tenantName": "Foodie", "date": "2026-08-06",
        "mealType": "Dinner", "quantity": 2, "pricePerMeal": 80})
    cancelled = client.post("/api/food-orders", json={
        "tenantId": "9111111111", "tenantName": "Foodie", "date": "2026-08-06",
        "mealType": "Breakfast", "quantity": 1, "pricePerMeal": 50}).json()
    client.put(f"/api/food-orders/{cancelled['id']}", json={
        "tenantId": "9111111111", "tenantName": "Foodie", "date": "2026-08-06",
        "mealType": "Breakfast", "quantity": 1, "pricePerMeal": 50, "status": "Cancelled"})
    today = client.get("/api/food-orders/today", params={"date": "2026-08-06"}).json()
    assert today["totalMeals"] == 2  # cancelled breakfast excluded
    s = client.get("/api/food-orders/summary", params={"month": "2026-08"}).json()
    assert s["foodRevenue"] == 240.0
    per = [t for t in s["perTenant"] if t["tenantName"] == "Foodie"]
    assert per and per[0]["total"] == 240.0
    assert client.post("/api/food-orders", json={"tenantName": "", "mealType": "Lunch"}).status_code == 422


def _make_billable_tenant():
    csv_text = "Full Name,Mobile Number,Monthly Rent\nBilling Test,9111111111,8000\n"
    client.post("/api/imports/commit", json={"filename": "t.csv", "csvText": csv_text, "mapping": {"0": "name", "1": "mobile", "2": "rent"}})
    client.put("/api/tenants/9111111111", json={"roomNumber": "201", "status": "Active", "rent": 8000})


def test_monthly_billing_food_and_duplicate_prevention():
    _make_billable_tenant()
    prev = client.get("/api/billing/preview", params={"month": "2026-08"}).json()
    row = [r for r in prev["rows"] if r["tenantName"] == "Billing Test"][0]
    assert row["rent"] == 8000
    assert row["food"] == 240.0  # from food orders above (Foodie == same tenant key)
    gen = client.post("/api/billing/generate", json={"month": "2026-08", "rows": [row]}).json()
    assert len(gen["created"]) == 1
    inv = gen["created"][0]
    assert inv["food"] == 240.0 and inv["total"] == 8240.0
    again = client.post("/api/billing/generate", json={"month": "2026-08", "rows": [row]}).json()
    assert len(again["created"]) == 0 and "Billing Test" in again["skipped"]


def test_overdue_tracking():
    past = client.post("/api/invoices", json={
        "tenantName": "Late Payer", "tenantMobile": "9222222222", "billingMonth": "2026-07",
        "rent": 5000, "amountPaid": 0, "dueDate": "2026-08-01"}).json()
    paid = client.post("/api/invoices", json={
        "tenantName": "On Time", "tenantMobile": "9333333333", "billingMonth": "2026-07",
        "rent": 5000, "amountPaid": 5000, "dueDate": "2026-08-01"}).json()
    od = client.get("/api/invoices/overdue").json()
    nums = [i["invoiceNumber"] for i in od["overdue"]]
    assert past["invoiceNumber"] in nums
    assert paid["invoiceNumber"] not in nums
    entry = [i for i in od["overdue"] if i["invoiceNumber"] == past["invoiceNumber"]][0]
    assert entry["daysOverdue"] >= 20 and entry["effectiveStatus"] == "Overdue"
    assert od["summary"]["overdueAmount"] >= 5000


FIXTURE_CSV = os.path.join(os.path.dirname(__file__), "..", "..", "tests", "fixtures", "google_form_sample.csv")


def test_csv_preview_automapping_and_commit():
    text = open(FIXTURE_CSV).read()
    prev = client.post("/api/imports/preview", json={"filename": "Untitled form.csv", "csvText": text}).json()
    mapping = prev["mapping"]
    cols = prev["columns"]
    def field_of(label):
        return mapping.get(str(cols.index(label)))
    assert field_of("Full Name") == "name"
    assert field_of("Guest Mobile Number") == "mobile"
    assert field_of("Email Address") == "email"
    assert field_of("Monthly Rent") == "rent"
    assert field_of("Security Deposit") == "deposit"
    assert field_of("Room / Bed Number") == "roomNumber"
    assert field_of("Identity Document Type") == "idType"
    assert field_of("ID Document Number") == "idNumber"
    assert field_of("Current Occupation") == "occupation"
    assert field_of("Company / College / Organization Name") == "company"
    assert prev["summary"]["total"] == 3
    res = client.post("/api/imports/commit", json={
        "filename": "Untitled form.csv", "csvText": text, "mapping": mapping, "decisions": {}}).json()
    assert res["imported"] == 3 and res["invalid"] == 0
    # tenants imported; first has rent/room from CSV → Active
    t = client.get("/api/tenants/8975751671").json()
    assert t["name"] == "kishor Binwade" and t["rent"] == 7000 and t["status"] == "Active"
    # re-import same file → all skipped as duplicates, no data clobbered
    res2 = client.post("/api/imports/commit", json={
        "filename": "Untitled form.csv", "csvText": text, "mapping": mapping, "decisions": {}}).json()
    assert res2["imported"] == 0 and res2["skipped"] == 3
    assert client.get("/api/tenants/8975751671").json()["rent"] == 7000


def test_csv_duplicate_update_existing():
    csv_text = "Full Name,Mobile Number,Company Name\nKishor Binwade,8975751671,NewCorp\n"
    prev = client.post("/api/imports/preview", json={"filename": "u.csv", "csvText": csv_text}).json()
    dup = prev["rows"][0]
    assert dup["status"] == "duplicate" and dup["changes"]["company"]["to"] == "NewCorp"
    res = client.post("/api/imports/commit", json={
        "filename": "u.csv", "csvText": csv_text,
        "mapping": {"0": "name", "1": "mobile", "2": "company"},
        "decisions": {"0": "update"}}).json()
    assert res["duplicates"] == 1
    assert client.get("/api/tenants/8975751671").json()["company"] == "NewCorp"


def test_invalid_csv_and_import_history():
    r = client.post("/api/imports/preview", json={"filename": "x.csv", "csvText": ""})
    assert r.status_code == 400
    hist = client.get("/api/imports").json()
    assert len(hist) >= 2
    assert hist[0]["filename"] in ("u.csv", "Untitled form.csv")
    assert "totalRows" in hist[0] and isinstance(hist[0]["details"], list)


def test_backup_includes_new_modules():
    backup = client.get("/api/backup/export").json()
    assert "expenses" in backup and "foodOrders" in backup and "imports" in backup
    assert len(backup["foodOrders"]) >= 3
    res = client.post("/api/backup/import?mode=merge", json=backup).json()
    assert res["food_orders_added"] == 0  # merge skips existing ids


def test_tenant_ledger_running_balance():
    base = {"tenantName": "Ledger Tenant", "tenantMobile": "9123456780", "roomNumber": "L1", "bedNumber": "A"}
    client.post("/api/invoices", json={**base, "billingMonth": "2026-01", "invoiceDate": "2026-01-05",
                                       "rent": 5000, "amountPaid": 3000, "paymentMode": "UPI"})
    client.post("/api/invoices", json={**base, "billingMonth": "2026-02", "invoiceDate": "2026-02-05",
                                       "rent": 5000, "previousBalance": 2000, "amountPaid": 7000, "paymentMode": "Cash"})
    client.post("/api/invoices", json={**base, "billingMonth": "2026-03", "invoiceDate": "2026-03-05",
                                       "rent": 5000, "electricity": 300, "amountPaid": 0})
    r = client.get("/api/tenants/9123456780/ledger")
    assert r.status_code == 200
    led = r.json()
    assert led["tenant"]["name"] == "Ledger Tenant"
    assert led["summary"]["invoiceCount"] == 3
    # previous balance is excluded from charges so nothing is double counted
    assert led["summary"]["totalBilled"] == 15300
    assert led["summary"]["totalPaid"] == 10000
    assert led["summary"]["outstanding"] == 5300
    types = [row["type"] for row in led["rows"]]
    assert types == ["invoice", "payment", "invoice", "payment", "invoice"]
    assert [row["balance"] for row in led["rows"]] == [5000, 2000, 7000, 0, 5300]
    assert led["rows"][2]["debit"] == 5000 and led["rows"][2]["invoiceTotal"] == 7000
    assert led["rows"][1]["paymentMode"] == "UPI"


def test_tenant_ledger_opening_balance_and_404():
    r = client.post("/api/invoices", json={"tenantName": "Opening Tenant", "tenantMobile": "9123456781",
                                           "billingMonth": "2026-04", "rent": 4000, "previousBalance": 1500, "amountPaid": 0})
    assert r.status_code == 201
    led = client.get("/api/tenants/9123456781/ledger").json()
    assert led["rows"][0]["type"] == "opening" and led["rows"][0]["debit"] == 1500
    assert led["summary"]["totalBilled"] == 5500 and led["summary"]["outstanding"] == 5500
    assert client.get("/api/tenants/0000000000/ledger").status_code == 404


# ---------- invoice email owner+tenant-cc / snapshot behavior ----------

class _SinkAuth:
    def __call__(self, server_, session, envelope, mechanism, auth_data):
        ok = isinstance(auth_data, LoginPassword) and auth_data.password == b"secret"
        return AuthResult(success=ok)


class _SinkHandler:
    def __init__(self):
        self.messages = []

    async def handle_DATA(self, server_, session, envelope):
        self.messages.append({
            "mail_from": envelope.mail_from,
            "rcpt_tos": list(envelope.rcpt_tos),
            "content": envelope.original_content if hasattr(envelope, "original_content") else envelope.content,
        })
        return "250 OK"


@pytest.fixture
def smtp_sink():
    if Controller is None:
        pytest.skip("aiosmtpd is not installed in this test environment")
    handler = _SinkHandler()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        port = s.getsockname()[1]
    ctrl = Controller(
        handler,
        hostname="127.0.0.1",
        port=port,
        auth_require_tls=False,
        authenticator=_SinkAuth(),
    )
    ctrl.start()
    try:
        yield {"handler": handler, "port": port}
    finally:
        ctrl.stop()


def _set_local_smtp(monkeypatch, port):
    monkeypatch.setattr(server, "SMTP_HOST", "127.0.0.1", raising=False)
    monkeypatch.setattr(server, "SMTP_PORT", int(port), raising=False)
    monkeypatch.setattr(server, "SMTP_USER", "owner@test.local", raising=False)
    monkeypatch.setattr(server, "SMTP_APP_PASSWORD", "secret", raising=False)
    monkeypatch.setattr(server, "SMTP_TLS", False, raising=False)
    monkeypatch.setattr(server, "SMTP_CONFIGURED", True, raising=False)


def _mk_pdf_bytes():
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


def test_loopback_one_message_owner_to_tenant_cc_with_pdf_attachment(smtp_sink, monkeypatch):
    _set_local_smtp(monkeypatch, smtp_sink["port"])
    pdf_bytes = _mk_pdf_bytes()
    filename = "ShreeStayHomesPG_Invoice_SHPG-2026-9001.pdf"
    refused = server._send_smtp_sync(
        "shreehomestaypg@gmail.com",
        "Invoice",
        "<p>Attached invoice</p>",
        pdf_bytes,
        filename,
        "rahul@example.com",
    )
    assert refused == {}
    assert len(smtp_sink["handler"].messages) == 1
    msg_raw = smtp_sink["handler"].messages[0]["content"]
    if isinstance(msg_raw, str):
        msg_raw = msg_raw.encode("utf-8")
    parsed = BytesParser(policy=policy.default).parsebytes(msg_raw)
    assert parsed["To"] == "shreehomestaypg@gmail.com"
    assert parsed["Cc"] == "rahul@example.com"
    assert smtp_sink["handler"].messages[0]["rcpt_tos"] == ["shreehomestaypg@gmail.com", "rahul@example.com"]
    pdf_part = next(p for p in parsed.walk() if p.get_content_type() == "application/pdf")
    assert pdf_part.get_filename() == filename
    assert pdf_part.get_payload(decode=True) == pdf_bytes


def test_loopback_missing_tenant_email_still_single_message_without_cc(smtp_sink, monkeypatch):
    _set_local_smtp(monkeypatch, smtp_sink["port"])
    server._send_smtp_sync(
        "shreehomestaypg@gmail.com",
        "Invoice",
        "<p>Owner only</p>",
        _mk_pdf_bytes(),
        "ShreeStayHomesPG_Invoice_SHPG-2026-9002.pdf",
        None,
    )
    assert len(smtp_sink["handler"].messages) == 1
    msg_raw = smtp_sink["handler"].messages[0]["content"]
    if isinstance(msg_raw, str):
        msg_raw = msg_raw.encode("utf-8")
    parsed = BytesParser(policy=policy.default).parsebytes(msg_raw)
    assert parsed["To"] == "shreehomestaypg@gmail.com"
    assert parsed.get("Cc") in (None, "")
    assert smtp_sink["handler"].messages[0]["rcpt_tos"] == ["shreehomestaypg@gmail.com"]


def test_loopback_same_owner_and_cc_deduplicates_envelope_recipient(smtp_sink, monkeypatch):
    _set_local_smtp(monkeypatch, smtp_sink["port"])
    owner = "same@example.com"
    server._send_smtp_sync(owner, "Invoice", "<p>same</p>", _mk_pdf_bytes(), "a.pdf", owner)
    assert len(smtp_sink["handler"].messages) == 1
    assert smtp_sink["handler"].messages[0]["rcpt_tos"] == [owner]


def test_api_create_invoice_uses_sqlite_tenant_email_snapshot_and_rejects_identity_mismatch(monkeypatch):
    base = {
        "tenantName": "Snapshot Rahul",
        "tenantMobile": "9550011111",
        "tenantEmail": "sqlite-rahul@example.com",
        "billingMonth": "2026-10",
        "rent": 5000,
    }
    seed = client.post("/api/invoices", json=base)
    assert seed.status_code == 201
    tenants = client.get("/api/tenants").json()
    tenant = next(t for t in tenants if t["mobile"] == "9550011111")

    req_payload = {
        **base,
        "tenantId": tenant["id"],
        "tenantEmail": "browser-tamper@example.com",  # must be ignored in favor of SQLite tenant email
        "amountPaid": 0,
    }
    create = client.post("/api/invoices", json=req_payload)
    assert create.status_code == 201, create.text
    assert create.json()["tenantEmail"] == "sqlite-rahul@example.com"

    mismatch = client.post("/api/invoices", json={
        **req_payload,
        "tenantName": "Different Name",
    })
    assert mismatch.status_code == 422


def test_email_resend_uses_invoice_snapshot_even_after_tenant_email_change(monkeypatch):
    created = client.post("/api/invoices", json={
        "tenantName": "Frozen CC",
        "tenantMobile": "9550022222",
        "tenantEmail": "old-cc@example.com",
        "billingMonth": "2026-10",
        "rent": 6500,
    }).json()
    tid = "9550022222"
    upd_tenant = client.put(f"/api/tenants/{tid}", json={"email": "new-profile@example.com"})
    assert upd_tenant.status_code == 200
    assert client.get(f"/api/invoices/{created['id']}").json()["tenantEmail"] == "old-cc@example.com"

    captured = {}

    async def fake_send(to, subject, html, pdf_b64, filename, cc=None):
        captured["to"] = to
        captured["cc"] = cc
        captured["filename"] = filename
        return {}

    monkeypatch.setattr(server, "SMTP_CONFIGURED", True, raising=False)
    monkeypatch.setattr(server, "send_invoice_email", fake_send)

    req = {
        "invoiceId": created["id"],
        "invoiceNumber": created["invoiceNumber"],
        "tenantName": created["tenantName"],
        "billingMonth": created["billingMonth"],
        "total": created["total"],
        "amountPaid": created["amountPaid"],
        "balanceDue": created["balanceDue"],
        "paymentStatus": created["paymentStatus"],
        "ownerEmail": "ignored@example.com",
        "tenantEmail": "tampered-payload@example.com",
        "pdfBase64": base64.b64encode(_mk_pdf_bytes()).decode(),
        "pdfFilename": "ignored.pdf",
    }
    sent = client.post("/api/email/invoice", json=req)
    assert sent.status_code == 200, sent.text
    assert captured["cc"] == "old-cc@example.com"
    latest = client.get(f"/api/invoices/{created['id']}").json()
    assert latest["emailStatus"]["owner"] == "sent"
    assert latest["emailStatus"]["tenant"] == "included"


def test_email_status_handles_partial_and_all_refusals(monkeypatch):
    inv = client.post("/api/invoices", json={
        "tenantName": "Refusal Test",
        "tenantMobile": "9550033333",
        "tenantEmail": "cc-refuse@example.com",
        "billingMonth": "2026-10",
        "rent": 7000,
    }).json()
    monkeypatch.setattr(server, "SMTP_CONFIGURED", True, raising=False)

    async def owner_ok_cc_refused(*args, **kwargs):
        return {"cc-refuse@example.com": (550, b"refused")}

    monkeypatch.setattr(server, "send_invoice_email", owner_ok_cc_refused)
    payload = {
        "invoiceId": inv["id"],
        "invoiceNumber": inv["invoiceNumber"],
        "tenantName": inv["tenantName"],
        "billingMonth": inv["billingMonth"],
        "total": inv["total"],
        "amountPaid": inv["amountPaid"],
        "balanceDue": inv["balanceDue"],
        "paymentStatus": inv["paymentStatus"],
        "ownerEmail": "owner@example.com",
        "tenantEmail": inv["tenantEmail"],
        "pdfBase64": base64.b64encode(_mk_pdf_bytes()).decode(),
        "pdfFilename": "x.pdf",
    }
    r1 = client.post("/api/email/invoice", json=payload)
    assert r1.status_code == 200
    assert r1.json()["owner"] == "sent"
    assert r1.json()["tenant"] == "failed"

    async def all_refused(*args, **kwargs):
        return {
            "shreehomestaypg@gmail.com": (550, b"owner refused"),
            "cc-refuse@example.com": (550, b"cc refused"),
        }

    monkeypatch.setattr(server, "send_invoice_email", all_refused)
    r2 = client.post("/api/email/invoice", json=payload)
    assert r2.status_code == 200
    assert r2.json()["owner"] == "failed"
    assert r2.json()["tenant"] == "failed"


def test_email_endpoint_persists_owner_failed_and_supports_retry_record(monkeypatch):
    inv = client.post("/api/invoices", json={
        "tenantName": "No SMTP",
        "tenantMobile": "9550044444",
        "tenantEmail": "",
        "billingMonth": "2026-10",
        "rent": 4000,
    }).json()
    monkeypatch.setattr(server, "SMTP_CONFIGURED", False, raising=False)
    payload = {
        "invoiceId": inv["id"],
        "invoiceNumber": inv["invoiceNumber"],
        "tenantName": inv["tenantName"],
        "billingMonth": inv["billingMonth"],
        "total": inv["total"],
        "amountPaid": inv["amountPaid"],
        "balanceDue": inv["balanceDue"],
        "paymentStatus": inv["paymentStatus"],
        "ownerEmail": "owner@example.com",
        "tenantEmail": None,
        "pdfBase64": base64.b64encode(_mk_pdf_bytes()).decode(),
        "pdfFilename": "x.pdf",
    }
    r = client.post("/api/email/invoice", json=payload)
    assert r.status_code == 503
    latest = client.get(f"/api/invoices/{inv['id']}").json()
    assert latest["emailStatus"]["owner"] == "failed"
    assert latest["emailStatus"]["tenant"] == "no-email"


def test_resend_after_tenant_deleted_does_not_recreate_tenant(monkeypatch):
    inv = client.post("/api/invoices", json={
        "tenantName": "Deleted Tenant",
        "tenantMobile": "9550055555",
        "tenantEmail": "deleted-tenant@example.com",
        "billingMonth": "2026-11",
        "rent": 5000,
    }).json()
    tid = "9550055555"
    assert client.delete(f"/api/tenants/{tid}").status_code == 200
    assert client.get(f"/api/tenants/{tid}").status_code == 404

    monkeypatch.setattr(server, "SMTP_CONFIGURED", True, raising=False)

    async def fake_send(*args, **kwargs):
        return {}

    monkeypatch.setattr(server, "send_invoice_email", fake_send)
    payload = {
        "invoiceId": inv["id"],
        "invoiceNumber": inv["invoiceNumber"],
        "tenantName": inv["tenantName"],
        "billingMonth": inv["billingMonth"],
        "total": inv["total"],
        "amountPaid": inv["amountPaid"],
        "balanceDue": inv["balanceDue"],
        "paymentStatus": inv["paymentStatus"],
        "ownerEmail": "owner@example.com",
        "tenantEmail": "tampered@example.com",
        "pdfBase64": base64.b64encode(_mk_pdf_bytes()).decode(),
        "pdfFilename": "x.pdf",
    }
    resend = client.post("/api/email/invoice", json=payload)
    assert resend.status_code == 200
    assert client.get(f"/api/tenants/{tid}").status_code == 404


def test_no_smtp_secrets_exposed_in_read_apis_after_email_errors():
    for path in ("/api/settings", "/api/invoices", "/api/backup/export"):
        body = client.get(path).text
        assert "SMTP_USER" not in body
        assert "SMTP_APP_PASSWORD" not in body
