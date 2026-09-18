import { Checkbox } from './ui/checkbox';
import { Input } from './ui/input';
import { Label } from './ui/label';

export function InvoiceEmailRecipients({ enabled, onEnabledChange, ownerEmail, tenantEmail }) {
  return (
    <section className="rounded-xl border border-[#E6E4E0] bg-white p-6 shadow-sm" data-testid="invoice-email-recipients">
      <h2 className="font-heading text-lg font-bold text-stone-900">Email recipients</h2>
      <label className="mt-4 flex items-center gap-2 text-sm text-stone-700" data-testid="send-invoice-email-label">
        <Checkbox checked={enabled} onCheckedChange={(v) => onEnabledChange(!!v)} data-testid="send-invoice-email" />
        Send invoice by email
      </label>
      <div className="mt-4 grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="min-w-0">
          <Label htmlFor="invoice-email-owner" className="text-xs text-stone-500">To · Owner</Label>
          <Input id="invoice-email-owner" readOnly value={ownerEmail} data-testid="invoice-email-owner" className="mt-1.5 min-w-0 border-stone-200 bg-stone-50 text-sm" />
        </div>
        <div className="min-w-0">
          <Label htmlFor="invoice-email-cc" className="text-xs text-stone-500">CC · Tenant</Label>
          <Input id="invoice-email-cc" readOnly value={tenantEmail || ''} placeholder="No email provided" data-testid="invoice-email-cc" className="mt-1.5 min-w-0 border-stone-200 bg-stone-50 text-sm" />
        </div>
      </div>
    </section>
  );
}