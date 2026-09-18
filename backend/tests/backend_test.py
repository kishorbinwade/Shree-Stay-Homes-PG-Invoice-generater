"""SQLite-backed API tests — hermetic: runs against a temporary database
(DB_PATH) and never touches the real backend/data/pg_billing.db."""
import os
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="shpg-test-")
os.environ["DB_PATH"] = os.path.join(_TMP, "test.db")
os.environ["SMTP_USER"] = ""
os.environ["SMTP_APP_PASSWORD"] = ""

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402
import server  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

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
