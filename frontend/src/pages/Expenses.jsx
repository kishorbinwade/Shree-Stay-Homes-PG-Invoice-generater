import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Wallet, Plus, Trash2, Loader2, Download } from 'lucide-react';
import { fetchExpenses, createExpense, removeExpense } from '../lib/api';
import { inr, num, todayISO, currentMonth, PAYMENT_MODES } from '../lib/format';
import { downloadFile } from '../lib/backup';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';

const CATEGORIES = ['Electricity', 'Food ingredients', 'Internet', 'Cleaning', 'Maintenance', 'Repairs', 'Staff', 'Rent/property expense', 'Other'];
const inputCls = 'bg-[#FDFCFB] border-[#E6E4E0] focus-visible:ring-terracotta-500';

export default function Expenses() {
  const [month, setMonth] = useState(currentMonth());
  const [expenses, setExpenses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ date: todayISO(), category: 'Electricity', description: '', amount: '', paymentMethod: 'Cash', reference: '' });

  const reload = () => fetchExpenses({ month }).then(setExpenses).catch((e) => toast.error(e.message));
  useEffect(() => { setLoading(true); reload().finally(() => setLoading(false)); }, [month]);

  const total = expenses.reduce((a, e) => a + e.amount, 0);

  const handleAdd = async () => {
    if (num(form.amount) <= 0) {
      toast.error('Enter a valid amount');
      return;
    }
    setSaving(true);
    try {
      await createExpense({ ...form, amount: num(form.amount) });
      toast.success('Expense added');
      setForm((f) => ({ ...f, description: '', amount: '', reference: '' }));
      reload();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSaving(false);
    }
  };

  const exportCSV = () => {
    const esc = (v) => (/[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : v);
    const lines = ['Date,Category,Description,Amount,Payment Method,Reference'];
    expenses.forEach((e) => lines.push([e.date, e.category, e.description, e.amount, e.paymentMethod, e.reference].map(esc).join(',')));
    downloadFile(lines.join('\n'), `ShreeStayHomesPG_Expenses_${month}.csv`, 'text/csv');
    toast.success('Expenses CSV exported');
  };

  return (
    <div data-testid="expenses-page" className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-extrabold tracking-tight text-stone-900 sm:text-4xl">Expenses</h1>
          <p className="mt-1 text-sm text-stone-600">Track PG operating expenses. Net Profit = Revenue − Expenses (see Reports).</p>
        </div>
        <div className="flex items-center gap-2">
          <Input type="month" value={month} onChange={(e) => setMonth(e.target.value)} data-testid="expenses-month" className="w-44 border-[#E6E4E0] bg-white" />
          <Button variant="outline" onClick={exportCSV} data-testid="expenses-csv-btn" className="border-stone-200 bg-white">
            <Download className="mr-2 h-4 w-4" /> CSV
          </Button>
        </div>
      </div>

      <div className="rounded-xl border border-[#E6E4E0] bg-white p-5 shadow-sm">
        <h2 className="flex items-center gap-2 font-heading text-lg font-bold text-stone-900"><Wallet className="h-5 w-5 text-terracotta-500" /> Add Expense</h2>
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Input type="date" value={form.date} onChange={(e) => setForm((f) => ({ ...f, date: e.target.value }))} data-testid="expense-date" className={inputCls} />
          <Select value={form.category} onValueChange={(v) => setForm((f) => ({ ...f, category: v }))}>
            <SelectTrigger data-testid="expense-category" className={inputCls}><SelectValue /></SelectTrigger>
            <SelectContent>{CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
          </Select>
          <Input value={form.description} onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))} placeholder="Description" data-testid="expense-description" className={inputCls} />
          <Input type="number" min="0" step="0.01" value={form.amount} onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))} placeholder="Amount ₹" data-testid="expense-amount" className={inputCls} />
          <Select value={form.paymentMethod} onValueChange={(v) => setForm((f) => ({ ...f, paymentMethod: v }))}>
            <SelectTrigger data-testid="expense-method" className={inputCls}><SelectValue /></SelectTrigger>
            <SelectContent>{PAYMENT_MODES.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
          </Select>
          <div className="flex gap-2">
            <Input value={form.reference} onChange={(e) => setForm((f) => ({ ...f, reference: e.target.value }))} placeholder="Ref / notes" data-testid="expense-reference" className={inputCls} />
            <Button onClick={handleAdd} disabled={saving} data-testid="expense-add-btn" className="shrink-0 bg-terracotta-500 text-white hover:bg-terracotta-600">
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            </Button>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-[#E6E4E0] bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-stone-200 px-5 py-3">
          <span className="text-sm font-semibold text-stone-800">{month} expenses</span>
          <span className="text-sm" data-testid="expenses-total">Total: <strong className="text-red-600">{inr(total)}</strong></span>
        </div>
        {loading ? (
          <div className="py-16 text-center text-sm text-stone-400">Loading…</div>
        ) : expenses.length === 0 ? (
          <div className="py-16 text-center text-sm text-stone-400" data-testid="expenses-empty">No expenses recorded for this month.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="expenses-table">
              <thead>
                <tr className="border-b border-stone-200 text-left text-xs uppercase tracking-wider text-stone-500">
                  <th className="px-4 py-2.5">Date</th><th className="px-4 py-2.5">Category</th>
                  <th className="px-4 py-2.5">Description</th><th className="px-4 py-2.5 text-right">Amount</th>
                  <th className="px-4 py-2.5">Method</th><th className="px-4 py-2.5">Reference</th><th className="px-4 py-2.5"></th>
                </tr>
              </thead>
              <tbody>
                {expenses.map((e) => (
                  <tr key={e.id} className="border-b border-stone-100" data-testid={`expense-row-${e.id}`}>
                    <td className="px-4 py-2.5 text-stone-600">{e.date}</td>
                    <td className="px-4 py-2.5"><span className="rounded-full bg-stone-100 px-2.5 py-0.5 text-xs font-medium text-stone-700">{e.category}</span></td>
                    <td className="px-4 py-2.5 text-stone-800">{e.description}</td>
                    <td className="px-4 py-2.5 text-right font-semibold text-stone-900">{inr(e.amount)}</td>
                    <td className="px-4 py-2.5 text-stone-600">{e.paymentMethod}</td>
                    <td className="px-4 py-2.5 text-xs text-stone-500">{e.reference}</td>
                    <td className="px-4 py-2.5 text-right">
                      <Button variant="ghost" size="icon" onClick={() => removeExpense(e.id).then(reload)} data-testid={`expense-delete-${e.id}`}>
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </td>
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
