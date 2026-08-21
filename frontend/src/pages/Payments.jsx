import { useEffect, useMemo, useState } from 'react';
import { IndianRupee } from 'lucide-react';
import { fetchInvoices } from '../lib/api';
import { inr, fmtDate, monthLabel } from '../lib/format';

export default function Payments() {
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchInvoices().then(setInvoices).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const payments = useMemo(
    () => invoices.filter((i) => Number(i.amountPaid) > 0),
    [invoices],
  );
  const collected = payments.reduce((a, i) => a + Math.min(Number(i.amountPaid) || 0, Number(i.total) || 0), 0);

  return (
    <div data-testid="payments-page" className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-extrabold tracking-tight text-stone-900 sm:text-4xl">Payments</h1>
          <p className="mt-1 text-sm text-stone-600">All payments recorded against invoices.</p>
        </div>
        <div className="rounded-xl border border-[#E6E4E0] bg-white px-5 py-3 shadow-sm" data-testid="payments-total">
          <span className="text-xs uppercase tracking-wider text-stone-500">Total Collected</span>
          <div className="font-heading text-xl font-extrabold text-green-700">{inr(collected)}</div>
        </div>
      </div>

      <div className="rounded-xl border border-[#E6E4E0] bg-white shadow-sm">
        {loading ? (
          <div className="py-24 text-center text-sm text-stone-400">Loading…</div>
        ) : payments.length === 0 ? (
          <div className="flex flex-col items-center py-24 text-center" data-testid="payments-empty">
            <IndianRupee className="h-12 w-12 text-stone-300" />
            <p className="mt-3 text-sm text-stone-500">No payments recorded yet.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="payments-table">
              <thead>
                <tr className="border-b border-stone-200 text-left text-xs uppercase tracking-wider text-stone-500">
                  <th className="px-4 py-3">Invoice</th><th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Tenant</th><th className="px-4 py-3">Month</th>
                  <th className="px-4 py-3">Mode</th><th className="px-4 py-3">Txn ID / UTR</th>
                  <th className="px-4 py-3 text-right">Paid</th><th className="px-4 py-3 text-right">Balance</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((i) => (
                  <tr key={i.id} className="border-b border-stone-100" data-testid={`payment-row-${i.invoiceNumber}`}>
                    <td className="px-4 py-3 font-semibold text-stone-900">{i.invoiceNumber}</td>
                    <td className="px-4 py-3 text-stone-600">{fmtDate(i.invoiceDate)}</td>
                    <td className="px-4 py-3 text-stone-900">{i.tenantName}</td>
                    <td className="px-4 py-3 text-stone-600">{monthLabel(i.billingMonth)}</td>
                    <td className="px-4 py-3 text-stone-600">{i.paymentMode || '—'}</td>
                    <td className="px-4 py-3 text-xs text-stone-500">{i.transactionId || '—'}</td>
                    <td className="px-4 py-3 text-right font-semibold text-green-700">{inr(i.amountPaid)}</td>
                    <td className={`px-4 py-3 text-right font-medium ${Number(i.balanceDue) > 0 ? 'text-red-600' : 'text-stone-500'}`}>{inr(Math.max(Number(i.balanceDue) || 0, 0))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
