"""Payment ledger and receipt regression tests using the shared hermetic API client."""

import base64
import os
import socket
from concurrent.futures import ThreadPoolExecutor
from email import policy
from email.parser import BytesParser
from pathlib import Path

import pytest

from backend_test import client
import server

try:
    from aiosmtpd.controller import Controller
    from aiosmtpd.smtp import AuthResult, LoginPassword
except Exception:  # pragma: no cover
    Controller = None
    AuthResult = None
    LoginPassword = None


def _make_invoice(name: str, mobile: str, rent: float = 100.0, paid: float = 0.0):
    payload = {
        "tenantName": name,
        "tenantMobile": mobile,
        "tenantEmail": f"{mobile}@example.com",
        "billingMonth": "2026-10",
        "rent": rent,
        "amountPaid": paid,
        "paymentMode": "Cash",
    }
    res = client.post("/api/invoices", json=payload)
    assert res.status_code == 201, res.text
    return res.json()


def _add_payment(invoice_id: str, amount: float, date: str = "2026-10-01", method: str = "Cash"):
    return client.post("/api/payments", json={
        "invoiceId": invoice_id,
        "paymentDate": date,
        "amount": amount,
        "paymentMethod": method,
        "reference": "ref",
        "notes": "note",
    })


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
def smtp_sink_route():
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


def _mk_pdf_bytes(tag: str):
    return f"%PDF-1.4\n{tag}\n%%EOF\n".encode("utf-8")


def _parse_message_bytes(raw):
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    return BytesParser(policy=policy.default).parsebytes(raw)


# Payment scenarios: one invoice, many payments, edit/delete and status summary
def test_payment_examples_unpaid_partial_paid_multi_and_reject_excess():
    i1 = _make_invoice("TEST_P1", "9000010001", rent=100, paid=0)
    assert i1["total"] == 100
    assert i1["amountPaid"] == 0
    assert i1["balanceDue"] == 100
    assert i1["paymentStatus"] == "Pending"

    p = _add_payment(i1["id"], 50, date="2026-10-02", method="UPI")
    assert p.status_code == 201, p.text
    i1_after = client.get(f"/api/invoices/{i1['id']}").json()
    assert i1_after["amountPaid"] == 50
    assert i1_after["balanceDue"] == 50
    assert i1_after["paymentStatus"] == "Partially Paid"
    assert i1_after["invoiceNumber"] == i1["invoiceNumber"]
    assert i1_after["total"] == 100

    i2 = _make_invoice("TEST_P2", "9000010002", rent=100, paid=0)
    assert _add_payment(i2["id"], 50, "2026-10-02").status_code == 201
    assert _add_payment(i2["id"], 50, "2026-10-03").status_code == 201
    i2_after = client.get(f"/api/invoices/{i2['id']}").json()
    assert i2_after["amountPaid"] == 100
    assert i2_after["balanceDue"] == 0
    assert i2_after["paymentStatus"] == "Paid"

    i3 = _make_invoice("TEST_P3", "9000010003", rent=100, paid=0)
    assert _add_payment(i3["id"], 30, "2026-10-02").status_code == 201
    assert _add_payment(i3["id"], 20, "2026-10-03").status_code == 201
    assert _add_payment(i3["id"], 50, "2026-10-04").status_code == 201
    i3_after = client.get(f"/api/invoices/{i3['id']}").json()
    assert i3_after["amountPaid"] == 100
    assert i3_after["paymentStatus"] == "Paid"

    i4 = _make_invoice("TEST_P4", "9000010004", rent=100, paid=0)
    assert _add_payment(i4["id"], 60, "2026-10-02").status_code == 201
    reject = _add_payment(i4["id"], 50, "2026-10-03")
    assert reject.status_code == 422
    assert "remaining balance" in reject.json()["detail"]
    i4_after = client.get(f"/api/invoices/{i4['id']}").json()
    assert i4_after["amountPaid"] == 60
    assert i4_after["balanceDue"] == 40


