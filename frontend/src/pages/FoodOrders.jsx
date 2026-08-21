import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { UtensilsCrossed, Plus, Trash2, Loader2, Check, Minus } from 'lucide-react';
import { fetchFoodToday, fetchFoodOrders, createFoodOrder, updateFoodOrder, removeFoodOrder, fetchTenants } from '../lib/api';
import { inr, todayISO, fmtDate } from '../lib/format';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';

const MEALS = ['Breakfast', 'Lunch', 'Dinner'];
const inputCls = 'bg-[#FDFCFB] border-[#E6E4E0] focus-visible:ring-terracotta-500';

export default function FoodOrders() {
  const [date, setDate] = useState(todayISO());
  const [today, setToday] = useState(null);
  const [orders, setOrders] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [form, setForm] = useState({ tenantId: '', mealType: 'Lunch', quantity: '1', pricePerMeal: '80', note: '' });
  const [saving, setSaving] = useState(false);

  const reload = () => {
    fetchFoodToday(date).then(setToday).catch((e) => toast.error(e.message));
    fetchFoodOrders({ date }).then(setOrders).catch(() => {});
  };
  useEffect(() => { reload(); }, [date]);
  useEffect(() => { fetchTenants().then(setTenants).catch(() => {}); }, []);

  const handleAdd = async () => {
    const tenant = tenants.find((t) => t.id === form.tenantId);
    if (!tenant) {
      toast.error('Select a tenant');
      return;
    }
    setSaving(true);
    try {
      await createFoodOrder({
        tenantId: tenant.id, tenantName: tenant.name, date, mealType: form.mealType,
        quantity: num(form.quantity), pricePerMeal: num(form.pricePerMeal), note: form.note,
      });
      toast.success(`${form.mealType} order added for ${tenant.name}`);
      setForm((f) => ({ ...f, note: '' }));
      reload();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSaving(false);
    }
  };

  const setStatus = async (order, status) => {
    try {
      await updateFoodOrder(order.id, { ...order, status });
      reload();
    } catch (e) {
      toast.error(e.message);
    }
  };

  const num = (v) => parseFloat(v) || 0;

  return (
    <div data-testid="food-page" className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-extrabold tracking-tight text-stone-900 sm:text-4xl">Food Orders</h1>
          <p className="mt-1 text-sm text-stone-600">On-demand meals. Only ordered meals are charged — monthly food totals flow into Monthly Billing automatically.</p>
        </div>
        <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} data-testid="food-date" className="w-44 border-[#E6E4E0] bg-white" />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {MEALS.map((meal) => (
          <div key={meal} className="rounded-xl border border-[#E6E4E0] bg-white p-5 shadow-sm" data-testid={`food-meal-card-${meal.toLowerCase()}`}>
            <div className="flex items-center justify-between">
              <span className="font-heading text-base font-bold text-stone-900">{meal}</span>
              <span className="rounded-full bg-terracotta-50 px-2.5 py-0.5 text-xs font-semibold text-terracotta-700">
                {today?.meals?.[meal]?.length || 0} orders
              </span>
            </div>
            <div className="mt-3 space-y-1.5">
              {(today?.meals?.[meal] || []).length === 0 && <div className="text-sm text-stone-400">No orders</div>}
              {(today?.meals?.[meal] || []).map((o) => (
                <div key={o.id} className="flex items-center justify-between text-sm">
                  <span className="text-stone-800">{o.tenantName}{o.quantity > 1 ? ` ×${o.quantity}` : ''}</span>
                  {o.status === 'Served' ? <Check className="h-4 w-4 text-green-600" /> : <Minus className="h-4 w-4 text-stone-300" />}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-[#E6E4E0] bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="font-heading text-lg font-bold text-stone-900">{fmtDate(date)} — Day Summary</h2>
          <div className="text-sm text-stone-600" data-testid="food-total-meals">
            Total meals: <strong>{today?.totalMeals || 0}</strong> · Amount: <strong>{inr(today?.totalAmount || 0)}</strong>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-1 gap-3 border-t border-stone-100 pt-4 sm:grid-cols-6">
          <Select value={form.tenantId} onValueChange={(v) => setForm((f) => ({ ...f, tenantId: v }))}>
            <SelectTrigger data-testid="food-add-tenant" className={inputCls}><SelectValue placeholder="Tenant" /></SelectTrigger>
            <SelectContent>
              {tenants.map((t) => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={form.mealType} onValueChange={(v) => setForm((f) => ({ ...f, mealType: v }))}>
            <SelectTrigger data-testid="food-add-meal" className={inputCls}><SelectValue /></SelectTrigger>
            <SelectContent>{MEALS.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
          </Select>
          <Input type="number" min="1" value={form.quantity} onChange={(e) => setForm((f) => ({ ...f, quantity: e.target.value }))} placeholder="Qty" data-testid="food-add-qty" className={inputCls} />
          <Input type="number" min="0" value={form.pricePerMeal} onChange={(e) => setForm((f) => ({ ...f, pricePerMeal: e.target.value }))} placeholder="Price ₹" data-testid="food-add-price" className={inputCls} />
          <Input value={form.note} onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))} placeholder="Note (optional)" data-testid="food-add-note" className={inputCls} />
          <Button onClick={handleAdd} disabled={saving} data-testid="food-add-btn" className="bg-terracotta-500 text-white hover:bg-terracotta-600">
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plus className="mr-2 h-4 w-4" />} Add Order
          </Button>
        </div>

        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm" data-testid="food-orders-table">
            <thead>
              <tr className="border-b border-stone-200 text-left text-xs uppercase tracking-wider text-stone-500">
                <th className="px-3 py-2">Tenant</th><th className="px-3 py-2">Meal</th>
                <th className="px-3 py-2 text-right">Qty</th><th className="px-3 py-2 text-right">Price</th>
                <th className="px-3 py-2 text-right">Total</th><th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Note</th><th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {orders.length === 0 && <tr><td colSpan={8} className="px-3 py-8 text-center text-stone-400" data-testid="food-empty">No food orders for this date.</td></tr>}
              {orders.map((o) => (
                <tr key={o.id} className="border-b border-stone-100" data-testid={`food-order-row-${o.id}`}>
                  <td className="px-3 py-2 font-medium text-stone-900">{o.tenantName}</td>
                  <td className="px-3 py-2 text-stone-600">{o.mealType}</td>
                  <td className="px-3 py-2 text-right">{o.quantity}</td>
                  <td className="px-3 py-2 text-right">{inr(o.pricePerMeal)}</td>
                  <td className="px-3 py-2 text-right font-semibold">{inr(o.total)}</td>
                  <td className="px-3 py-2">
                    <Select value={o.status} onValueChange={(v) => setStatus(o, v)}>
                      <SelectTrigger data-testid={`food-status-${o.id}`} className="h-8 w-32 border-[#E6E4E0] bg-[#FDFCFB] text-xs"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {['Ordered', 'Served', 'Cancelled'].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </td>
                  <td className="px-3 py-2 text-xs text-stone-500">{o.note}</td>
                  <td className="px-3 py-2 text-right">
                    <Button variant="ghost" size="icon" onClick={() => removeFoodOrder(o.id).then(reload)} data-testid={`food-delete-${o.id}`}>
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex items-center gap-2 text-xs text-stone-400">
        <UtensilsCrossed className="h-3.5 w-3.5" /> Cancelled orders are never billed. Monthly totals appear in Monthly Billing under "Food".
      </div>
    </div>
  );
}
