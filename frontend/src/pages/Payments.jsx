import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Download, IndianRupee } from 'lucide-react';
import { fetchPayments, fetchPaymentReceipt } from '../lib/api';
import { downloadPaymentReceipt } from '../lib/receipt';
import { useSettings } from '../context/SettingsContext';
import { inr, fmtDate } from '../lib/format';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';

export default function Payments() {
  const { settings } = useSettings();
  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => { fetchPayments().then(setPayments).catch((e) => setError(e.message)).finally(() => setLoading(false)); }, []);
  const receipt = async (p) => {
    try { downloadPaymentReceipt(await fetchPaymentReceipt(p.id), settings); }
    catch (e) { toast.error(e.message); }
  };
  return (
    <div data-testid="payments-page" className="min-w-0 space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="font-heading text-3xl font-extrabold sm:text-4xl">Payments</h1>
        <div className="rounded-lg border border-stone-200 bg-white px-5 py-3" data-testid="payments-total"><span className="text-xs uppercase text-stone-500">Total Received</span><div className="font-heading text-xl font-bold text-green-700">{inr(payments.reduce((sum, p) => sum + p.amount, 0))}</div></div>
      </div>
      {error && <p role="alert" data-testid="payments-error" className="text-red-700">{error}</p>}
      {loading ? <p data-testid="payments-loading">Loading payments…</p> : !payments.length ? <div className="py-16 text-center text-stone-500" data-testid="payments-empty"><IndianRupee className="mx-auto mb-3 h-8 w-8" />No payments recorded yet.</div> : (
        <div className="divide-y divide-stone-200 border-y border-stone-200" data-testid="payments-table">
          {payments.map((p) => <div key={p.id} className="grid min-w-0 grid-cols-2 items-center gap-3 py-4 text-sm md:grid-cols-[1fr_2fr_1fr_1fr_1fr_44px]" data-testid={`payment-record-${p.id}`}>
            <div data-testid={`payments-date-${p.id}`}>{fmtDate(p.paymentDate)}{p.dateInferred && <p className="text-xs text-amber-700">Date inferred</p>}</div>
            <div className="min-w-0 break-words"><Link to={`/invoices/${p.invoiceId}`} className="font-semibold text-terracotta-600" data-testid={`payments-invoice-${p.id}`}>{p.invoiceNumber}</Link><p>{p.tenantName}</p></div>
            <div data-testid={`payments-method-${p.id}`}>{p.paymentMethod}</div><div className="min-w-0 break-words" data-testid={`payments-reference-${p.id}`}>{p.reference || '—'}</div>
            <div className="font-bold text-green-700" data-testid={`payments-amount-${p.id}`}>{inr(p.amount)}</div>
            <Button variant="ghost" size="icon" title="Download payment receipt" aria-label="Download payment receipt" data-testid={`payments-receipt-${p.id}`} onClick={() => receipt(p)}><Download className="h-4 w-4" /></Button>
          </div>)}
        </div>
      )}
    </div>
  );
}