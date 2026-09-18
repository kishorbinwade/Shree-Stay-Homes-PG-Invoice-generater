import os
import re
import json
import time
from pypdf import PdfReader


async def run(page):
    page.on("console", lambda msg: print(f"CONSOLE: {msg.text}"))
    created_invoice_id = None
    created_mobile = None
    result_path = "/app/test_reports/final-local/pdf_invoice_check_result.json"
    os.makedirs("/app/test_reports/final-local", exist_ok=True)

    try:
        await page.set_viewport_size({"width": 1920, "height": 1080})
        print("Step 1: Viewport set")

        base_url = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
        if not base_url:
            raise Exception("REACT_APP_BACKEND_URL missing")
        print(f"Step 2: Using base URL: {base_url}")

        tag = str(int(time.time()))
        created_mobile = f"9{tag[-9:]}"
        tenant_name = f"TEST_FINAL_PDF_invoice100_{tag}"

        create_payload = {
            "tenantName": tenant_name,
            "tenantMobile": created_mobile,
            "tenantEmail": "",
            "roomNumber": "R100",
            "billingMonth": "2026-10",
            "rent": 100,
            "amountPaid": 0,
            "paymentMode": "Cash",
        }
        create_resp = await page.request.post(f"{base_url}/api/invoices", json=create_payload)
        if create_resp.status != 201:
            raise Exception(f"Invoice create failed: {create_resp.status} {await create_resp.text()}")
        invoice = await create_resp.json()
        created_invoice_id = invoice["id"]
        invoice_number = invoice["invoiceNumber"]
        print(f"Step 3: Created invoice {invoice_number}")

        for amount, pdate in [(30, "2026-10-02"), (20, "2026-10-03")]:
            pay_resp = await page.request.post(f"{base_url}/api/payments", json={
                "invoiceId": created_invoice_id,
                "paymentDate": pdate,
                "amount": amount,
                "paymentMethod": "UPI",
                "reference": f"TEST_FINAL_PDF_{amount}",
                "notes": "final local verification",
            })
            if pay_resp.status != 201:
                raise Exception(f"Payment {amount} failed: {pay_resp.status} {await pay_resp.text()}")
        print("Step 4: Added payments 30 + 20")

        inv_resp = await page.request.get(f"{base_url}/api/invoices/{created_invoice_id}")
        latest = await inv_resp.json()
        if float(latest.get("total", 0)) != 100 or float(latest.get("amountPaid", 0)) != 50 or float(latest.get("balanceDue", 0)) != 50:
            raise Exception(f"Invoice totals mismatch: {latest}")
        print("Step 5: API totals validated (total=100, paid=50, due=50)")

        await page.goto(f"{base_url}/invoices/{created_invoice_id}", wait_until="domcontentloaded")
        await page.wait_for_selector('[data-testid="invoice-details-download"]', timeout=10000)
        await page.wait_for_selector('[data-testid="invoice-total"]', timeout=10000)
        print("Step 6: Invoice details page loaded")

        pdf_path = f"/app/test_reports/final-local/TEST_FINAL_PDF_{invoice_number}.pdf"
        async with page.expect_download() as info:
            await page.get_by_test_id("invoice-details-download").click(force=True)
        download = await info.value
        suggested_name = download.suggested_filename
        await download.save_as(pdf_path)
        print(f"Step 7: Downloaded invoice PDF to {pdf_path}")

        if "receipt" in suggested_name.lower():
            raise Exception(f"Filename looks like receipt, expected invoice: {suggested_name}")
        if "invoice" not in suggested_name.lower() and "invoice" not in os.path.basename(pdf_path).lower():
            raise Exception(f"Invoice filename marker missing: {suggested_name}")

        reader = PdfReader(pdf_path)
        text = "\n".join([(p.extract_text() or "") for p in reader.pages])
        normalized = " ".join(text.split())
        print(f"Step 8: Parsed PDF text length={len(normalized)}")

        checks = {
            "invoice_number": invoice_number in normalized,
            "total_100": bool(re.search(r"Total\s*Amount\s*(?:Rs\.?|₹)?\s*100(?:\.00)?", normalized, re.IGNORECASE)),
            "paid_50": bool(re.search(r"Amount\s*Paid\s*(?:Rs\.?|₹)?\s*50(?:\.00)?", normalized, re.IGNORECASE)),
            "due_50": bool(re.search(r"Balance\s*Due\s*(?:Rs\.?|₹)?\s*50(?:\.00)?", normalized, re.IGNORECASE)),
        }
        if not all(checks.values()):
            raise Exception(f"PDF semantic checks failed: {checks}")
        print("Step 9: PDF values validated (original total 100, paid 50, due 50)")

        with open(result_path, "w", encoding="utf-8") as f:
            json.dump({
                "status": "passed",
                "invoice_id": created_invoice_id,
                "invoice_number": invoice_number,
                "downloaded_pdf": pdf_path,
                "suggested_filename": suggested_name,
                "checks": checks,
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
        print(f"PDF script failed: {str(e)}")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump({"status": "failed", "error": str(e)}, f, indent=2)
        raise
    finally:
        if created_invoice_id:
            try:
                await page.request.delete(f"{base_url}/api/invoices/{created_invoice_id}")
                print("Cleanup: deleted test invoice")
            except Exception as cleanup_err:
                print(f"Cleanup warning (invoice): {cleanup_err}")
        if created_mobile:
            try:
                await page.request.delete(f"{base_url}/api/tenants/{created_mobile}")
                print("Cleanup: deleted test tenant")
            except Exception as cleanup_err:
                print(f"Cleanup warning (tenant): {cleanup_err}")


await run(page)
