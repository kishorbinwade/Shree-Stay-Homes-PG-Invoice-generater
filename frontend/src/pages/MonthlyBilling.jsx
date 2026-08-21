import { useState } from 'react';
import { toast } from 'sonner';
import { CalendarPlus, Loader2, CheckCircle2 } from 'lucide-react';
import { fetchBillingPreview, generateMonthlyBilling } from '../lib/api';
import { inr, num, currentMonth, monthLabel } from '../lib/format';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Checkbox } from '../components/ui/checkbox';

const EDITABLE = [
  ['rent', 'Rent'], ['food', 'Food'], ['electricity', 'Electricity'],
  ['maintenance', 'Maintenance'], ['otherCharges', 'Other'], ['discount', 'Discount'],
];

export default function MonthlyBilling() {
  const [month, setMonth] = useState(currentMonth());
  const [dueDate, setDueDate] = useState('');
  const [rows, setRows] = useState(null);
  const [selected, setSelected] = useState({});
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);

  const loadPreview = async () => {
    setLoading(true);
    setResult(null);
    try {
      const data = await fetchBillingPreview(month);
      setRows(data.rows);
      const sel = {};
      data.rows.forEach((r) => { if (!r.alreadyBilled) sel[r.tenantId] = true; });
      setSelected(sel);
      if (data.rows.length === 0) toast.info('No active tenants found. Assign rooms/rent in Rooms & Beds first.');
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  };

  const setCell = (tenantId, key, value) =>
    setRows((rs) => rs.map((r) => (r.tenantId === tenantId ? { ...r, [key]: value } : r)));

  const rowTotal = (r) =>
    Math.max(0, num(r.rent) + num(r.food) + num(r.electricity) + num(r.maintenance) +
      num(r.otherCharges) + num(r.previousBalance) - num(r.discount));

  const handleGenerate = async () => {
    const chosen = rows.filter((r) => selected[r.tenantId] && !r.alreadyBilled);
    if (chosen.length === 0) {
      toast.error('No new invoices selected');
      return;
    }
    setGenerating(true);
    try {
      const res = await generateMonthlyBilling({ month, dueDate, rows: chosen.map((r) => ({ ...r, dueDate })) });
      setResult(res);
      toast.success(`Generated ${res.created.length} invoice(s)${res.skipped.length ? `, skipped ${res.skipped.length} duplicate(s)` : ''}`);
      loadPreview();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div data-testid="billing-page" className="space-y-6">
      <div>
        <h1 className="font-heading text-3xl font-extrabold tracking-tight text-stone-900 sm:text-4xl">Monthly Billing</h1>
        <p className="mt-1 text-sm text-stone-600">Generate invoices for all active tenants in one go. Food charges are computed from actual food orders.</p>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-[#E6E4E0] bg-white p-4 shadow-sm">
        <div>
          <label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Billing Month</label>
          <Input type="month" value={month} onChange={(e) => setMonth(e.target.value)} data-testid="billing-month" className="mt-1.5 w-44 border-[#E6E4E0] bg-[#FDFCFB]" />
        </div>
        <div>
          <label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Due Date</label>
          <Input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} data-testid="billing-due-date" className="mt-1.5 w-44 border-[#E6E4E0] bg-[#FDFCFB]" />
        </div>
        <Button onClick={loadPreview} disabled={loading} data-testid="billing-load-btn" className="bg-terracotta-500 text-white hover:bg-terracotta-600">
          {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CalendarPlus className="mr-2 h-4 w-4" />}
          Preview Invoices
        </Button>
      </div>

      {rows && (
        <div className="rounded-xl border border-[#E6E4E0] bg-white shadow-sm">
          <div className="border-b border-stone-200 px-5 py-3 text-sm font-semibold text-stone-800">
            Preview — {monthLabel(month)} · {rows.filter((r) => !r.alreadyBilled).length} to generate · {rows.filter((r) => r.alreadyBilled).length} already billed
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="billing-table">
              <thead>
                <tr className="border-b border-stone-200 text-left text-xs uppercase tracking-wider text-stone-500">
                  <th className="px-3 py-3"></th>
                  <th className="px-3 py-3">Tenant</th>
                  {EDITABLE.map(([, l]) => <th key={l} className="px-3 py-3 text-right">{l}</th>)}
                  <th className="px-3 py-3 text-right">Prev. Balance</th>
                  <th className="px-3 py-3 text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && (
                  <tr><td colSpan={10} className="px-4 py-12 text-center text-sm text-stone-400" data-testid="billing-empty">No active tenants to bill.</td></tr>
                )}
                {rows.map((r) => (
                  <tr key={r.tenantId} className={`border-b border-stone-100 ${r.alreadyBilled ? 'opacity-60' : ''}`} data-testid={`billing-row-${r.tenantId}`}>
                    <td className="px-3 py-2">
                      {r.alreadyBilled ? (
                        <span className="flex items-center gap-1 whitespace-nowrap text-xs text-green-700" data-testid={`billing-billed-${r.tenantId}`}>
                          <CheckCircle2 className="h-3.5 w-3.5" /> {r.existingInvoiceNumber}
                        </span>
                      ) : (
                        <Checkbox checked={!!selected[r.tenantId]} onCheckedChange={(v) => setSelected((s) => ({ ...s, [r.tenantId]: !!v }))} data-testid={`billing-include-${r.tenantId}`} />
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <div className="font-semibold text-stone-900">{r.tenantName}</div>
                      <div className="text-xs text-stone-500">Room {r.roomNumber || '-'}/{r.bedNumber || '-'}</div>
                    </td>
                    {EDITABLE.map(([key]) => (
                      <td key={key} className="px-2 py-2">
                        <Input type="number" min="0" step="0.01" value={r[key]} disabled={r.alreadyBilled}
                          onChange={(e) => setCell(r.tenantId, key, e.target.value)}
                          data-testid={`billing-${key}-${r.tenantId}`}
                          className="h-8 w-24 border-[#E6E4E0] bg-[#FDFCFB] text-right text-xs" />
                      </td>
                    ))}
                    <td className="px-3 py-2 text-right text-xs font-medium text-stone-700">{inr(num(r.previousBalance))}</td>
                    <td className="px-3 py-2 text-right font-bold text-terracotta-600" data-testid={`billing-total-${r.tenantId}`}>{inr(rowTotal(r))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex justify-end border-t border-stone-200 p-4">
            <Button onClick={handleGenerate} disabled={generating} data-testid="billing-generate-btn" className="bg-terracotta-500 text-white hover:bg-terracotta-600">
              {generating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <CalendarPlus className="mr-2 h-4 w-4" />}
              Generate Selected Invoices
            </Button>
          </div>
        </div>
      )}

      {result && (
        <div className="rounded-xl border border-green-200 bg-green-50 p-5" data-testid="billing-result">
          <div className="flex items-center gap-2 font-semibold text-green-800">
            <CheckCircle2 className="h-5 w-5" /> Generated {result.created.length} invoice(s) for {monthLabel(month)}
          </div>
          <div className="mt-2 space-y-1 text-sm text-green-800">
            {result.created.map((i) => (
              <div key={i.id} data-testid={`billing-created-${i.invoiceNumber}`}>{i.invoiceNumber} — {i.tenantName} — {inr(i.total)}</div>
            ))}
            {result.skipped.length > 0 && <div className="text-amber-700">Skipped duplicates: {result.skipped.join(', ')}</div>}
          </div>
        </div>
      )}
    </div>
  );
}