# Payment scenarios: delete/edit and invoice usability with zero-payment records
def test_payment_delete_edit_and_zero_paid_invoice_usable():
    i5 = _make_invoice("TEST_P5", "9000010005", rent=100, paid=0)
    p = _add_payment(i5["id"], 50, "2026-10-02")
    assert p.status_code == 201
    pid = p.json()["id"]
    d = client.delete(f"/api/payments/{pid}")
    assert d.status_code == 200
    i5_after = client.get(f"/api/invoices/{i5['id']}").json()
    assert i5_after["amountPaid"] == 0
    assert i5_after["balanceDue"] == 100
    assert i5_after["paymentStatus"] == "Pending"

    i6 = _make_invoice("TEST_P6", "9000010006", rent=100, paid=0)
    p2 = _add_payment(i6["id"], 50, "2026-10-02")
    assert p2.status_code == 201
    pid2 = p2.json()["id"]
    upd = client.put(f"/api/payments/{pid2}", json={
        "paymentDate": "2026-10-05",
        "amount": 30,
        "paymentMethod": "Bank Transfer",
        "reference": "utr-1",
        "notes": "edited",
        "invoiceId": "some-other-invoice",
    })
    assert upd.status_code == 200
    i6_after = client.get(f"/api/invoices/{i6['id']}").json()
    assert i6_after["amountPaid"] == 30
    assert i6_after["balanceDue"] == 70
    assert i6_after["invoiceNumber"] == i6["invoiceNumber"]
    payments = client.get(f"/api/invoices/{i6['id']}/payments").json()["payments"]
    assert payments[0]["invoiceId"] == i6["id"]  # PUT cannot reassign invoice

    i7 = _make_invoice("TEST_P7", "9000010007", rent=100, paid=0)
    assert client.get(f"/api/invoices/{i7['id']}/payments").json()["payments"] == []
    assert _add_payment(i7["id"], 25, "2026-10-06", "Card").status_code == 201
    i7_after = client.get(f"/api/invoices/{i7['id']}").json()
    assert i7_after["amountPaid"] == 25
    assert i7_after["balanceDue"] == 75


# Validations and ordering: amount/date/method/invoice checks + date sorting newest first
def test_payment_validation_and_sorting():
    inv = _make_invoice("TEST_VALID", "9000010010", rent=100, paid=0)
    bad_amounts = [
        {"amount": -1},
        {"amount": 0},
        {"amount": "NaN"},
        {"amount": 10.123},
    ]
    for item in bad_amounts:
        payload = {
            "invoiceId": inv["id"], "paymentDate": "2026-10-01", "paymentMethod": "Cash",
            "reference": "", "notes": "", **item,
        }
        r = client.post("/api/payments", json=payload)
        assert r.status_code == 422

    assert _add_payment("does-not-exist", 10, "2026-10-01").status_code == 404
    assert _add_payment(inv["id"], 10, "2026-13-01").status_code == 422
    assert _add_payment(inv["id"], 10, "2026-10-01", "Cheque").status_code == 422

    assert _add_payment(inv["id"], 10, "2026-10-03").status_code == 201
    assert _add_payment(inv["id"], 20, "2026-10-01").status_code == 201
    assert _add_payment(inv["id"], 15, "2026-10-02").status_code == 201
    listed = client.get(f"/api/invoices/{inv['id']}/payments").json()["payments"]
    assert [p["paymentDate"] for p in listed] == ["2026-10-03", "2026-10-02", "2026-10-01"]


