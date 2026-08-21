from datetime import datetime
from fastapi import FastAPI, APIRouter, HTTPException, Body
from fastapi.responses import JSONResponse, Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import re
import ipaddress
import logging
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator, model_validator
import asyncio
import base64
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formataddr

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import database as db

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Shree Stay Homes & PG")
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")

# Gmail SMTP is the ONLY email path — invoices are sent as multipart/mixed
# with the real PDF attachment. Credentials live only in backend/.env.
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_APP_PASSWORD = os.environ.get("SMTP_APP_PASSWORD", "")
SMTP_TLS = os.environ.get("SMTP_TLS", "true").lower() != "false"
SMTP_CONFIGURED = bool(SMTP_USER and SMTP_APP_PASSWORD)

# ---- Guardrail gate (structural defense for email safety) ----
_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r}")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r}")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r}")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r}")


def inr(n) -> str:
    n = round(float(n or 0), 2)
    sign = "-" if n < 0 else ""
    s = f"{abs(n):.2f}"
    whole, frac = s.split(".")
    if len(whole) > 3:
        last3 = whole[-3:]
        rest = whole[:-3]
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        whole = ",".join(parts + [last3])
    return f"{sign}{whole}.{frac}"


class InvoiceEmailRequest(BaseModel):
    invoiceNumber: str
    tenantName: str
    billingMonth: str
    total: float
    amountPaid: float
    balanceDue: float
    paymentStatus: str = ""
    ownerEmail: EmailStr
    tenantEmail: Optional[EmailStr] = None
    sendToTenant: bool = False
    pdfBase64: str
    pdfFilename: str = "invoice.pdf"


def invoice_email_html(d: InvoiceEmailRequest) -> str:
    row = lambda k, v: (f'<tr><td style="padding:8px 16px;color:#5C5A57;font-size:14px;">{k}</td>'
                        f'<td style="padding:8px 16px;font-size:14px;font-weight:600;color:#1C1B1A;" align="right">{v}</td></tr>')
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F7F5F2;padding:24px 0;">'
        '<tr><td align="center">'
        '<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border:1px solid #E6E4E0;border-radius:12px;overflow:hidden;font-family:Arial,sans-serif;">'
        f'<tr><td style="background:#D85C40;padding:20px 24px;"><span style="color:#ffffff;font-size:18px;font-weight:bold;">{escape(EMAIL_FROM_NAME)}</span><br/>'
        '<span style="color:#FBE3DC;font-size:12px;">PG Accommodation &amp; Stay Services</span></td></tr>'
        f'<tr><td style="padding:20px 24px 4px;font-size:15px;color:#1C1B1A;">Dear {escape(d.tenantName)},</td></tr>'
        '<tr><td style="padding:4px 24px 12px;font-size:14px;color:#5C5A57;">Your PG invoice is attached to this email as a PDF. Summary below:</td></tr>'
        '<tr><td style="padding:0 8px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
        + row("Invoice Number", escape(d.invoiceNumber))
        + row("Billing Month", escape(d.billingMonth))
        + row("Total Amount", f"&#8377;{inr(d.total)}")
        + row("Amount Paid", f"&#8377;{inr(d.amountPaid)}")
        + row("Balance Due", f"&#8377;{inr(d.balanceDue)}")
        + row("Payment Status", escape(d.paymentStatus or "-"))
        + '</table></td></tr>'
        '<tr><td style="padding:20px 24px;border-top:1px solid #E6E4E0;margin-top:12px;font-size:12px;color:#8A8885;">'
        f'This invoice is generated by {escape(EMAIL_FROM_NAME)}.</td></tr>'
        '</table></td></tr></table>'
    )


async def send_invoice_email(to: str, subject: str, html: str, pdf_b64: str, filename: str) -> None:
    """Send one invoice email via Gmail SMTP with the PDF attached."""
    _assert_safe_email(subject, html)
    await send_smtp_email(to, subject, html, pdf_b64, filename)


