"""Backend API tests for Shree Stay Homes & PG Billing app."""
import base64
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://pg-invoice-pro.preview.emergentagent.com").rstrip("/")

# Minimal 1-page PDF (valid) for attachment
_MIN_PDF = base64.b64encode(
    b"%PDF-1.1\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 300]>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000053 00000 n \n0000000102 00000 n \n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n160\n%%EOF"
).decode()


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# Health check
def test_root(api):
    r = api.get(f"{BASE_URL}/api/")
    assert r.status_code == 200
    d = r.json()
    assert d.get("status") == "ok"


def _payload(**overrides):
    p = {
        "invoiceNumber": "SHPG-2026-9999",
        "tenantName": "Test Tenant",
        "billingMonth": "January 2026",
        "total": 5000.0,
        "amountPaid": 5000.0,
        "balanceDue": 0.0,
        "paymentStatus": "Paid",
        "ownerEmail": "delivered@resend.dev",
        "sendToTenant": False,
        "pdfBase64": _MIN_PDF,
        "pdfFilename": "ShreeStayHomesPG_Invoice_SHPG-2026-9999.pdf",
    }
    p.update(overrides)
    return p


# Email invoice endpoint tests
def test_email_owner_only(api):
    r = api.post(f"{BASE_URL}/api/email/invoice", json=_payload())
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("owner") == "sent", d
    assert d.get("tenant") in ("skipped", None)
    # attachment flag must be present and boolean; false when SMTP not configured
    assert "attachment" in d, d
    assert isinstance(d["attachment"], bool)


def test_email_owner_and_tenant(api):
    r = api.post(f"{BASE_URL}/api/email/invoice", json=_payload(
        sendToTenant=True, tenantEmail="delivered@resend.dev"))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("owner") == "sent"
    assert d.get("tenant") == "sent"


def test_email_send_to_tenant_no_email(api):
    r = api.post(f"{BASE_URL}/api/email/invoice", json=_payload(sendToTenant=True))
    assert r.status_code == 200
    d = r.json()
    assert d.get("tenant") == "no-email"


def test_email_invalid_owner_email_422(api):
    r = api.post(f"{BASE_URL}/api/email/invoice", json=_payload(ownerEmail="not-an-email"))
    assert r.status_code == 422


def test_email_invalid_tenant_email_422(api):
    r = api.post(f"{BASE_URL}/api/email/invoice", json=_payload(
        sendToTenant=True, tenantEmail="bad"))
    assert r.status_code == 422


def test_email_missing_required_422(api):
    r = api.post(f"{BASE_URL}/api/email/invoice", json={"invoiceNumber": "X"})
    assert r.status_code == 422
