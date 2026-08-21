import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { FileText, IndianRupee, Wallet, Clock3, FilePlus2, ArrowRight } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { fetchInvoices } from '../lib/api';
import { inr, currentMonth, monthLabel, fmtDate } from '../lib/format';
import { Button } from '../components/ui/button';

function StatCard({ icon: Icon, label, value, sub, delay, testId }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay }}
      data-testid={testId}
      className="rounded-xl border border-[#E6E4E0] bg-white p-6 shadow-sm"
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-[0.1em] text-stone-500">{label}</span>
        <Icon className="h-4 w-4 text-terracotta-500" />
      </div>
      <div className="mt-3 font-heading text-2xl font-extrabold tracking-tight text-stone-900">{value}</div>
      {sub && <div className="mt-1 text-xs text-stone-500">{sub}</div>}
    </motion.div>
  );
}

function StatusBadge({ status }) {
  const cls =
    status === 'Paid'
      ? 'bg-green-50 text-green-700'
      : status === 'Pending'
        ? 'bg-red-50 text-red-700'
        : 'bg-amber-50 text-amber-700';
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>{status}</span>;
}

export default function Dashboard() {
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchInvoices()
      .then(setInvoices)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const stats = useMemo(() => {
    const cm = currentMonth();
    const sum = (fn) => invoices.reduce((a, i) => a + fn(i), 0);
    return {
      count: invoices.length,
      billed: sum((i) => Number(i.total) || 0),
      collected: sum((i) => Math.min(Number(i.amountPaid) || 0, Number(i.total) || 0)),
      pending: sum((i) => Math.max(Number(i.balanceDue) || 0, 0)),
      monthCollected: sum((i) => (i.billingMonth === cm ? Math.min(Number(i.amountPaid) || 0, Number(i.total) || 0) : 0)),
      monthPending: sum((i) => (i.billingMonth === cm ? Math.max(Number(i.balanceDue) || 0, 0) : 0)),
    };
  }, [invoices]);

  const chartData = useMemo(() => {
    const months = [];
    const now = new Date();
    for (let k = 5; k >= 0; k--) {
      const d = new Date(now.getFullYear(), now.getMonth() - k, 1);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      months.push({ key, month: d.toLocaleDateString('en-IN', { month: 'short' }), billed: 0, collected: 0 });
    }
    for (const i of invoices) {
      const m = months.find((x) => x.key === i.billingMonth);
      if (m) {
        m.billed += Number(i.total) || 0;
        m.collected += Math.min(Number(i.amountPaid) || 0, Number(i.total) || 0);
      }
    }
    return months;
  }, [invoices]);

  const recent = invoices.slice(0, 5);

  return (
    <div data-testid="dashboard-page" className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-extrabold tracking-tight text-stone-900 sm:text-4xl">Dashboard</h1>
          <p className="mt-1 text-sm text-stone-600">Billing overview for {monthLabel(currentMonth())}</p>
        </div>
        <Button asChild className="bg-terracotta-500 hover:bg-terracotta-600 text-white">
          <Link to="/invoices/new" data-testid="dashboard-new-invoice-btn">
            <FilePlus2 className="mr-2 h-4 w-4" /> New Invoice
          </Link>
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={FileText} label="Total Invoices" value={stats.count} delay={0} testId="stat-total-invoices" />
        <StatCard icon={IndianRupee} label="Total Billed" value={inr(stats.billed)} delay={0.05} testId="stat-total-billed" />
        <StatCard icon={Wallet} label="Total Collected" value={inr(stats.collected)} sub={`This month: ${inr(stats.monthCollected)}`} delay={0.1} testId="stat-total-collected" />
        <StatCard icon={Clock3} label="Total Pending" value={inr(stats.pending)} sub={`This month: ${inr(stats.monthPending)}`} delay={0.15} testId="stat-total-pending" />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-[#E6E4E0] bg-white p-6 shadow-sm">
          <h2 className="font-heading text-lg font-bold text-stone-900">Billed vs Collected</h2>
          <p className="text-xs text-stone-500">Last 6 billing months</p>
          <div className="mt-4 h-64" data-testid="dashboard-chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} barGap={4}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EFEDEA" vertical={false} />
                <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#5C5A57' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#8A8885' }} axisLine={false} tickLine={false} width={60} />
                <Tooltip formatter={(v) => inr(v)} cursor={{ fill: '#F7F5F2' }} />
                <Bar dataKey="billed" name="Billed" fill="#D85C40" radius={[4, 4, 0, 0]} />
                <Bar dataKey="collected" name="Collected" fill="#3A7D44" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-xl border border-[#E6E4E0] bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="font-heading text-lg font-bold text-stone-900">Recent Invoices</h2>
            <Link to="/history" className="flex items-center gap-1 text-xs font-medium text-terracotta-600 hover:text-terracotta-700" data-testid="dashboard-view-all-link">
              View all <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          {loading ? (
            <div className="py-16 text-center text-sm text-stone-400" data-testid="dashboard-loading">Loading…</div>
          ) : recent.length === 0 ? (
            <div className="flex flex-col items-center py-16 text-center" data-testid="dashboard-empty-state">
              <FileText className="h-12 w-12 text-stone-300" />
              <p className="mt-3 text-sm text-stone-500">No invoices yet. Create your first invoice to see stats here.</p>
              <Button asChild className="mt-4 bg-terracotta-500 hover:bg-terracotta-600 text-white">
                <Link to="/invoices/new" data-testid="dashboard-create-first-btn">Create First Invoice</Link>
              </Button>
            </div>
          ) : (
            <div className="mt-3 divide-y divide-stone-100" data-testid="dashboard-recent-list">
              {recent.map((i) => (
                <div key={i.id} className="flex items-center justify-between gap-3 py-3" data-testid={`recent-invoice-${i.invoiceNumber}`}>
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-stone-900">{i.tenantName}</div>
                    <div className="text-xs text-stone-500">{i.invoiceNumber} · {fmtDate(i.invoiceDate)}</div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold text-stone-900">{inr(i.total)}</span>
                    <StatusBadge status={i.paymentStatus} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