def _send_smtp_sync(to: str, subject: str, html: str, pdf_bytes: bytes, filename: str) -> None:
    msg = MIMEMultipart("mixed")
    msg["From"] = formataddr((EMAIL_FROM_NAME, SMTP_USER))
    msg["To"] = to
    msg["Subject"] = subject
    if EMAIL_REPLY_TO:
        msg["Reply-To"] = EMAIL_REPLY_TO
    msg.attach(MIMEText(html, "html", "utf-8"))
    part = MIMEApplication(pdf_bytes, _subtype="pdf")
    part.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(part)
    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.ehlo()
        if SMTP_TLS:
            server.starttls(context=context)
            server.ehlo()
        server.login(SMTP_USER, SMTP_APP_PASSWORD)
        server.sendmail(SMTP_USER, [to], msg.as_string())


def smtp_error_message(e: Exception) -> str:
    if isinstance(e, smtplib.SMTPAuthenticationError):
        return "Gmail authentication failed — check SMTP_USER and SMTP_APP_PASSWORD (use a Gmail App Password, not your Gmail password)"
    if isinstance(e, smtplib.SMTPServerDisconnected):
        return "SMTP server dropped the connection — check SMTP credentials and settings"
    if isinstance(e, smtplib.SMTPResponseException):
        return f"SMTP server rejected the email (code {e.smtp_code})"
    if isinstance(e, smtplib.SMTPException):
        return "SMTP error while sending email — check SMTP settings"
    if isinstance(e, (ConnectionRefusedError, TimeoutError, OSError)):
        return f"Could not reach SMTP server {SMTP_HOST}:{SMTP_PORT} — check internet connection and SMTP settings"
    return "Email delivery failed"


async def send_smtp_email(to: str, subject: str, html: str, pdf_b64: str, filename: str) -> None:
    pdf_bytes = base64.b64decode(pdf_b64)
    await asyncio.to_thread(_send_smtp_sync, to, subject, html, pdf_bytes, filename)


@api_router.get("/")
async def root():
    return {"status": "ok", "app": "Shree Stay Homes & PG Billing"}


@api_router.post("/email/invoice")
async def email_invoice(payload: InvoiceEmailRequest):
    if not SMTP_CONFIGURED:
        raise HTTPException(
            status_code=503,
            detail="Gmail SMTP is not configured. Set SMTP_USER and SMTP_APP_PASSWORD in backend/.env and restart the backend.",
        )
    if len(payload.pdfBase64) > 14_000_000:
        raise HTTPException(status_code=413, detail="PDF attachment too large")
    filename = re.sub(r"[^A-Za-z0-9_.-]", "_", payload.pdfFilename) or "invoice.pdf"
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    subject = re.sub(r"[\r\n]+", " ", f"PG Invoice {payload.invoiceNumber} - {payload.tenantName}")[:150]
    body = invoice_email_html(payload)
    result = {"owner": "failed", "tenant": "skipped", "errors": {}, "attachment": True}
    try:
        await send_invoice_email(str(payload.ownerEmail), subject, body, payload.pdfBase64, filename)
        result["owner"] = "sent"
    except Exception as e:
        logger.error(f"Owner email failed: {type(e).__name__}")
        result["errors"]["owner"] = smtp_error_message(e)
    if payload.sendToTenant:
        if payload.tenantEmail:
            try:
                await send_invoice_email(str(payload.tenantEmail), subject, body, payload.pdfBase64, filename)
                result["tenant"] = "sent"
            except Exception as e:
                logger.error(f"Tenant email failed: {type(e).__name__}")
                result["tenant"] = "failed"
                result["errors"]["tenant"] = smtp_error_message(e)
        else:
            result["tenant"] = "no-email"
    return result