# Receipt and persistence: receipt identity stable on edit + backup v4 payment dedupe
def test_receipt_stable_on_edit_and_backup_merge_dedupe():
    inv = _make_invoice("TEST_RCPT", "9000010011", rent=100, paid=0)
    p = _add_payment(inv["id"], 40, "2026-10-01", "UPI")
    assert p.status_code == 201
    pid = p.json()["id"]

    r1 = client.get(f"/api/payments/{pid}/receipt")
    assert r1.status_code == 200
    body1 = r1.json()
    receipt_no = body1["payment"]["receiptNumber"]
    assert body1["invoice_total"] == 100
    assert body1["previousPaid"] == 0
    assert body1["payment"]["amount"] == 40
    assert body1["total_paid"] == 40
    assert body1["balance_due"] == 60
    assert body1["payment_status"] == "PARTIALLY PAID"

    upd = client.put(f"/api/payments/{pid}", json={
        "paymentDate": "2026-10-05",
        "amount": 30,
        "paymentMethod": "Bank Transfer",
        "reference": "new-ref",
        "notes": "edited",
    })
    assert upd.status_code == 200
    assert upd.json()["receiptNumber"] == receipt_no

    r2 = client.get(f"/api/payments/{pid}/receipt")
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["payment"]["receiptNumber"] == receipt_no
    assert body2["previousPaid"] == 0
    assert body2["payment"]["amount"] == 30
    assert body2["total_paid"] == 30
    assert body2["balance_due"] == 70
    assert body2["payment"]["paymentMethod"] == "Bank Transfer"
    assert body2["payment"]["paymentDate"] == "2026-10-05"

    backup = client.get("/api/backup/export").json()
    assert backup["version"] == 4
    assert isinstance(backup.get("payments"), list)
    payment_count = len(backup["payments"])
    merge = client.post("/api/backup/import?mode=merge", json=backup)
    assert merge.status_code == 200
    m = merge.json()
    assert m["payments_added"] == 0
    after = client.get("/api/backup/export").json()
    assert len(after["payments"]) == payment_count


# Legacy migration: preserve prior amountPaid as one migrated payment and stay idempotent
def test_migration_preserves_legacy_paid_and_stays_idempotent():
    payload = {
        "invoices": [{
            "id": "legacy-pay-1",
            "invoiceNumber": "SHPG-2025-0888",
            "invoiceDate": "2025-12-01",
            "billingMonth": "2025-12",
            "tenantName": "Legacy Pay",
            "tenantMobile": "9000099999",
            "rent": 100,
            "subtotal": 100,
            "total": 100,
            "amountPaid": 35,
            "balanceDue": 65,
            "paymentMode": "UPI",
            "paymentStatus": "Partially Paid",
            "createdAt": "2025-12-01T00:00:00+00:00",
            "updatedAt": "2025-12-01T00:00:00+00:00",
        }]
    }
    first = client.post("/api/migrate", json=payload)
    assert first.status_code == 200
    invoice = client.get("/api/invoices/legacy-pay-1").json()
    assert invoice["amountPaid"] == 35
    assert invoice["balanceDue"] == 65
    assert len(invoice["payments"]) == 1
    assert invoice["payments"][0]["amount"] == 35
    assert invoice["payments"][0]["dateInferred"] is True

    second = client.post("/api/migrate", json=payload)
    assert second.status_code == 200
    invoice2 = client.get("/api/invoices/legacy-pay-1").json()
    assert len(invoice2["payments"]) == 1


# FK enforcement/cascade: deleting invoice removes dependent payments
def test_payment_fk_cascade_on_invoice_delete():
    inv = _make_invoice("TEST_FK", "9000010012", rent=100, paid=0)
    p = _add_payment(inv["id"], 40, "2026-10-01")
    assert p.status_code == 201
    pid = p.json()["id"]

    deleted = client.delete(f"/api/invoices/{inv['id']}")
    assert deleted.status_code == 200
    payments = client.get("/api/payments").json()
    assert all(item["id"] != pid for item in payments)


