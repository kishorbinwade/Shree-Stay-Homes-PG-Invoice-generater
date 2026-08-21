import { buildInvoicePDF, pdfToBase64, pdfFilename } from './pdf';

// Backend URL: set REACT_APP_BACKEND_URL in frontend/.env.
// Falls back to http://localhost:8001 for local/offline runs.
const BACKEND = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
const API = `${BACKEND}/api`;

export const DEFAULT_SETTINGS = {
  businessName: 'SHREE STAY HOMES & PG',
  subtitle: 'PG Accommodation & Stay Services',
  address: '',
  mobile: '',
  email: 'shreehomestaypg@gmail.com',
  gstin: '',
  logo: '',
  signature: '',
  ownerEmail: 'shreehomestaypg@gmail.com',
  autoOwnerEmail: true,
  tenantEmailEnabled: true,
  invoicePrefix: 'SHPG',
  startingNumber: 1,
  paymentTerms: 'Payment due within 7 days of invoice date.',
  notes: 'Thank you for staying with Shree Stay Homes & PG.',
  watermarkText: 'SHREE STAY HOMES & PG',
};

async function req(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
  } catch (e) {
    throw new Error('Cannot reach the local backend (http://localhost:8001). Start it with ./scripts/run-local.sh');
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const j = await res.json();
      if (j?.detail) detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
    } catch (e2) { /* keep default */ }
    throw new Error(detail);
  }
  return res.json();
}

// ---------- invoices ----------
export const fetchInvoices = ({ q, month, status, order } = {}) => {
  const p = new URLSearchParams();
  if (q) p.set('q', q);
  if (month) p.set('month', month);
  if (status && status !== 'all') p.set('status', status);
  if (order) p.set('order', order);
  const s = p.toString();
  return req(`/invoices${s ? `?${s}` : ''}`);
};
export const fetchInvoice = (id) => req(`/invoices/${id}`);
export const createInvoice = (data) => req('/invoices', { method: 'POST', body: JSON.stringify(data) });
export const updateInvoice = (id, data) => req(`/invoices/${id}`, { method: 'PUT', body: JSON.stringify(data) });
export const removeInvoice = (id) => req(`/invoices/${id}`, { method: 'DELETE' });
export const peekNextNumber = () => req('/invoices/next-number');

// ---------- tenants ----------
export const fetchTenants = () => req('/tenants');
export const fetchTenant = (id) => req(`/tenants/${encodeURIComponent(id)}`);
export const removeTenant = (id) => req(`/tenants/${encodeURIComponent(id)}`, { method: 'DELETE' });

// ---------- settings ----------
export const fetchSettings = () => req('/settings');
export const saveSettings = (s) => req('/settings', { method: 'PUT', body: JSON.stringify(s) });

// ---------- backup / restore / migration ----------
export const fetchBackupJSON = () => req('/backup/export');
export const importBackup = (payload, mode = 'merge') =>
  req(`/backup/import?mode=${mode}`, { method: 'POST', body: JSON.stringify(payload) });
export const migrateLocalData = (payload) => req('/migrate', { method: 'POST', body: JSON.stringify(payload) });
export const clearAllData = () => req('/data', { method: 'DELETE' });
export const csvDownloadUrl = () => `${API}/backup/export.csv`;

export function downloadViaUrl(url) {
  const a = document.createElement('a');
  a.href = url;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

// ---------- email (Gmail SMTP via backend; PDF attached) ----------
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
  return req('/email/invoice', { method: 'POST', body: JSON.stringify(body) });
}
