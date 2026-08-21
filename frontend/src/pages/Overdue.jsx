import { useEffect, useState } from 'react';
import { AlarmClock, CalendarClock, CalendarCheck, MessageCircle } from 'lucide-react';
import { fetchOverdue } from '../lib/api';
import { useSettings } from '../context/SettingsContext';
import { inr, fmtDate, monthLabel, waReminderLink } from '../lib/format';
import { Button } from '../components/ui/button';

function Card({ label, count, amount, tone, testId }) {
  const colors = {
    red: 'border-red-200 bg-red-50 text-red-700',
    amber: 'border-amber-200 bg-amber-50 text-amber-700',
    green: 'border-green-200 bg-green-50 text-green-700',
  };
  return (
    <div className={`rounded-xl border p-5 ${colors[tone]}`} data-testid={testId}>
      <div className="text-xs font-semibold uppercase tracking-[0.1em]">{label}</div>
      <div className="mt-2 font-heading text-2xl font-extrabold">{count}</div>
      <div className="mt-1 text-sm font-medium">{inr(amount)}</div>
    </div>
  );
}

function InvoiceTable({ title, icon: Icon, rows, showDays, businessName, emptyText }) {
  return (
    <div className="rounded-xl border border-[#E6E4E0] bg-white shadow-sm">
      <div className="flex items-center gap-2 border-b border-stone-200 px-5 py-3">
        <Icon className="h-4 w-4 text-terracotta-500" />
        <span className="text-sm font-semibold text-stone-800">{title}</span>
      </div>
      {rows.length === 0 ? (
        <div className="py-10 text-center text-sm text-stone-400">{emptyText}</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-stone-200 text-left text-xs uppercase tracking-wider text-stone-500">
                <th className="px-4 py-2.5">Tenant</th>
                <th className="px-4 py-2.5">Invoice</th>
                <th className="px-4 py-2.5">Month</th>
                <th className="px-4 py-2.5">Due Date</th>
                {showDays && <th className="px-4 py-2.5 text-right">Days Overdue</th>}
                <th className="px-4 py-2.5 text-right">Pending</th>
                <th className="px-4 py-2.5 text-right">Reminder</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((inv) => (
                <tr key={inv.id} className="border-b border-stone-100" data-testid={`overdue-row-${inv.invoiceNumber}`}>
                  <td className="px-4 py-2.5 font-semibold text-stone-900">{inv.tenantName}</td>
                  <td className="px-4 py-2.5 text-stone-600">{inv.invoiceNumber}</td>
                  <td className="px-4 py-2.5 text-stone-600">{monthLabel(inv.billingMonth)}</td>
                  <td className="px-4 py-2.5 text-stone-600">{fmtDate(inv.dueDate)}</td>
                  {showDays && <td className="px-4 py-2.5 text-right font-bold text-red-600">{inv.daysOverdue}d</td>}
                  <td className="px-4 py-2.5 text-right font-semibold text-red-600">{inr(inv.balanceDue)}</td>
                  <td className="px-4 py-2.5 text-right">
                    <Button asChild variant="outline" size="sm" className="border-green-300 text-green-700 hover:bg-green-50" data-testid={`whatsapp-${inv.invoiceNumber}`}>
                      <a href={waReminderLink(inv, businessName)} target="_blank" rel="noopener noreferrer">
                        <MessageCircle className="mr-1.5 h-3.5 w-3.5" /> WhatsApp
                      </a>
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function Overdue() {
  const { settings } = useSettings();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchOverdue().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const s = data?.summary;
  return (
    <div data-testid="overdue-page" className="space-y-6">
      <div>
        <h1 className="font-heading text-3xl font-extrabold tracking-tight text-stone-900 sm:text-4xl">Overdue Tracking</h1>
        <p className="mt-1 text-sm text-stone-600">Invoices past their due date with pending balance.</p>
      </div>
      {loading ? (
        <div className="py-24 text-center text-sm text-stone-400">Loading…</div>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Card label="Overdue" count={s.overdueCount} amount={s.overdueAmount} tone="red" testId="overdue-summary-overdue" />
            <Card label="Due Today" count={s.dueTodayCount} amount={s.dueTodayAmount} tone="amber" testId="overdue-summary-today" />
            <Card label="Upcoming" count={s.upcomingCount} amount={s.upcomingAmount} tone="green" testId="overdue-summary-upcoming" />
          </div>
          <InvoiceTable title="Overdue" icon={AlarmClock} rows={data.overdue} showDays businessName={settings.businessName} emptyText="No overdue invoices." />
          <InvoiceTable title="Due Today" icon={CalendarClock} rows={data.dueToday} businessName={settings.businessName} emptyText="Nothing due today." />
          <InvoiceTable title="Upcoming Due" icon={CalendarCheck} rows={data.upcoming} businessName={settings.businessName} emptyText="No upcoming dues." />
        </>
      )}
    </div>
  );
}
