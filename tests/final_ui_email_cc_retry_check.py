import os
import json
import time


async def run(page):
    page.on("console", lambda msg: print(f"CONSOLE: {msg.text}"))
    result_path = "/app/test_reports/final-local/email_ui_check_result.json"
    os.makedirs("/app/test_reports/final-local", exist_ok=True)

    created_invoice_ids = []
    created_mobiles = []
    ui_created_invoice_id = None
    base_url = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
    if not base_url:
        raise Exception("REACT_APP_BACKEND_URL missing")

    try:
        await page.set_viewport_size({"width": 1920, "height": 1080})
        print("Step 1: Viewport set")

        tag = str(int(time.time()))
        t1 = {
            "name": f"TEST_FINAL_EMAIL1_{tag}",
            "mobile": f"91{tag[-8:]}",
            "email": f"test_email1_{tag}@example.com",
            "room": "E101",
        }
        t2 = {
            "name": f"TEST_FINAL_EMAIL2_{tag}",
            "mobile": f"92{tag[-8:]}",
            "email": f"test_email2_{tag}@example.com",
            "room": "E102",
        }
        t3 = {
            "name": f"TEST_FINAL_EMAIL_NO_{tag}",
            "mobile": f"93{tag[-8:]}",
            "email": "",
            "room": "E103",
        }
        tenants_seed = [t1, t2, t3]

        for t in tenants_seed:
            created_mobiles.append(t["mobile"])
            resp = await page.request.post(f"{base_url}/api/invoices", json={
                "tenantName": t["name"],
                "tenantMobile": t["mobile"],
                "tenantEmail": t["email"],
                "roomNumber": t["room"],
                "billingMonth": "2026-10",
                "rent": 10,
                "amountPaid": 0,
            })
            if resp.status != 201:
                raise Exception(f"Seed invoice failed for {t['name']}: {resp.status} {await resp.text()}")
            created_invoice_ids.append((await resp.json())["id"])
        print("Step 2: Created three tagged tenants via API")

        tenants_resp = await page.request.get(f"{base_url}/api/tenants")
        all_tenants = await tenants_resp.json()
        by_mobile = {t.get("mobile"): t for t in all_tenants}
        for t in tenants_seed:
            if t["mobile"] not in by_mobile:
                raise Exception(f"Tenant missing from list: {t['mobile']}")
            t["id"] = by_mobile[t["mobile"]]["id"]
        print("Step 3: Resolved tenant suggestion IDs")

        email_calls = {"count": 0}

        def on_request(req):
            if req.method == "POST" and "/api/email/invoice" in req.url:
                email_calls["count"] += 1

        page.on("request", on_request)

        await page.goto(f"{base_url}/invoices/new", wait_until="domcontentloaded")
        await page.wait_for_selector('[data-testid="tenant-name"]', timeout=12000)
        await page.wait_for_selector('[data-testid="invoice-email-cc"]', timeout=12000)
        print("Step 4: Create Invoice page loaded")

        send_toggle = page.get_by_test_id("send-invoice-email")
        send_state = await send_toggle.get_attribute("data-state")
        if send_state != "unchecked":
            await send_toggle.click(force=True)
            await page.wait_for_timeout(300)
        final_send_state = await send_toggle.get_attribute("data-state")
        if final_send_state != "unchecked":
            raise Exception("send-invoice-email is not unchecked")
        print("Step 5: Disabled auto send-invoice-email before generate")

        tenant_input = page.get_by_test_id("tenant-name")
        cc_input = page.get_by_test_id("invoice-email-cc")

        await tenant_input.fill(t1["name"][:14])
        await page.wait_for_selector(f'[data-testid="tenant-suggestion-{t1["id"]}"]', timeout=8000)
        await page.get_by_test_id(f"tenant-suggestion-{t1['id']}").click(force=True)
        await page.wait_for_timeout(300)
        cc1 = await cc_input.input_value()
        cc_readonly = await cc_input.get_attribute("readonly")
        if cc1 != t1["email"] or cc_readonly is None:
            raise Exception(f"CC after tenant1 incorrect: cc={cc1}, readonly={cc_readonly}")
        print("Step 6: Tenant1 selected; CC readonly set to email1")

        await tenant_input.fill(t2["name"][:14])
        await page.wait_for_timeout(250)
        cc_mid = await cc_input.input_value()
        if cc_mid != "":
            raise Exception(f"CC not cleared while typing tenant2: {cc_mid}")
        await page.wait_for_selector(f'[data-testid="tenant-suggestion-{t2["id"]}"]', timeout=8000)
        await page.get_by_test_id(f"tenant-suggestion-{t2['id']}").click(force=True)
        await page.wait_for_timeout(300)
        cc2 = await cc_input.input_value()
        if cc2 != t2["email"]:
            raise Exception(f"CC after tenant2 incorrect: {cc2}")
        print("Step 7: Tenant2 selected; CC switched to email2")

        await tenant_input.fill(t3["name"][:14])
        await page.wait_for_timeout(250)
        cc_mid2 = await cc_input.input_value()
        if cc_mid2 != "":
            raise Exception(f"CC not cleared while typing tenant3: {cc_mid2}")
        await page.wait_for_selector(f'[data-testid="tenant-suggestion-{t3["id"]}"]', timeout=8000)
        await page.get_by_test_id(f"tenant-suggestion-{t3['id']}").click(force=True)
        await page.wait_for_timeout(300)
        cc3 = await cc_input.input_value()
        if cc3 != "":
            raise Exception(f"CC should be empty for no-email tenant: {cc3}")
        print("Step 8: No-email tenant selected; CC remains empty")

        await page.get_by_test_id("room-number").fill("E103")
        await page.get_by_test_id("charge-rent").fill("100")
        await page.get_by_test_id("amount-paid").fill("0")
        print("Step 9: Filled required invoice fields")

        await page.get_by_test_id("generate-invoice-btn").click(force=True)
        await page.wait_for_selector('[data-testid="generate-success-message"]', timeout=12000)
        await page.wait_for_timeout(700)
        if email_calls["count"] != 0:
            raise Exception(f"/api/email/invoice called during save: {email_calls['count']}")
        print("Step 10: Invoice saved with zero automatic email API calls")

        manage_href = await page.get_by_test_id("manage-invoice-payments").get_attribute("href")
        if manage_href and "/invoices/" in manage_href:
            ui_created_invoice_id = manage_href.split("/invoices/")[-1]

        await page.get_by_test_id("email-invoice-btn").click(force=True)
        await page.wait_for_timeout(1800)
        owner_status_text = await page.get_by_test_id("email-status-owner").inner_text()
        retry_visible = await page.get_by_test_id("retry-email-btn").is_visible()
        if "Failed" not in owner_status_text or not retry_visible:
            raise Exception(f"First email fail state not shown. status={owner_status_text}, retry={retry_visible}")
        print("Step 11: First explicit email shows failed state + retry button")

        await page.get_by_test_id("retry-email-btn").click(force=True)
        await page.wait_for_timeout(1800)
        owner_status_text_2 = await page.get_by_test_id("email-status-owner").inner_text()
        page_ok = await page.get_by_test_id("create-invoice-page").is_visible()
        if "Failed" not in owner_status_text_2 or not page_ok:
            raise Exception(f"Retry fail state missing or page crashed. status={owner_status_text_2}, page_ok={page_ok}")
        print("Step 12: Retry preserves fail state without crash")

        with open(result_path, "w", encoding="utf-8") as f:
            json.dump({
                "status": "passed",
                "tenants": tenants_seed,
                "ui_created_invoice_id": ui_created_invoice_id,
                "email_call_count_on_save": email_calls["count"],
                "owner_status_after_retry": owner_status_text_2,
            }, f, indent=2)

        # Get error messages using specific selectors
        error_text = await page.evaluate("""() => {
const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
return errorElements.map(el => el.textContent).join(", ");
}""")
        if error_text:
            print(f"Found error message: {error_text}")
        else:
            print("No error messages found on the page")

    except Exception as e:
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump({"status": "failed", "error": str(e)}, f, indent=2)
        print(f"Email UI script failed: {str(e)}")
        raise

    finally:
        cleanup_invoice_ids = list(created_invoice_ids)
        if ui_created_invoice_id:
            cleanup_invoice_ids.append(ui_created_invoice_id)

        for inv_id in cleanup_invoice_ids:
            try:
                await page.request.delete(f"{base_url}/api/invoices/{inv_id}")
            except Exception as cleanup_err:
                print(f"Cleanup warning (invoice {inv_id}): {cleanup_err}")

        for mobile in created_mobiles:
            try:
                await page.request.delete(f"{base_url}/api/tenants/{mobile}")
            except Exception as cleanup_err:
                print(f"Cleanup warning (tenant {mobile}): {cleanup_err}")


await run(page)
