"""Backend API tests for Shree Stay Homes & PG Billing app.

Email delivery uses Gmail SMTP only. When SMTP_USER / SMTP_APP_PASSWORD are not
configured in backend/.env, POST /api/email/invoice must return 503 and the
frontend shows "Email failed" with a Retry button — invoice/PDF flows are
unaffected. When credentials ARE configured, set the OWNER_EMAIL env var to a
real inbox before running the live-send test.
"""
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


def _smtp_configured() -> bool:
    try:
        r = requests.post(f"{BASE_URL}/api/email/invoice", json=_payload(), timeout=30)
        return r.status_code != 503
    except Exception:
        return False


SMTP_CONFIGURED = _smtp_configured()


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _payload(**overrides):
    p = {
        "invoiceNumber": "SHPG-2026-9999",
        "tenantName": "Test Tenant",
        "billingMonth": "January 2026",
        "total": 5000.0,
        "amountPaid": 5000.0,
        "balanceDue": 0.0,
        "paymentStatus": "Paid",
        "ownerEmail": "shreehomestaypg@gmail.com",
        "sendToTenant": False,
        "pdfBase64": _MIN_PDF,
        "pdfFilename": "ShreeStayHomesPG_Invoice_SHPG-2026-9999.pdf",
    }
    p.update(overrides)
    return p


# Health check — backend must work with no database at all
def test_root(api):
    r = api.get(f"{BASE_URL}/api/")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_email_invalid_owner_email_422(api):
    r = api.post(f"{BASE_URL}/api/email/invoice", json=_payload(ownerEmail="not-an-email"))
    assert r.status_code == 422


def test_email_invalid_tenant_email_422(api):
    r = api.post(f"{BASE_URL}/api/email/invoice", json=_payload(sendToTenant=True, tenantEmail="bad"))
    assert r.status_code == 422


def test_email_missing_required_422(api):
    r = api.post(f"{BASE_URL}/api/email/invoice", json={"invoiceNumber": "X"})
    assert r.status_code == 422


@pytest.mark.skipif(SMTP_CONFIGURED, reason="SMTP is configured — 503 path not applicable")
def test_email_503_when_smtp_not_configured(api):
    r = api.post(f"{BASE_URL}/api/email/invoice", json=_payload())
    assert r.status_code == 503
    assert "SMTP" in r.json().get("detail", "")


@pytest.mark.skipif(not SMTP_CONFIGURED, reason="SMTP not configured in backend/.env")
def test_email_owner_only_smtp(api):
    r = api.post(f"{BASE_URL}/api/email/invoice", json=_payload())
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("owner") == "sent", d
    assert d.get("attachment") is True
    assert d.get("tenant") in ("skipped", None)


@pytest.mark.skipif(not SMTP_CONFIGURED, reason="SMTP not configured in backend/.env")
def test_email_owner_and_tenant_smtp(api):
    r = api.post(f"{BASE_URL}/api/email/invoice", json=_payload(
        sendToTenant=True, tenantEmail="shreehomestaypg@gmail.com"))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d.get("owner") == "sent"
    assert d.get("tenant") == "sent"


@pytest.mark.skipif(not SMTP_CONFIGURED, reason="SMTP not configured in backend/.env")
def test_email_send_to_tenant_no_email(api):
    r = api.post(f"{BASE_URL}/api/email/invoice", json=_payload(sendToTenant=True))
    assert r.status_code == 200
    assert r.json().get("tenant") == "no-email"
