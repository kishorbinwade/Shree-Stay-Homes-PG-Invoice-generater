import { buildInvoicePDF, pdfToBase64, pdfFilename } from './pdf';

// Backend URL: set REACT_APP_BACKEND_URL in frontend/.env.
// Falls back to http://localhost:8001 for local/offline runs.
const BACKEND = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
const API = `${BACKEND}/api`;

export async function deliverInvoiceEmail(invoice, settings) {
  const doc = buildInvoicePDF(invoice, settings);
  const body = {
    invoiceNumber: invoice.invoiceNumber,
    tenantName: invoice.tenantName,
    billingMonth: String(invoice.billingMonth || ''),
    total: Number(invoice.total) || 0,
    amountPaid: Number(invoice.amountPaid) || 0,
    balanceDue: Number(invoice.balanceDue) || 0,
    paymentStatus: invoice.paymentStatus,
    ownerEmail: settings.ownerEmail,
    tenantEmail: invoice.tenantEmail || null,
    sendToTenant: !!invoice.sendToTenant,
    pdfBase64: pdfToBase64(doc),
    pdfFilename: pdfFilename(invoice),
  };
  let res;
  try {
    res = await fetch(`${API}/email/invoice`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch (e) {
    throw new Error('No internet connection — email could not be sent.');
  }
  if (!res.ok) {
    let detail = `Email failed (${res.status})`;
    try {
      const j = await res.json();
      if (j?.detail) detail = j.detail;
    } catch (e) { /* ignore */ }
    throw new Error(detail);
  }
  return res.json();
}