# ---------- Billing data API (SQLite) ----------

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class InvoiceIn(BaseModel):
    tenantName: str
    tenantEmail: Optional[str] = ""
    tenantMobile: str = ""
    roomNumber: str = ""
    bedNumber: str = ""
    checkIn: str = ""
    checkOut: str = ""
    occupation: str = ""
    emergencyContact: str = ""
    invoiceDate: Optional[str] = None
    billingMonth: str = ""
    dueDate: str = ""
    rent: float = 0
    securityDeposit: float = 0
    electricity: float = 0
    food: float = 0
    maintenance: float = 0
    otherCharges: float = 0
    discount: float = 0
    previousBalance: float = 0
    amountPaid: float = 0
    paymentMode: str = "Cash"
    transactionId: str = ""
    sendToTenant: bool = False
    emailStatus: Optional[dict] = None
    notes: str = ""

    @field_validator("tenantEmail")
    @classmethod
    def _email_ok(cls, v):
        v = (v or "").strip()
        if v and not EMAIL_RE.match(v):
            raise ValueError("Invalid tenant email address")
        return v

    @model_validator(mode="after")
    def _amounts_ok(self):
        for k in ("rent", "securityDeposit", "electricity", "food", "maintenance",
                  "otherCharges", "discount", "previousBalance", "amountPaid"):
            if getattr(self, k) < 0:
                raise ValueError(f"{k} cannot be negative")
        if not self.tenantName.strip():
            raise ValueError("Tenant name is required")
        return self


class MigratePayload(BaseModel):
    invoices: list = []
    tenants: list = []
    settings: Optional[dict] = None


@api_router.get("/invoices/next-number")
async def api_next_number():
    return {"nextNumber": db.peek_next_number()}


@api_router.get("/invoices")
async def api_list_invoices(q: Optional[str] = None, month: Optional[str] = None,
                            status: Optional[str] = None, order: str = "desc"):
    return db.list_invoices(q=q, month=month, status=status, order=order)


@api_router.post("/invoices", status_code=201)
async def api_create_invoice(payload: InvoiceIn):
    return db.create_invoice(payload.model_dump())


@api_router.get("/invoices/overdue")
async def api_overdue():
    return db.overdue_invoices()


@api_router.get("/invoices/{inv_id}")
async def api_get_invoice(inv_id: str):
    inv = db.get_invoice(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


@api_router.put("/invoices/{inv_id}")
async def api_update_invoice(inv_id: str, payload: InvoiceIn):
    inv = db.update_invoice(inv_id, payload.model_dump())
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


@api_router.delete("/invoices/{inv_id}")
async def api_delete_invoice(inv_id: str):
    if not db.delete_invoice(inv_id):
        raise HTTPException(status_code=404, detail="Invoice not found")
    return {"deleted": True}


@api_router.get("/tenants")
async def api_list_tenants():
    return db.list_tenants()


@api_router.get("/tenants/{tid}")
async def api_get_tenant(tid: str):
    t = db.get_tenant(tid)
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return t


@api_router.delete("/tenants/{tid}")
async def api_delete_tenant(tid: str):
    if not db.delete_tenant(tid):
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {"deleted": True}


@api_router.get("/settings")
async def api_get_settings():
    return db.get_settings()


@api_router.put("/settings")
async def api_put_settings(payload: dict = Body(...)):
    return db.save_settings(payload)


CSV_COLUMNS = [
    ("Invoice Number", "invoiceNumber"), ("Invoice Date", "invoiceDate"),
    ("Billing Month", "billingMonth"), ("Tenant Name", "tenantName"),
    ("Tenant Email", "tenantEmail"), ("Mobile", "tenantMobile"),
    ("Room", "roomNumber"), ("Bed", "bedNumber"), ("Check-in", "checkIn"),
    ("Check-out", "checkOut"), ("Rent", "rent"), ("Security Deposit", "securityDeposit"),
    ("Electricity", "electricity"), ("Food", "food"), ("Maintenance", "maintenance"),
    ("Other Charges", "otherCharges"), ("Previous Balance", "previousBalance"),
    ("Discount", "discount"), ("Subtotal", "subtotal"), ("Total", "total"),
    ("Amount Paid", "amountPaid"), ("Balance Due", "balanceDue"),
    ("Payment Mode", "paymentMode"), ("Transaction ID", "transactionId"),
    ("Payment Status", "paymentStatus"), ("Created At", "createdAt"),
    ("Updated At", "updatedAt"),
]


def _csv_cell(v) -> str:
    s = "" if v is None else str(v)
    return f'"{s.replace(chr(34), chr(34) * 2)}"' if any(c in s for c in '",\n') else s


def invoices_to_csv(invoices) -> str:
    lines = [",".join(h for h, _ in CSV_COLUMNS)]
    for inv in invoices:
        lines.append(",".join(_csv_cell(inv.get(k)) for _, k in CSV_COLUMNS))
    return "\n".join(lines)


@api_router.get("/backup/export")
async def api_backup_export():
    name = f"ShreeStayHomesPG_Backup_{datetime.now().date().isoformat()}.json"
    return JSONResponse(db.export_data(),
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})


