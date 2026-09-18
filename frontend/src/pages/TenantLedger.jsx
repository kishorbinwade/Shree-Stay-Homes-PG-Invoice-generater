import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, BookOpen, FilePlus2, Receipt, IndianRupee, Scale, Pencil } from 'lucide-react';
import { fetchTenantLedger } from '../lib/api';
import { inr, fmtDate, monthLabel } from '../lib/format';
import { Button } from '../components/ui/button';

function SummaryCard({ icon: Icon, label, value, tone, testId }) {
  return (
    <div data-testid={testId} className="rounded-xl border border-[#E6E4E0] bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-[0.1em] text-stone-500">{label}</span>
        <Icon className="h-4 w-4 text-terracotta-500" />
      </div>
      <div className={`mt-3 font-heading text-2xl font-extrabold tracking-tight ${tone || 'text-stone-900'}`}>{value}</div>
    </div>
  );
}

const TYPE_STYLE = {
  invoice: 'bg-stone-100 text-stone-700',
  payment: 'bg-green-50 text-green-700',
  opening: 'bg-amber-50 text-amber-700',
};
const TYPE_LABEL = { invoice: 'Invoice', payment: 'Payment', opening: 'Opening' };

function LedgerRow({ row, idx }) {
  const isPay = row.type === 'payment';
  return (
    <tr className="border-b border-stone-100 transition-colors duration-150 hover:bg-stone-50" data-testid={`ledger-row-${idx}`}>
      <td className="px-4 py-3 text-stone-600 whitespace-nowrap">{fmtDate(row.date)}</td>
      <td className="px-4 py-3">
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${TYPE_STYLE[row.type]}`}>{TYPE_LABEL[row.type]}</span>
      </td>
      <td className="px-4 py-3">
        <Link to={`/invoices/${row.invoiceId}/edit`} className="font-semibold text-stone-900 hover:text-terracotta-600" data-testid={`ledger-row-${idx}-invoice-link`}>
          {row.invoiceNumber}
        </Link>
        <div className="text-xs text-stone-500">{monthLabel(row.billingMonth)}</div>
      </td>
      <td className="px-4 py-3 text-stone-600">
        {isPay ? (
          <>
            {row.description}
            {row.transactionId && <div className="text-xs text-stone-400">Txn: {row.transactionId}</div>}
          </>
        ) : row.type === 'invoice' ? (
          <>
            {row.description}
            {row.previousBalance > 0 && (
              <div className="text-xs text-stone-400">Invoice total {inr(row.invoiceTotal)} incl. {inr(row.previousBalance)} carried forward</div>
            )}
          </>
        ) : row.description}
      </td>
      <td className="px-4 py-3 text-right font-medium text-stone-900">{row.debit ? inr(row.debit) : '—'}</td>
      <td className="px-4 py-3 text-right font-medium text-green-700">{row.credit ? inr(row.credit) : '—'}</td>
      <td className={`px-4 py-3 text-right font-semibold ${row.balance > 0 ? 'text-red-600' : row.balance < 0 ? 'text-green-700' : 'text-stone-600'}`}>
        {inr(row.balance)}
      </td>
    </tr>
  );
}

export default function TenantLedger() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchTenantLedger(id)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="py-24 text-center text-sm text-stone-400" data-testid="ledger-loading">Loading ledger…</div>;
  if (error || !data) {
    return (
      <div className="space-y-4" data-testid="ledger-error">
        <Link to="/tenants" className="inline-flex items-center gap-1 text-sm text-stone-600 hover:text-terracotta-600"><ArrowLeft className="h-4 w-4" /> Back to tenants</Link>
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">{error || 'Tenant not found'}</div>
      </div>
    );
  }

  const { tenant, rows, summary } = data;
  const outstandingTone = summary.outstanding > 0 ? 'text-red-600' : summary.outstanding < 0 ? 'text-green-700' : 'text-stone-900';

  return (
    <div data-testid="tenant-ledger-page" className="space-y-6">
      <Link to="/tenants" className="inline-flex items-center gap-1 text-sm text-stone-600 hover:text-terracotta-600" data-testid="ledger-back-link">
        <ArrowLeft className="h-4 w-4" /> Back to tenants
      </Link>

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-extrabold tracking-tight text-stone-900 sm:text-4xl" data-testid="ledger-tenant-name">{tenant.name}</h1>
          <p className="mt-1 text-sm text-stone-600" data-testid="ledger-tenant-meta">
            {tenant.mobile || '—'} · Room {tenant.roomNumber || '-'}/{tenant.bedNumber || '-'}
            {tenant.email ? ` · ${tenant.email}` : ''}
            {tenant.deleted ? ' · profile removed (invoices kept)' : ''}
          </p>
        </div>
        <Button asChild className="bg-terracotta-500 text-white hover:bg-terracotta-600">
          <Link to={`/invoices/new?tenant=${encodeURIComponent(tenant.id)}`} data-testid="ledger-new-invoice-btn"><FilePlus2 className="mr-2 h-4 w-4" /> New Invoice</Link>
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <SummaryCard icon={Receipt} label="Total Billed" value={inr(summary.totalBilled)} testId="ledger-total-billed" />
        <SummaryCard icon={IndianRupee} label="Total Paid" value={inr(summary.totalPaid)} tone="text-green-700" testId="ledger-total-paid" />
        <SummaryCard icon={Scale} label={summary.outstanding < 0 ? 'Advance / Credit' : 'Outstanding'} value={inr(Math.abs(summary.outstanding))} tone={outstandingTone} testId="ledger-outstanding" />
      </div>

      <div className="rounded-xl border border-[#E6E4E0] bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-stone-100 px-5 py-4">
          <div className="flex items-center gap-2 font-heading text-lg font-bold text-stone-900"><BookOpen className="h-4 w-4 text-terracotta-500" /> Running Ledger</div>
          <span className="text-xs text-stone-500" data-testid="ledger-invoice-count">{summary.invoiceCount} invoice{summary.invoiceCount === 1 ? '' : 's'}</span>
        </div>
        {rows.length === 0 ? (
          <div className="flex flex-col items-center py-24 text-center" data-testid="ledger-empty">
            <BookOpen className="h-12 w-12 text-stone-300" />
            <p className="mt-3 text-sm text-stone-500">No invoices yet for this tenant.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="ledger-table">
              <thead>
                <tr className="border-b border-stone-200 text-left text-xs uppercase tracking-wider text-stone-500">
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Invoice</th>
                  <th className="px-4 py-3">Description</th>
                  <th className="px-4 py-3 text-right">Charge</th>
                  <th className="px-4 py-3 text-right">Paid</th>
                  <th className="px-4 py-3 text-right">Balance</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, idx) => <LedgerRow key={`${row.invoiceId}-${row.type}-${idx}`} row={row} idx={idx} />)}
              </tbody>
              <tfoot>
                <tr className="bg-stone-50 text-sm font-semibold" data-testid="ledger-footer">
                  <td className="px-4 py-3" colSpan={4}>Totals</td>
                  <td className="px-4 py-3 text-right text-stone-900">{inr(summary.totalBilled)}</td>
                  <td className="px-4 py-3 text-right text-green-700">{inr(summary.totalPaid)}</td>
                  <td className={`px-4 py-3 text-right ${outstandingTone}`}>{inr(summary.outstanding)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
        <div className="flex items-center gap-1.5 border-t border-stone-100 px-5 py-3 text-xs text-stone-400">
          <Pencil className="h-3 w-3" /> Charges exclude the "Previous Balance" carried into an invoice, so nothing is counted twice. Click an invoice number to edit or record a payment.
        </div>
      </div>
    </div>
  );
}