# Backup restore flow: export -> delete only test records -> merge restore exact payment IDs/receipts
def test_backup_roundtrip_restores_deleted_test_records_and_advance_credit():
    inv = _make_invoice("TEST_BKP_PAY", "9000011010", rent=100, paid=0)
    p1 = _add_payment(inv["id"], 30, "2026-10-02", "UPI").json()
    p2 = _add_payment(inv["id"], 20, "2026-10-05", "Cash").json()

    advance = client.post("/api/invoices", json={
        "tenantName": "TEST_BKP_ADV",
        "tenantMobile": "9000011011",
        "tenantEmail": "adv-bkp@example.com",
        "billingMonth": "2026-10",
        "rent": 100,
        "amountPaid": 150,
        "allowAdvance": True,
        "paymentMode": "UPI",
        "paymentDate": "2026-10-09",
    })
    assert advance.status_code == 201, advance.text
    adv = advance.json()
    assert adv["creditBalance"] == 50
    assert adv["balanceDue"] == 0

    backup = client.get("/api/backup/export").json()
    exported_inv = next(i for i in backup["invoices"] if i["id"] == inv["id"])
    exported_adv = next(i for i in backup["invoices"] if i["id"] == adv["id"])
    exported_payments = [p for p in backup["payments"] if p["invoiceId"] == inv["id"]]
    assert {p["id"] for p in exported_payments} == {p1["id"], p2["id"]}
    assert {p["receiptNumber"] for p in exported_payments} == {p1["receiptNumber"], p2["receiptNumber"]}
    assert {p["paymentDate"] for p in exported_payments} == {"2026-10-02", "2026-10-05"}

    assert client.delete(f"/api/invoices/{inv['id']}").status_code == 200
    assert client.delete(f"/api/invoices/{adv['id']}").status_code == 200
    assert client.get(f"/api/invoices/{inv['id']}").status_code == 404
    assert client.get(f"/api/invoices/{adv['id']}").status_code == 404

    restored = client.post("/api/backup/import?mode=merge", json=backup)
    assert restored.status_code == 200
    data = restored.json()
    assert data["invoices_added"] >= 2
    assert data["payments_added"] >= 3

    inv_after = client.get(f"/api/invoices/{inv['id']}").json()
    assert inv_after["invoiceNumber"] == exported_inv["invoiceNumber"]
    assert inv_after["total"] == exported_inv["total"]
    assert inv_after["amountPaid"] == exported_inv["amountPaid"] == 50
    assert inv_after["balanceDue"] == exported_inv["balanceDue"] == 50

    payments_after = client.get(f"/api/invoices/{inv['id']}/payments").json()["payments"]
    by_id = {p["id"]: p for p in payments_after}
    for original in exported_payments:
        restored_payment = by_id[original["id"]]
        assert restored_payment["receiptNumber"] == original["receiptNumber"]
        assert restored_payment["paymentDate"] == original["paymentDate"]
        assert restored_payment["amount"] == original["amount"]

    adv_after = client.get(f"/api/invoices/{adv['id']}").json()
    assert adv_after["invoiceNumber"] == exported_adv["invoiceNumber"]
    assert adv_after["total"] == exported_adv["total"] == 100
    assert adv_after["amountPaid"] == exported_adv["amountPaid"] == 150
    assert adv_after["balanceDue"] == 0
    assert adv_after["creditBalance"] == 50


# Payment CRUD impact on overdue/reports/ledger: revenue stays payment-derived, not full billed.
def test_payment_crud_updates_overdue_report_and_dated_ledger_events():
    inv = client.post("/api/invoices", json={
        "tenantName": "TEST_RPT_LEDGER",
        "tenantMobile": "9000011020",
        "tenantEmail": "rpt-ledger@example.com",
        "billingMonth": "2026-11",
        "invoiceDate": "2026-11-01",
        "dueDate": "2024-01-01",
        "rent": 100,
        "amountPaid": 0,
    }).json()

    add = _add_payment(inv["id"], 60, "2026-11-10", "UPI")
    assert add.status_code == 201
    pid = add.json()["id"]

    report_after_add = client.get("/api/reports/monthly", params={"month": "2026-11"}).json()
    assert report_after_add["billed"] >= 100
    assert report_after_add["revenue"] >= 60
    assert report_after_add["revenue"] < report_after_add["billed"]

    overdue_after_add = client.get("/api/invoices/overdue").json()
    row = next(i for i in overdue_after_add["overdue"] if i["id"] == inv["id"])
    assert row["balanceDue"] == 40
    assert row["effectiveStatus"] == "Overdue"

    ledger_add = client.get("/api/tenants/9000011020/ledger").json()
    payment_rows = [r for r in ledger_add["rows"] if r["type"] == "payment"]
    assert payment_rows and payment_rows[-1]["date"] == "2026-11-10"
    assert payment_rows[-1]["receiptNumber"]

    edit = client.put(f"/api/payments/{pid}", json={
        "paymentDate": "2027-01-15",
        "amount": 30,
        "paymentMethod": "Bank Transfer",
        "reference": "rpt-1",
        "notes": "edited",
    })
    assert edit.status_code == 200

    report_after_edit = client.get("/api/reports/monthly", params={"month": "2026-11"}).json()
    assert report_after_edit["revenue"] >= 30
    assert report_after_edit["revenue"] < report_after_edit["billed"]

    ledger_edit = client.get("/api/tenants/9000011020/ledger").json()
    payment_rows_edit = [r for r in ledger_edit["rows"] if r["type"] == "payment"]
    assert payment_rows_edit[-1]["date"] == "2027-01-15"
    assert payment_rows_edit[-1]["paymentMode"] == "Bank Transfer"

    remove = client.delete(f"/api/payments/{pid}")
    assert remove.status_code == 200

    report_after_delete = client.get("/api/reports/monthly", params={"month": "2026-11"}).json()
    assert report_after_delete["revenue"] >= 0
    assert report_after_delete["revenue"] < report_after_delete["billed"]

    overdue_after_delete = client.get("/api/invoices/overdue").json()
    row2 = next(i for i in overdue_after_delete["overdue"] if i["id"] == inv["id"])
    assert row2["balanceDue"] == 100
    ledger_delete = client.get("/api/tenants/9000011020/ledger").json()
    assert all(r["type"] != "payment" for r in ledger_delete["rows"])