@api_router.get("/backup/export.csv")
async def api_backup_export_csv():
    name = f"ShreeStayHomesPG_Invoices_{datetime.now().date().isoformat()}.csv"
    return Response(content=invoices_to_csv(db.list_invoices()), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@api_router.post("/backup/import")
async def api_backup_import(payload: dict = Body(...), mode: str = "merge"):
    if mode not in ("merge", "overwrite"):
        raise HTTPException(status_code=400, detail="mode must be 'merge' or 'overwrite'")
    try:
        return db.import_data(payload, mode=mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@api_router.post("/migrate")
async def api_migrate(payload: MigratePayload):
    counts = db.import_data(payload.model_dump(), mode="merge")
    return {**counts, **db.counts()}


@api_router.delete("/data")
async def api_delete_all_data():
    return {"cleared": True, **db.clear_all()}


# ---------- Expenses / Food / Billing / Overdue / Reports / Import ----------

class ExpenseIn(BaseModel):
    date: Optional[str] = None
    category: str = "Other"
    description: str = ""
    amount: float = 0
    paymentMethod: str = "Cash"
    reference: str = ""

    @model_validator(mode="after")
    def _amount_ok(self):
        if self.amount < 0:
            raise ValueError("Amount cannot be negative")
        if self.amount == 0:
            raise ValueError("Amount is required")
        return self


class FoodOrderIn(BaseModel):
    tenantId: str = ""
    tenantName: str
    date: Optional[str] = None
    mealType: str = "Lunch"
    quantity: float = 1
    pricePerMeal: float = 0
    status: str = "Ordered"
    note: str = ""

    @model_validator(mode="after")
    def _ok(self):
        if not self.tenantName.strip():
            raise ValueError("Tenant name is required")
        if self.mealType not in ("Breakfast", "Lunch", "Dinner"):
            raise ValueError("Invalid meal type")
        if self.quantity <= 0 or self.pricePerMeal < 0:
            raise ValueError("Invalid quantity or price")
        if self.status not in ("Ordered", "Served", "Cancelled"):
            raise ValueError("Invalid status")
        return self


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    occupation: Optional[str] = None
    emergencyContact: Optional[str] = None
    emergencyContactRelationship: Optional[str] = None
    company: Optional[str] = None
    permanentAddress: Optional[str] = None
    idType: Optional[str] = None
    idNumber: Optional[str] = None
    dateOfBirth: Optional[str] = None
    joiningDate: Optional[str] = None
    roomNumber: Optional[str] = None
    bedNumber: Optional[str] = None
    checkIn: Optional[str] = None
    checkOut: Optional[str] = None
    status: Optional[str] = None
    rent: Optional[float] = None
    deposit: Optional[float] = None


class BillingGenerateIn(BaseModel):
    month: str
    dueDate: str = ""
    rows: list = []


class CsvPreviewIn(BaseModel):
    filename: str = "upload.csv"
    csvText: str


class CsvCommitIn(BaseModel):
    filename: str = "upload.csv"
    csvText: str
    mapping: dict = {}
    decisions: dict = {}


@api_router.get("/expenses")
async def api_list_expenses(month: Optional[str] = None, dateFrom: Optional[str] = None,
                            dateTo: Optional[str] = None):
    return db.list_expenses(month=month, date_from=dateFrom, date_to=dateTo)


@api_router.post("/expenses", status_code=201)
async def api_create_expense(payload: ExpenseIn):
    return db.create_expense(payload.model_dump())


@api_router.delete("/expenses/{eid}")
async def api_delete_expense(eid: str):
    if not db.delete_expense(eid):
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"deleted": True}


@api_router.get("/food-orders")
async def api_list_food(date: Optional[str] = None, month: Optional[str] = None):
    return db.list_food_orders(date=date, month=month)


@api_router.post("/food-orders", status_code=201)
async def api_create_food(payload: FoodOrderIn):
    return db.create_food_order(payload.model_dump())


@api_router.put("/food-orders/{fid}")
async def api_update_food(fid: str, payload: FoodOrderIn):
    rec = db.update_food_order(fid, payload.model_dump())
    if not rec:
        raise HTTPException(status_code=404, detail="Food order not found")
    return rec


@api_router.delete("/food-orders/{fid}")
async def api_delete_food(fid: str):
    if not db.delete_food_order(fid):
        raise HTTPException(status_code=404, detail="Food order not found")
    return {"deleted": True}


@api_router.get("/food-orders/today")
async def api_food_today(date: Optional[str] = None):
    return db.food_today(date or datetime.now().date().isoformat())


@api_router.get("/food-orders/summary")
async def api_food_summary(month: Optional[str] = None):
    return db.food_summary(month or datetime.now().date().isoformat()[:7])


@api_router.put("/tenants/{tid}")
async def api_update_tenant(tid: str, payload: TenantUpdate):
    t = db.update_tenant(tid, payload.model_dump(exclude_none=True))
    if not t:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return t


@api_router.get("/billing/preview")
async def api_billing_preview(month: str):
    if not re.match(r"^\d{4}-\d{2}$", month or ""):
        raise HTTPException(status_code=422, detail="month must be YYYY-MM")
    return db.billing_preview(month)


@api_router.post("/billing/generate")
async def api_billing_generate(payload: BillingGenerateIn):
    if not re.match(r"^\d{4}-\d{2}$", payload.month or ""):
        raise HTTPException(status_code=422, detail="month must be YYYY-MM")
    return db.billing_generate(payload.month, payload.rows, payload.dueDate)


@api_router.get("/reports/monthly")
async def api_report(month: Optional[str] = None, dateFrom: Optional[str] = None,
                     dateTo: Optional[str] = None):
    return db.monthly_report(month=month, date_from=dateFrom, date_to=dateTo)


@api_router.get("/dashboard/stats")
async def api_dashboard_stats():
    return db.dashboard_stats()


@api_router.post("/imports/preview")
async def api_import_preview(payload: CsvPreviewIn):
    if len(payload.csvText) > 5_000_000:
        raise HTTPException(status_code=413, detail="CSV too large")
    try:
        return db.csv_preview(payload.filename, payload.csvText)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@api_router.post("/imports/commit")
async def api_import_commit(payload: CsvCommitIn):
    if len(payload.csvText) > 5_000_000:
        raise HTTPException(status_code=413, detail="CSV too large")
    try:
        return db.csv_commit(payload.filename, payload.csvText, payload.mapping, payload.decisions)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@api_router.get("/imports")
async def api_imports():
    return db.list_imports()


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', 'http://localhost:3000').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
