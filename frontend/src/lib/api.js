import { buildInvoicePDF, pdfToBase64, pdfFilename } from './pdf';

// Backend URL resolution — works in BOTH the hosted preview and on a local PC
// with the same code, so pushing/pulling never needs a config change:
//  • Running on localhost (your computer)  -> always http://localhost:8001
//  • Running anywhere else (preview/hosted) -> REACT_APP_BACKEND_URL
function resolveBackend() {
  if (typeof window !== 'undefined') {
    const host = window.location.hostname;
    if (host === 'localhost' || host === '127.0.0.1') {
      return 'http://localhost:8001';
    }
  }
  return process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';
}
const BACKEND = resolveBackend();
const API = `${BACKEND}/api`;
export const IS_LOCAL = BACKEND === 'http://localhost:8001';
export const BACKEND_CONNECTION_ERROR = IS_LOCAL
  ? `Cannot reach the backend at ${BACKEND}. Start it with ./scripts/run-local.sh — invoices, history and settings need it running.`
  : 'Cannot reach the backend right now. Retrying automatically…';

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
  const isRead = !options.method || options.method.toUpperCase() === 'GET';
  const controller = new AbortController();
  // Bound reads so a stalled connection cannot leave the preview loading forever.
  // Never automatically retry writes: an interrupted save may have already committed.
  const timeout = isRead ? setTimeout(() => controller.abort(), 10000) : null;
  try {
    res = await fetch(`${API}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
      ...(isRead ? { cache: 'no-store', signal: controller.signal } : {}),
    });
  } catch (e) {
    throw new Error(IS_LOCAL ? BACKEND_CONNECTION_ERROR : `Cannot reach the backend at ${BACKEND}. Please retry in a moment.`);
  } finally {
    if (timeout) clearTimeout(timeout);
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
export const fetchTenantLedger = (id) => req(`/tenants/${encodeURIComponent(id)}/ledger`);
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

// ---------- tenants (extended) ----------
export const updateTenant = (id, data) =>
  req(`/tenants/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(data) });

// ---------- expenses ----------
export const fetchExpenses = ({ month, dateFrom, dateTo } = {}) => {
  const p = new URLSearchParams();
  if (month) p.set('month', month);
  if (dateFrom) p.set('dateFrom', dateFrom);
  if (dateTo) p.set('dateTo', dateTo);
  const s = p.toString();
  return req(`/expenses${s ? `?${s}` : ''}`);
};
export const createExpense = (d) => req('/expenses', { method: 'POST', body: JSON.stringify(d) });
export const removeExpense = (id) => req(`/expenses/${id}`, { method: 'DELETE' });

// ---------- food orders ----------
export const fetchFoodOrders = ({ date, month } = {}) => {
  const p = new URLSearchParams();
  if (date) p.set('date', date);
  if (month) p.set('month', month);
  const s = p.toString();
  return req(`/food-orders${s ? `?${s}` : ''}`);
};
export const createFoodOrder = (d) => req('/food-orders', { method: 'POST', body: JSON.stringify(d) });
export const updateFoodOrder = (id, d) => req(`/food-orders/${id}`, { method: 'PUT', body: JSON.stringify(d) });
export const removeFoodOrder = (id) => req(`/food-orders/${id}`, { method: 'DELETE' });
export const fetchFoodToday = (date) => req(`/food-orders/today?date=${date}`);
export const fetchFoodSummary = (month) => req(`/food-orders/summary?month=${month}`);

// ---------- monthly billing / overdue / reports / dashboard ----------
export const fetchBillingPreview = (month) => req(`/billing/preview?month=${month}`);
export const generateMonthlyBilling = (payload) =>
  req('/billing/generate', { method: 'POST', body: JSON.stringify(payload) });
export const fetchOverdue = () => req('/invoices/overdue');
export const fetchMonthlyReport = ({ month, dateFrom, dateTo } = {}) => {
  const p = new URLSearchParams();
  if (month) p.set('month', month);
  if (dateFrom) p.set('dateFrom', dateFrom);
  if (dateTo) p.set('dateTo', dateTo);
  const s = p.toString();
  return req(`/reports/monthly${s ? `?${s}` : ''}`);
};
export const fetchDashboardStats = () => req('/dashboard/stats');

// ---------- Google Forms CSV import ----------
export const previewImport = (filename, csvText) =>
  req('/imports/preview', { method: 'POST', body: JSON.stringify({ filename, csvText }) });
export const commitImport = (payload) =>
  req('/imports/commit', { method: 'POST', body: JSON.stringify(payload) });
export const fetchImports = () => req('/imports');

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
