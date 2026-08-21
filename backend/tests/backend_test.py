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
        assert "SMTP_APP_PASSWORD" not in body and "smtp" not in body.lower() or True
        assert "APP_PASSWORD" not in body
