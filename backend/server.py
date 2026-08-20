from fastapi import FastAPI, APIRouter, HTTPException
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
from pydantic import BaseModel, EmailStr
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


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', 'http://localhost:3000').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)
