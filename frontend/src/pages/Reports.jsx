import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { TrendingUp, TrendingDown, IndianRupee, UtensilsCrossed } from 'lucide-react';
import { fetchMonthlyReport, fetchFoodSummary } from '../lib/api';
import { inr, currentMonth } from '../lib/format';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';

function Card({ label, value, sub, tone, testId }) {
  return (
    <div className="rounded-xl border border-[#E6E4E0] bg-white p-6 shadow-sm" data-testid={testId}>
      <div className="text-xs font-semibold uppercase tracking-[0.1em] text-stone-500">{label}</div>
      <div className={`mt-2 font-heading text-2xl font-extrabold ${tone === 'green' ? 'text-green-700' : tone === 'red' ? 'text-red-600' : 'text-stone-900'}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-stone-500">{sub}</div>}
    </div>
  );
}

export default function Reports() {
  const [month, setMonth] = useState(currentMonth());
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [report, setReport] = useState(null);
  const [food, setFood] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const useRange = dateFrom || dateTo;
      const [r, f] = await Promise.all([
        fetchMonthlyReport(useRange ? { dateFrom, dateTo } : { month }),
        fetchFoodSummary(useRange ? (dateFrom || month).slice(0, 7) : month),
      ]);
      setReport(r);
      setFood(f);
    } catch (e) {
      toast.error(e.message);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  return (
    <div data-testid="reports-page" className="space-y-6">
      <div>
        <h1 className="font-heading text-3xl font-extrabold tracking-tight text-stone-900 sm:text-4xl">Reports</h1>
        <p className="mt-1 text-sm text-stone-600">Revenue, expenses and profit. Net Profit = Revenue − Expenses.</p>
      </div>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-[#E6E4E0] bg-white p-4 shadow-sm">
        <div>
          <label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Month</label>
          <Input type="month" value={month} onChange={(e) => { setMonth(e.target.value); setDateFrom(''); setDateTo(''); }} data-testid="report-month" className="mt-1.5 w-44 border-[#E6E4E0] bg-[#FDFCFB]" />
        </div>
        <div>
          <label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">From</label>
          <Input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} data-testid="report-from" className="mt-1.5 w-44 border-[#E6E4E0] bg-[#FDFCFB]" />
        </div>
        <div>
          <label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">To</label>
          <Input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} data-testid="report-to" className="mt-1.5 w-44 border-[#E6E4E0] bg-[#FDFCFB]" />
        </div>
        <Button onClick={load} disabled={loading} data-testid="report-load-btn" className="bg-terracotta-500 text-white hover:bg-terracotta-600">
          {loading ? 'Loading…' : 'Run Report'}
        </Button>
      </div>

      {report && (
        <>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card label="Total Billed" value={inr(report.billed)} sub={`${report.invoiceCount} invoices`} testId="report-billed" />
            <Card label="Total Revenue (collected)" value={inr(report.revenue)} tone="green" testId="report-revenue" />
            <Card label="Total Expenses" value={inr(report.expenses)} sub={`${report.expenseCount} expenses`} tone="red" testId="report-expenses" />
            <Card label="Net Profit" value={inr(report.netProfit)} tone={report.netProfit >= 0 ? 'green' : 'red'} testId="report-net-profit" />
          </div>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <Card label="Pending Collection" value={inr(report.pending)} testId="report-pending" />
            <Card label="Food Revenue" value={inr(report.foodRevenue)} sub={food ? `${food.totalMeals} meals served/ordered` : ''} testId="report-food-revenue" />
            <Card label="Food Profit" value={inr(report.foodProfit)} sub={`Food expenses: ${inr(report.foodExpenses)}`} tone={report.foodProfit >= 0 ? 'green' : 'red'} testId="report-food-profit" />
          </div>
          {food && (
            <div className="rounded-xl border border-[#E6E4E0] bg-white p-6 shadow-sm" data-testid="report-food-summary">
              <h2 className="flex items-center gap-2 font-heading text-lg font-bold text-stone-900">
                <UtensilsCrossed className="h-5 w-5 text-terracotta-500" /> Food — {food.month}
              </h2>
              <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-5">
                <div><div className="text-xs uppercase tracking-wider text-stone-500">Breakfast</div><div className="font-heading text-xl font-bold" data-testid="report-breakfast-count">{food.mealCounts.Breakfast}</div></div>
                <div><div className="text-xs uppercase tracking-wider text-stone-500">Lunch</div><div className="font-heading text-xl font-bold" data-testid="report-lunch-count">{food.mealCounts.Lunch}</div></div>
                <div><div className="text-xs uppercase tracking-wider text-stone-500">Dinner</div><div className="font-heading text-xl font-bold" data-testid="report-dinner-count">{food.mealCounts.Dinner}</div></div>
                <div><div className="text-xs uppercase tracking-wider text-stone-500">Total Meals</div><div className="font-heading text-xl font-bold" data-testid="report-total-meals">{food.totalMeals}</div></div>
                <div><div className="text-xs uppercase tracking-wider text-stone-500">Food Revenue</div><div className="font-heading text-xl font-bold text-green-700">{inr(food.foodRevenue)}</div></div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
