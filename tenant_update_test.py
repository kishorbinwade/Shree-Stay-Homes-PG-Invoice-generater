#!/usr/bin/env python3
"""
Focused test for tenant update endpoint (PUT /api/tenants/{id})
Tests ONLY the new "Edit Tenant" feature as requested.
"""
import requests
import sys

# Backend URL from frontend/.env
BASE_URL = "https://code-preview-intact.preview.emergentagent.com/api"

def test_tenant_update():
    """Test the tenant update endpoint following the exact steps in the review request."""
    print("=" * 80)
    print("TENANT UPDATE ENDPOINT TEST")
    print("=" * 80)
    
    results = {
        "step1_get_tenants": False,
        "step2_put_update": False,
        "step3_verify_response": False,
        "step4_get_tenant_by_id": False,
        "step5_verify_no_duplicate": False,
        "step6_put_nonexistent": False,
    }
    
    # Step 1: GET /api/tenants — pick the first existing tenant
    print("\n[Step 1] GET /api/tenants - Fetch existing tenants")
    try:
        response = requests.get(f"{BASE_URL}/tenants", timeout=10)
        print(f"  Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"  ❌ FAILED: Expected 200, got {response.status_code}")
            print(f"  Response: {response.text}")
            return results
        
        tenants = response.json()
        print(f"  ✅ SUCCESS: Found {len(tenants)} tenant(s)")
        
        if not tenants:
            print("  ❌ FAILED: No tenants found in database")
            return results
        
        # Pick the first tenant
        tenant = tenants[0]
        tenant_id = tenant.get("id")
        original_name = tenant.get("name", "")
        original_mobile = tenant.get("mobile", "")
        original_email = tenant.get("email", "")
        original_rent = tenant.get("rent", 0)
        original_deposit = tenant.get("deposit", 0)
        
        print(f"  Selected tenant ID: {tenant_id}")
        print(f"  Original values:")
        print(f"    - name: {original_name}")
        print(f"    - mobile: {original_mobile}")
        print(f"    - email: {original_email}")
        print(f"    - rent: {original_rent}")
        print(f"    - deposit: {original_deposit}")
        
        results["step1_get_tenants"] = True
        
    except Exception as e:
        print(f"  ❌ FAILED: {type(e).__name__}: {e}")
        return results
    
    # Step 2: PUT /api/tenants/{id} with updated values
    print("\n[Step 2] PUT /api/tenants/{id} - Update tenant details")
    
    # New values as specified in the review request
    new_mobile = "9812345678"
    new_email = "updated.tenant@example.com"
    new_rent = 9500
    new_deposit = 19000
    
    update_payload = {
        "mobile": new_mobile,
        "email": new_email,
        "rent": new_rent,
        "deposit": new_deposit
    }
    
    print(f"  Updating tenant {tenant_id} with:")
    print(f"    - mobile: {new_mobile}")
    print(f"    - email: {new_email}")
    print(f"    - rent: {new_rent}")
    print(f"    - deposit: {new_deposit}")
    
    try:
        response = requests.put(
            f"{BASE_URL}/tenants/{tenant_id}",
            json=update_payload,
            timeout=10
        )
        print(f"  Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"  ❌ FAILED: Expected 200, got {response.status_code}")
            print(f"  Response: {response.text}")
            return results
        
        results["step2_put_update"] = True
        
        # Step 3: Verify the PUT response contains the updated values
        print("\n[Step 3] Verify PUT response contains updated values")
        updated_tenant = response.json()
        
        print(f"  Response tenant data:")
        print(f"    - id: {updated_tenant.get('id')}")
        print(f"    - name: {updated_tenant.get('name')}")
        print(f"    - mobile: {updated_tenant.get('mobile')}")
        print(f"    - email: {updated_tenant.get('email')}")
        print(f"    - rent: {updated_tenant.get('rent')}")
        print(f"    - deposit: {updated_tenant.get('deposit')}")
        
        # Verify each updated field
        checks = []
        if updated_tenant.get("mobile") == new_mobile:
            print(f"  ✅ mobile updated correctly: {new_mobile}")
            checks.append(True)
        else:
            print(f"  ❌ mobile mismatch: expected {new_mobile}, got {updated_tenant.get('mobile')}")
            checks.append(False)
        
        if updated_tenant.get("email") == new_email:
            print(f"  ✅ email updated correctly: {new_email}")
            checks.append(True)
        else:
            print(f"  ❌ email mismatch: expected {new_email}, got {updated_tenant.get('email')}")
            checks.append(False)
        
        if updated_tenant.get("rent") == new_rent:
            print(f"  ✅ rent updated correctly: {new_rent}")
            checks.append(True)
        else:
            print(f"  ❌ rent mismatch: expected {new_rent}, got {updated_tenant.get('rent')}")
            checks.append(False)
        
        if updated_tenant.get("deposit") == new_deposit:
            print(f"  ✅ deposit updated correctly: {new_deposit}")
            checks.append(True)
        else:
            print(f"  ❌ deposit mismatch: expected {new_deposit}, got {updated_tenant.get('deposit')}")
            checks.append(False)
        
        if all(checks):
            results["step3_verify_response"] = True
        else:
            print("  ❌ FAILED: Not all fields updated correctly in response")
            return results
        
    except Exception as e:
        print(f"  ❌ FAILED: {type(e).__name__}: {e}")
        return results
    
    # Step 4: GET /api/tenants/{id} — verify persistence
    print("\n[Step 4] GET /api/tenants/{id} - Verify persistence")
    try:
        response = requests.get(f"{BASE_URL}/tenants/{tenant_id}", timeout=10)
        print(f"  Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"  ❌ FAILED: Expected 200, got {response.status_code}")
            print(f"  Response: {response.text}")
            return results
        
        persisted_tenant = response.json()
        
        print(f"  Persisted tenant data:")
        print(f"    - id: {persisted_tenant.get('id')}")
        print(f"    - name: {persisted_tenant.get('name')}")
        print(f"    - mobile: {persisted_tenant.get('mobile')}")
        print(f"    - email: {persisted_tenant.get('email')}")
        print(f"    - rent: {persisted_tenant.get('rent')}")
        print(f"    - deposit: {persisted_tenant.get('deposit')}")
        
        # Verify persistence
        checks = []
        if persisted_tenant.get("mobile") == new_mobile:
            print(f"  ✅ mobile persisted correctly: {new_mobile}")
            checks.append(True)
        else:
            print(f"  ❌ mobile not persisted: expected {new_mobile}, got {persisted_tenant.get('mobile')}")
            checks.append(False)
        
        if persisted_tenant.get("email") == new_email:
            print(f"  ✅ email persisted correctly: {new_email}")
            checks.append(True)
        else:
            print(f"  ❌ email not persisted: expected {new_email}, got {persisted_tenant.get('email')}")
            checks.append(False)
        
        if persisted_tenant.get("rent") == new_rent:
            print(f"  ✅ rent persisted correctly: {new_rent}")
            checks.append(True)
        else:
            print(f"  ❌ rent not persisted: expected {new_rent}, got {persisted_tenant.get('rent')}")
            checks.append(False)
        
        if persisted_tenant.get("deposit") == new_deposit:
            print(f"  ✅ deposit persisted correctly: {new_deposit}")
            checks.append(True)
        else:
            print(f"  ❌ deposit not persisted: expected {new_deposit}, got {persisted_tenant.get('deposit')}")
            checks.append(False)
        
        if all(checks):
            results["step4_get_tenant_by_id"] = True
        else:
            print("  ❌ FAILED: Not all fields persisted correctly")
            return results
        
    except Exception as e:
        print(f"  ❌ FAILED: {type(e).__name__}: {e}")
        return results
    
    # Step 5: GET /api/tenants — verify no duplicate created
    print("\n[Step 5] GET /api/tenants - Verify no duplicate created")
    try:
        response = requests.get(f"{BASE_URL}/tenants", timeout=10)
        print(f"  Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"  ❌ FAILED: Expected 200, got {response.status_code}")
            print(f"  Response: {response.text}")
            return results
        
        all_tenants = response.json()
        print(f"  Total tenants in database: {len(all_tenants)}")
        
        # Count how many times our tenant_id appears
        matching_tenants = [t for t in all_tenants if t.get("id") == tenant_id]
        print(f"  Tenants with ID {tenant_id}: {len(matching_tenants)}")
        
        if len(matching_tenants) == 1:
            print(f"  ✅ SUCCESS: Tenant appears exactly once (no duplicate)")
            results["step5_verify_no_duplicate"] = True
        else:
            print(f"  ❌ FAILED: Tenant appears {len(matching_tenants)} times (expected 1)")
            return results
        
    except Exception as e:
        print(f"  ❌ FAILED: {type(e).__name__}: {e}")
        return results
    
    # Step 6: PUT /api/tenants/nonexistent-id — expect 404
    print("\n[Step 6] PUT /api/tenants/nonexistent-id - Expect 404")
    nonexistent_id = "nonexistent-tenant-id-12345"
    
    try:
        response = requests.put(
            f"{BASE_URL}/tenants/{nonexistent_id}",
            json={"mobile": "9812345678"},
            timeout=10
        )
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 404:
            print(f"  ✅ SUCCESS: Correctly returned 404 for nonexistent tenant")
            results["step6_put_nonexistent"] = True
        else:
            print(f"  ❌ FAILED: Expected 404, got {response.status_code}")
            print(f"  Response: {response.text}")
            return results
        
    except Exception as e:
        print(f"  ❌ FAILED: {type(e).__name__}: {e}")
        return results
    
    return results


def main():
    print("\n" + "=" * 80)
    print("TENANT UPDATE FEATURE TEST")
    print("Testing ONLY the new Edit Tenant functionality")
    print("=" * 80)
    
    results = test_tenant_update()
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    for step, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {step}")
    
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED - Tenant update endpoint working correctly!")
        return 0
    else:
        print(f"\n❌ {total_tests - passed_tests} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
