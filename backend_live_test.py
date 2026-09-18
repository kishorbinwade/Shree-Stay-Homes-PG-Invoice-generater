#!/usr/bin/env python3
"""Non-destructive live backend API verification for baseline check.
Tests the running backend service without mutating or deleting data."""

import requests
import sys

# Backend is running on internal port 8001
BASE_URL = "http://0.0.0.0:8001/api"

def test_endpoint(method, path, description):
    """Test a single endpoint and return result."""
    url = f"{BASE_URL}{path}"
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        status_ok = response.status_code in [200, 201]
        return {
            "path": path,
            "description": description,
            "status_code": response.status_code,
            "success": status_ok,
            "response_size": len(response.text),
            "error": None if status_ok else response.text[:200]
        }
    except Exception as e:
        return {
            "path": path,
            "description": description,
            "status_code": None,
            "success": False,
            "response_size": 0,
            "error": str(e)
        }

def main():
    print("=" * 80)
    print("LIVE BACKEND API BASELINE VERIFICATION")
    print("=" * 80)
    print(f"Backend URL: {BASE_URL}")
    print()
    
    # Non-destructive read-only endpoints
    tests = [
        ("GET", "/", "Health check"),
        ("GET", "/settings", "Settings read"),
        ("GET", "/invoices/next-number", "Invoice next number"),
        ("GET", "/dashboard/stats", "Dashboard statistics"),
        ("GET", "/invoices", "List invoices (empty/existing)"),
        ("GET", "/tenants", "List tenants (empty/existing)"),
        ("GET", "/expenses", "List expenses (empty/existing)"),
        ("GET", "/food-orders", "List food orders (empty/existing)"),
        ("GET", "/invoices/overdue", "Overdue invoices"),
        ("GET", "/backup/export", "Backup export (non-destructive)"),
    ]
    
    results = []
    for method, path, description in tests:
        result = test_endpoint(method, path, description)
        results.append(result)
        
        status = "✓ PASS" if result["success"] else "✗ FAIL"
        print(f"{status} | {method:4} {path:30} | {description}")
        if not result["success"]:
            print(f"       Error: {result['error']}")
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for r in results if r["success"])
    failed = sum(1 for r in results if not r["success"])
    
    print(f"Total endpoints tested: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed > 0:
        print()
        print("FAILED ENDPOINTS:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['path']}: {r['error']}")
        sys.exit(1)
    else:
        print()
        print("✓ All baseline endpoints are working correctly!")
        sys.exit(0)

if __name__ == "__main__":
    main()
