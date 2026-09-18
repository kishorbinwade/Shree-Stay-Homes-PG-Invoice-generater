import { Download, Pencil, Trash2 } from 'lucide-react';
import { Button } from './ui/button';
import { fmtDate, inr } from '../lib/format';

export function PaymentHistory({ payments, onEdit, onDelete, onReceipt }) {
  return (
    <section data-testid="payment-history" className="min-w-0">
      <h2 className="font-heading text-lg font-bold">Payment History</h2>
      {!payments.length ? <p className="py-8 text-sm text-stone-500" data-testid="payment-history-empty">No payments recorded.</p> : (
        <div className="mt-4 divide-y divide-stone-200 border-y border-stone-200" role="table" aria-label="Payment history">
          <div role="row" className="hidden gap-3 py-3 text-xs font-semibold uppercase text-stone-500 md:grid md:grid-cols-[1fr_1fr_1fr_2fr_120px]">
            {['Date', 'Amount', 'Method', 'Reference / Notes', 'Actions'].map((label) => <span role="columnheader" key={label}>{label}</span>)}
          </div>
          {payments.map((p) => (
            <div key={p.id} role="row" data-testid={`payment-row-${p.id}`} className="grid min-w-0 grid-cols-2 items-start gap-3 py-4 text-sm md:grid-cols-[1fr_1fr_1fr_2fr_120px]">
              <div role="cell" data-testid={`payment-date-${p.id}`}>{fmtDate(p.paymentDate)}{p.dateInferred && <div className="mt-1 text-xs text-amber-700">Date inferred</div>}</div>
              <div role="cell" className="font-bold text-green-700" data-testid={`payment-amount-${p.id}`}>{inr(p.amount)}</div>
              <div role="cell" data-testid={`payment-method-${p.id}`}>{p.paymentMethod}</div>
              <div role="cell" className="min-w-0 break-words" data-testid={`payment-reference-${p.id}`}><div>{p.reference || '—'}</div><p className="mt-1 whitespace-pre-wrap text-xs text-stone-500">{p.notes}</p></div>
              <div role="cell" className="col-span-2 flex gap-1 md:col-span-1">
                <Button variant="ghost" size="icon" title="Download payment receipt" aria-label="Download payment receipt" onClick={() => onReceipt(p)} data-testid={`payment-receipt-${p.id}`}><Download className="h-4 w-4" /></Button>
                <Button variant="ghost" size="icon" title="Edit payment" aria-label="Edit payment" onClick={() => onEdit(p)} data-testid={`payment-edit-${p.id}`}><Pencil className="h-4 w-4" /></Button>
                <Button variant="ghost" size="icon" title="Delete payment" aria-label="Delete payment" onClick={() => onDelete(p)} data-testid={`payment-delete-${p.id}`}><Trash2 className="h-4 w-4 text-red-600" /></Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}