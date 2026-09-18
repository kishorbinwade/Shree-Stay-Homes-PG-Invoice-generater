export const inr = (n) =>
  new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 }).format(Number(n) || 0);

export const inrPlain = (n) =>
  '₹' + new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(n) || 0);

export const num = (v) => {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : 0;
};

export function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

export function currentMonth() {
  return todayISO().slice(0, 7);
}

export function fmtDate(d) {
  if (!d) return '—';
  const dt = new Date(`${d}T00:00:00`);
  if (Number.isNaN(dt.getTime())) return '—';
  return dt.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

export function monthLabel(m) {
  if (!m) return '—';
  const s = String(m);
  const [y, mo] = s.split('-').map(Number);
  if (!y || !mo) return s;
  return new Date(y, mo - 1, 1).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
}

export function computeTotals(f) {
  const subtotal =
    num(f.rent) + num(f.securityDeposit) + num(f.electricity) + num(f.food) +
    num(f.maintenance) + num(f.otherCharges) + num(f.previousBalance);
  const total = Math.max(0, subtotal - num(f.discount));
  const balanceDue = total - num(f.amountPaid);
  return { subtotal, total, balanceDue };
}

export function paymentStatusOf(total, amountPaid) {
  if (num(amountPaid) <= 0) return 'Pending';
  if (num(amountPaid) >= num(total) && num(total) > 0) return 'Paid';
  return 'Partially Paid';
}

export const PAYMENT_MODES = ['Cash', 'UPI', 'Bank Transfer', 'Card', 'Other'];

export function waReminderLink(inv, businessName) {
  let digits = String(inv.tenantMobile || '').replace(/\D/g, '');
  if (digits.length === 10) digits = `91${digits}`;
  const lines = [
    `Hello ${inv.tenantName},`,
    '',
    `Your PG payment for ${monthLabel(inv.billingMonth)} is pending.`,
    `Invoice: ${inv.invoiceNumber}`,
    `Total: ${inrPlain(inv.total)}`,
    `Paid: ${inrPlain(inv.amountPaid)}`,
    `Pending: ${inrPlain(Math.max(Number(inv.balanceDue) || 0, 0))}`,
  ];
  if (inv.dueDate) lines.push(`Due date: ${fmtDate(inv.dueDate)}`);
  lines.push('', 'Please make the pending payment at your earliest convenience.', 'Thank you,',
    (businessName || 'SHREE STAY HOMES & PG').split(' ').map((w) => w.charAt(0) + w.slice(1).toLowerCase()).join(' '));
  return `https://wa.me/${digits}?text=${encodeURIComponent(lines.join('\n'))}`;
}
