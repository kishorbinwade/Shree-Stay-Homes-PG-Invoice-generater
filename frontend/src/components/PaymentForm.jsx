import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { createPayment, updatePayment, fetchPaymentReceipt } from '../lib/api';
import { downloadPaymentReceipt } from '../lib/receipt';
import { inr, todayISO, PAYMENT_MODES } from '../lib/format';
import { useSettings } from '../context/SettingsContext';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Checkbox } from './ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from './ui/dialog';
import { toast } from 'sonner';

export function PaymentForm({ invoice, payment, onClose, onSaved }) {
  const { settings } = useSettings();
  const [form, setForm] = useState(payment || { paymentDate: todayISO(), amount: '', paymentMethod: 'Cash', reference: '', notes: '' });
  const [receipt, setReceipt] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const remaining = Math.max(0, Number(invoice.total) - Number(invoice.amountPaid) + Number(payment?.amount || 0));
  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));
  const save = async (event) => {
    event.preventDefault();
    setError('');
    if (!Number.isFinite(Number(form.amount)) || Number(form.amount) <= 0) return setError('Payment amount must be greater than zero.');
    if (Math.round(Number(form.amount) * 100) > Math.round(remaining * 100)) return setError(`Payment cannot exceed the remaining balance of ${inr(remaining)}.`);
    setBusy(true);
    try {
      const body = { ...form, invoiceId: invoice.id, amount: Number(form.amount) };
      const saved = payment ? await updatePayment(payment.id, body) : await createPayment(body);
      toast.success(payment ? 'Payment updated' : 'Payment recorded');
      if (receipt) {
        try { downloadPaymentReceipt(await fetchPaymentReceipt(saved.id), settings); }
        catch (e) { toast.warning('Payment saved. Download the receipt from payment history.'); }
      }
      onSaved();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };
  return (
    <Dialog open onOpenChange={(open) => { if (!open && !busy) onClose(); }}>
      <DialogContent data-testid="payment-form-dialog" className="max-h-[90vh] overflow-y-auto bg-white sm:max-w-lg">
        <DialogHeader><DialogTitle>{payment ? 'Edit Payment' : 'Record Payment'}</DialogTitle>
          <DialogDescription data-testid="payment-form-invoice">{invoice.invoiceNumber} · {invoice.tenantName}</DialogDescription></DialogHeader>
        <form onSubmit={save} className="space-y-4" data-testid="payment-form">
          <p className="text-sm text-stone-600" data-testid="payment-remaining-balance">Remaining balance: <strong>{inr(remaining)}</strong></p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div><Label htmlFor="payment-date">Payment Date</Label><Input id="payment-date" data-testid="payment-date" type="date" required value={form.paymentDate} onChange={(e) => set('paymentDate', e.target.value)} /></div>
            <div><Label htmlFor="payment-amount">Amount (₹)</Label><Input id="payment-amount" data-testid="payment-amount" type="number" required min="0.01" step="0.01" value={form.amount} onChange={(e) => set('amount', e.target.value)} /></div>
          </div>
          <div><Label htmlFor="payment-method">Payment Method</Label>
            <Select value={form.paymentMethod} onValueChange={(v) => set('paymentMethod', v)}><SelectTrigger id="payment-method" data-testid="payment-method"><SelectValue /></SelectTrigger>
              <SelectContent>{PAYMENT_MODES.map((m) => <SelectItem value={m} key={m} data-testid={`record-method-${m.toLowerCase().replaceAll(' ', '-')}`}>{m}</SelectItem>)}</SelectContent></Select></div>
          <div><Label htmlFor="payment-reference">Reference / Transaction ID</Label><Input id="payment-reference" data-testid="payment-reference" maxLength={200} value={form.reference} onChange={(e) => set('reference', e.target.value)} /></div>
          <div><Label htmlFor="payment-notes">Notes</Label><Textarea id="payment-notes" data-testid="payment-notes" maxLength={2000} value={form.notes} onChange={(e) => set('notes', e.target.value)} /></div>
          <label className="flex items-center gap-2 text-sm"><Checkbox checked={receipt} onCheckedChange={(v) => setReceipt(!!v)} data-testid="payment-download-receipt-option" />Download payment receipt</label>
          {error && <p role="alert" className="break-words text-sm text-red-700" data-testid="payment-form-error">{error}</p>}
          <div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={onClose} disabled={busy} data-testid="payment-cancel-button">Cancel</Button>
            <Button type="submit" disabled={busy} data-testid="payment-save-button" className="bg-terracotta-500 text-white hover:bg-terracotta-600">{busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Save Payment</Button></div>
        </form>
      </DialogContent>
    </Dialog>
  );
}