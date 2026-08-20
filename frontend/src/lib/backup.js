import { listInvoices } from './db';

function csvEscape(v) {
  const s = v === null || v === undefined ? '' : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function invoicesToCSV(invoices) {
  const headers = [
    'Invoice Number', 'Invoice Date', 'Billing Month', 'Tenant Name', 'Tenant Email', 'Mobile',
    'Room', 'Bed', 'Check-in', 'Check-out', 'Rent', 'Security Deposit', 'Electricity', 'Food',
    'Maintenance', 'Other Charges', 'Previous Balance', 'Discount', 'Subtotal', 'Total',
    'Amount Paid', 'Balance Due', 'Payment Mode', 'Transaction ID', 'Payment Status',
    'Email Owner', 'Email Tenant', 'Created At', 'Updated At',
  ];
  const lines = [headers.join(',')];
  for (const i of invoices) {
    lines.push([
      i.invoiceNumber, i.invoiceDate, i.billingMonth, i.tenantName, i.tenantEmail, i.tenantMobile,
      i.roomNumber, i.bedNumber, i.checkIn, i.checkOut, i.rent, i.securityDeposit, i.electricity,
      i.food, i.maintenance, i.otherCharges, i.previousBalance, i.discount, i.subtotal, i.total,
      i.amountPaid, i.balanceDue, i.paymentMode, i.transactionId, i.paymentStatus,
      i.emailStatus?.owner || '', i.emailStatus?.tenant || '', i.createdAt, i.updatedAt,
    ].map(csvEscape).join(','));
  }
  return lines.join('\n');
}

export function downloadFile(content, filename, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export async function exportInvoicesCSV() {
  const invoices = await listInvoices();
  downloadFile(invoicesToCSV(invoices), `ShreeStayHomesPG_Invoices_${new Date().toISOString().slice(0, 10)}.csv`, 'text/csv');
  return invoices.length;
}
