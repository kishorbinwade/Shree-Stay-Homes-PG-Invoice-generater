"""Read-only public preview API smoke tests for dashboard connectivity and seeded billing data."""

import os

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")


@pytest.fixture(scope="session")
def preview_base_url():
    if not BASE_URL:
        pytest.skip("REACT_APP_BACKEND_URL is not set")
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="session")
def api_client():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


# Dashboard and connectivity
def test_health_ok(api_client, preview_base_url):
    response = api_client.get(f"{preview_base_url}/api/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


# Settings bootstrap endpoint
def test_settings_available(api_client, preview_base_url):
    response = api_client.get(f"{preview_base_url}/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["businessName"] == "SHREE STAY HOMES & PG"
    assert data["invoicePrefix"] == "SHPG"


# Dashboard stats should reflect seeded dataset
def test_dashboard_stats_seeded_counts(api_client, preview_base_url):
    response = api_client.get(f"{preview_base_url}/api/dashboard/stats")
    assert response.status_code == 200
    data = response.json()
    # Preview DB can contain extra records from prior QA iterations; keep lower-bound checks.
    assert data["totalInvoices"] >= 5
    assert float(data["totalBilled"]) >= 38150.0


# Recent invoices list should be present and non-empty
def test_invoices_list_shape(api_client, preview_base_url):
    response = api_client.get(f"{preview_base_url}/api/invoices")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    first = data[0]
    assert isinstance(first["id"], str)
    assert isinstance(first["invoiceNumber"], str)
    assert isinstance(first["tenantName"], str)