# Email API route -> local SMTP transport: immutable CC snapshot, one message, exact attachment, retry.
def test_email_route_loopback_transport_snapshot_retry_and_secret_hygiene(smtp_sink_route, monkeypatch):
    _set_local_smtp(monkeypatch, smtp_sink_route["port"])
    owner = client.get("/api/settings").json()["ownerEmail"]

    created = client.post("/api/invoices", json={
        "tenantName": "TEST_MAIL_ROUTE",
        "tenantMobile": "9000011030",
        "tenantEmail": "snapshot-old@example.com",
        "billingMonth": "2026-10",
        "rent": 100,
    }).json()
    t_upd = client.put("/api/tenants/9000011030", json={"email": "profile-new@example.com"})
    assert t_upd.status_code == 200
    assert client.get(f"/api/invoices/{created['id']}").json()["tenantEmail"] == "snapshot-old@example.com"

    pdf1 = _mk_pdf_bytes("ROUTE-CASE-1")
    req1 = {
        "invoiceId": created["id"],
        "invoiceNumber": created["invoiceNumber"],
        "tenantName": created["tenantName"],
        "billingMonth": created["billingMonth"],
        "total": created["total"],
        "amountPaid": created["amountPaid"],
        "balanceDue": created["balanceDue"],
        "paymentStatus": created["paymentStatus"],
        "ownerEmail": owner,
        "tenantEmail": "payload-tamper@example.com",
        "pdfBase64": base64.b64encode(pdf1).decode(),
        "pdfFilename": "ignored.pdf",
    }
    before = len(smtp_sink_route["handler"].messages)
    sent = client.post("/api/email/invoice", json=req1)
    assert sent.status_code == 200, sent.text
    body = sent.json()
    assert body["owner"] == "sent"
    assert body["tenant"] == "included"
    assert body["cc"] == "snapshot-old@example.com"
    assert "owner@test.local" not in sent.text
    assert "secret" not in sent.text
    assert len(smtp_sink_route["handler"].messages) == before + 1

    msg1 = smtp_sink_route["handler"].messages[-1]
    parsed1 = _parse_message_bytes(msg1["content"])
    assert parsed1["To"] == owner
    assert parsed1["Cc"] == "snapshot-old@example.com"
    assert msg1["rcpt_tos"] == [owner, "snapshot-old@example.com"]
    part1 = next(p for p in parsed1.walk() if p.get_content_type() == "application/pdf")
    assert part1.get_payload(decode=True) == pdf1

    latest = client.get(f"/api/invoices/{created['id']}").json()
    assert latest["emailStatus"]["owner"] == "sent"
    assert latest["emailStatus"]["tenant"] == "included"
    assert client.get("/api/tenants/9000011030").json()["email"] == "profile-new@example.com"

    owner_only = client.post("/api/invoices", json={
        "tenantName": "TEST_MAIL_OWNER_ONLY",
        "tenantMobile": "9000011031",
        "tenantEmail": "",
        "billingMonth": "2026-10",
        "rent": 100,
    }).json()
    pdf2 = _mk_pdf_bytes("ROUTE-CASE-2")
    req2 = {
        "invoiceId": owner_only["id"],
        "invoiceNumber": owner_only["invoiceNumber"],
        "tenantName": owner_only["tenantName"],
        "billingMonth": owner_only["billingMonth"],
        "total": owner_only["total"],
        "amountPaid": owner_only["amountPaid"],
        "balanceDue": owner_only["balanceDue"],
        "paymentStatus": owner_only["paymentStatus"],
        "ownerEmail": owner,
        "tenantEmail": None,
        "sendToTenant": False,
        "pdfBase64": base64.b64encode(pdf2).decode(),
        "pdfFilename": "ignored2.pdf",
    }
    before2 = len(smtp_sink_route["handler"].messages)
    sent2 = client.post("/api/email/invoice", json=req2)
    assert sent2.status_code == 200
    assert sent2.json()["tenant"] == "no-email"
    assert len(smtp_sink_route["handler"].messages) == before2 + 1
    parsed2 = _parse_message_bytes(smtp_sink_route["handler"].messages[-1]["content"])
    assert parsed2.get("Cc") in (None, "")
    assert smtp_sink_route["handler"].messages[-1]["rcpt_tos"] == [owner]
    part2 = next(p for p in parsed2.walk() if p.get_content_type() == "application/pdf")
    assert part2.get_payload(decode=True) == pdf2

    _set_local_smtp(monkeypatch, 9)
    fail = client.post("/api/email/invoice", json=req1)
    assert fail.status_code == 200
    assert fail.json()["owner"] == "failed"
    persisted_fail = client.get(f"/api/invoices/{created['id']}").json()["emailStatus"]
    assert persisted_fail["owner"] == "failed"

    _set_local_smtp(monkeypatch, smtp_sink_route["port"])
    pdf3 = _mk_pdf_bytes("ROUTE-CASE-3-RETRY")
    req3 = {**req1, "pdfBase64": base64.b64encode(pdf3).decode()}
    before3 = len(smtp_sink_route["handler"].messages)
    retry = client.post("/api/email/invoice", json=req3)
    assert retry.status_code == 200
    assert retry.json()["owner"] == "sent"
    assert len(smtp_sink_route["handler"].messages) == before3 + 1
    part3 = next(p for p in _parse_message_bytes(smtp_sink_route["handler"].messages[-1]["content"]).walk()
                 if p.get_content_type() == "application/pdf")
    assert part3.get_payload(decode=True) == pdf3

    sqlite_blob = Path(os.environ["DB_PATH"]).read_bytes()
    assert b"owner@test.local" not in sqlite_blob
    assert b"secret" not in sqlite_blob
    assert "owner@test.local" not in client.get("/api/settings").text
    assert "secret" not in client.get("/api/backup/export").text


# Optional concurrency correctness: two parallel payment attempts should not overpay.
def test_two_parallel_payment_submissions_allow_only_one_success():
    inv = _make_invoice("TEST_PAR_60", "9000011040", rent=100, paid=0)

    payload = {
        "invoiceId": inv["id"],
        "paymentDate": "2026-10-12",
        "amount": 60,
        "paymentMethod": "UPI",
        "reference": "par",
        "notes": "parallel",
    }

    def submit():
        return client.post("/api/payments", json=payload).status_code

    with ThreadPoolExecutor(max_workers=2) as ex:
        statuses = sorted([f.result() for f in [ex.submit(submit), ex.submit(submit)]])

    assert statuses == [201, 422]
    final = client.get(f"/api/invoices/{inv['id']}").json()
    assert final["amountPaid"] == 60
    assert final["balanceDue"] == 40
