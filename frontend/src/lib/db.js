import { openDB } from 'idb';

const DB_NAME = 'shree-stay-pg-db';

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

let dbPromise = null;
export function getDB() {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, 1, {
      upgrade(db) {
        const inv = db.createObjectStore('invoices', { keyPath: 'id' });
        inv.createIndex('invoiceNumber', 'invoiceNumber', { unique: true });
        inv.createIndex('billingMonth', 'billingMonth');
        inv.createIndex('paymentStatus', 'paymentStatus');
        db.createObjectStore('tenants', { keyPath: 'id' });
        db.createObjectStore('kv', { keyPath: 'key' });
      },
    });
  }
  return dbPromise;
}

export async function getSettings() {
  const db = await getDB();
  const rec = await db.get('kv', 'settings');
  return { ...DEFAULT_SETTINGS, ...(rec?.value || {}) };
}

export async function saveSettings(settings) {
  const db = await getDB();
  await db.put('kv', { key: 'settings', value: settings });
}

function yearOf(dateStr) {
  const d = dateStr ? new Date(dateStr) : new Date();
  return d.getFullYear();
}

export function formatInvoiceNumber(prefix, year, seq) {
  return `${prefix}-${year}-${String(seq).padStart(4, '0')}`;
}

async function getSeq(db, year) {
  const rec = await db.get('kv', `seq-${year}`);
  return rec?.value || 0;
}

export async function peekInvoiceNumber(settings) {
  const db = await getDB();
  const year = new Date().getFullYear();
  const seq = await getSeq(db, year);
  const next = Math.max(seq + 1, Number(settings.startingNumber) || 1);
  return formatInvoiceNumber(settings.invoicePrefix || 'SHPG', year, next);
}

export async function allocateInvoiceNumber(settings) {
  const db = await getDB();
  const year = new Date().getFullYear();
  const tx = db.transaction('kv', 'readwrite');
  const rec = await tx.store.get(`seq-${year}`);
  const seq = rec?.value || 0;
  const next = Math.max(seq + 1, Number(settings.startingNumber) || 1);
  await tx.store.put({ key: `seq-${year}`, value: next });
  await tx.done;
  return formatInvoiceNumber(settings.invoicePrefix || 'SHPG', year, next);
}

export async function listInvoices() {
  const db = await getDB();
  const all = await db.getAll('invoices');
  return all.sort((a, b) => (b.createdAt || '').localeCompare(a.createdAt || ''));
}

export async function getInvoice(id) {
  const db = await getDB();
  return db.get('invoices', id);
}

export async function putInvoice(invoice) {
  const db = await getDB();
  await db.put('invoices', invoice);
  return invoice;
}

export async function deleteInvoice(id) {
  const db = await getDB();
  await db.delete('invoices', id);
}

export async function upsertTenantFromInvoice(inv) {
  const key = (inv.tenantMobile || inv.tenantName || '').toLowerCase().trim();
  if (!key) return;
  const db = await getDB();
  const existing = await db.get('tenants', key);
  const now = new Date().toISOString();
  await db.put('tenants', {
    id: key,
    name: inv.tenantName,
    mobile: inv.tenantMobile || '',
    email: inv.tenantEmail || '',
    occupation: inv.occupation || '',
    emergencyContact: inv.emergencyContact || '',
    roomNumber: inv.roomNumber || '',
    bedNumber: inv.bedNumber || '',
    checkIn: inv.checkIn || '',
    checkOut: inv.checkOut || '',
    createdAt: existing?.createdAt || now,
    updatedAt: now,
  });
}

export async function listTenants() {
  const db = await getDB();
  const all = await db.getAll('tenants');
  return all.sort((a, b) => (b.updatedAt || '').localeCompare(a.updatedAt || ''));
}

export async function getTenant(id) {
  const db = await getDB();
  return db.get('tenants', id);
}

export async function deleteTenant(id) {
  const db = await getDB();
  await db.delete('tenants', id);
}

export async function exportAllData() {
  const db = await getDB();
  return {
    app: 'Shree Stay Homes & PG Billing',
    version: 1,
    exportedAt: new Date().toISOString(),
    invoices: await db.getAll('invoices'),
    tenants: await db.getAll('tenants'),
    settings: (await db.get('kv', 'settings'))?.value || null,
  };
}

export async function importAllData(data) {
  const db = await getDB();
  const invoices = Array.isArray(data) ? data : data.invoices || [];
  const tenants = Array.isArray(data) ? [] : data.tenants || [];
  let invCount = 0;
  let tenantCount = 0;
  for (const inv of invoices) {
    if (inv && inv.id && inv.invoiceNumber) {
      await db.put('invoices', inv);
      invCount++;
    }
  }
  for (const t of tenants) {
    if (t && t.id) {
      await db.put('tenants', t);
      tenantCount++;
    }
  }
  await recomputeSequences();
  return { invoices: invCount, tenants: tenantCount };
}

async function recomputeSequences() {
  const db = await getDB();
  const all = await db.getAll('invoices');
  const maxByYear = {};
  for (const inv of all) {
    const m = /-(\d{4})-(\d+)$/.exec(inv.invoiceNumber || '');
    if (m) {
      const yr = m[1];
      const num = parseInt(m[2], 10);
      if (!maxByYear[yr] || num > maxByYear[yr]) maxByYear[yr] = num;
    }
  }
  for (const [yr, num] of Object.entries(maxByYear)) {
    const existing = await getSeq(db, Number(yr));
    if (num > existing) await db.put('kv', { key: `seq-${yr}`, value: num });
  }
}

export async function clearAllData() {
  const db = await getDB();
  await db.clear('invoices');
  await db.clear('tenants');
  await db.clear('kv');
}
