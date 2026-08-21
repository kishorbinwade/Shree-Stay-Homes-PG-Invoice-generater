import { useEffect, useMemo, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { toast } from 'sonner';
import { Users, FilePlus2, Trash2, Search } from 'lucide-react';
import { fetchTenants, fetchInvoices, removeTenant } from '../lib/api';
import { inr, fmtDate } from '../lib/format';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../components/ui/alert-dialog';

export default function Tenants() {
  const navigate = useNavigate();
  const [tenants, setTenants] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [pendingDelete, setPendingDelete] = useState(null);

  const reload = () =>
    Promise.all([fetchTenants(), fetchInvoices()])
      .then(([t, i]) => { setTenants(t); setInvoices(i); })
      .catch(() => {});

  useEffect(() => {
    reload().finally(() => setLoading(false));
  }, []);

  const aggregates = useMemo(() => {
    const map = {};
    for (const inv of invoices) {
      const key = (inv.tenantMobile || inv.tenantName || '').toLowerCase().trim();
      if (!key) continue;
      if (!map[key]) map[key] = { billed: 0, pending: 0, count: 0, lastDate: '' };
      map[key].billed += Number(inv.total) || 0;
      map[key].pending += Math.max(Number(inv.balanceDue) || 0, 0);
      map[key].count += 1;
      const d = inv.invoiceDate || inv.createdAt || '';
      if (d > map[key].lastDate) map[key].lastDate = d;
    }
    return map;
  }, [invoices]);

  const filtered = tenants.filter((t) => {
    const needle = q.trim().toLowerCase();
    return !needle || t.name?.toLowerCase().includes(needle) || t.mobile?.includes(needle) || t.roomNumber?.toLowerCase().includes(needle);
  });

  const handleDelete = async () => {
    if (!pendingDelete) return;
    await removeTenant(pendingDelete.id);
    toast.success(`Tenant ${pendingDelete.name} removed (invoices are kept)`);
    setPendingDelete(null);
    reload();
  };

  return (
    <div data-testid="tenants-page" className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-extrabold tracking-tight text-stone-900 sm:text-4xl">Tenants</h1>
          <p className="mt-1 text-sm text-stone-600">Tenants are added automatically when you create invoices.</p>
        </div>
        <Button asChild className="bg-terracotta-500 text-white hover:bg-terracotta-600">
          <Link to="/invoices/new" data-testid="tenants-new-invoice-btn"><FilePlus2 className="mr-2 h-4 w-4" /> New Invoice</Link>
        </Button>
      </div>

      <div className="rounded-xl border border-[#E6E4E0] bg-white p-4 shadow-sm">
        <div className="relative max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, mobile or room…" data-testid="tenants-search" className="border-[#E6E4E0] bg-[#FDFCFB] pl-9" />
        </div>
      </div>

      <div className="rounded-xl border border-[#E6E4E0] bg-white shadow-sm">
        {loading ? (
          <div className="py-24 text-center text-sm text-stone-400" data-testid="tenants-loading">Loading tenants…</div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center py-24 text-center" data-testid="tenants-empty-state">
            <Users className="h-12 w-12 text-stone-300" />
            <p className="mt-3 text-sm text-stone-500">No tenants yet. They appear here after you create invoices.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="tenants-table">
              <thead>
                <tr className="border-b border-stone-200 text-left text-xs uppercase tracking-wider text-stone-500">
                  <th className="px-4 py-3">Tenant</th>
                  <th className="px-4 py-3">Mobile</th>
                  <th className="px-4 py-3">Room/Bed</th>
                  <th className="px-4 py-3 text-right">Invoices</th>
                  <th className="px-4 py-3 text-right">Total Billed</th>
                  <th className="px-4 py-3 text-right">Pending</th>
                  <th className="px-4 py-3">Last Invoice</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((t) => {
                  const agg = aggregates[t.id] || { billed: 0, pending: 0, count: 0, lastDate: '' };
                  return (
                    <tr key={t.id} className="border-b border-stone-100 transition-colors duration-150 hover:bg-stone-50" data-testid={`tenant-row-${t.id}`}>
                      <td className="px-4 py-3">
                        <div className="font-semibold text-stone-900">{t.name}</div>
                        {t.occupation && <div className="text-xs text-stone-500">{t.occupation}</div>}
                      </td>
                      <td className="px-4 py-3 text-stone-600">{t.mobile || '-'}</td>
                      <td className="px-4 py-3 text-stone-600">{t.roomNumber || '-'}/{t.bedNumber || '-'}</td>
                      <td className="px-4 py-3 text-right text-stone-600">{agg.count}</td>
                      <td className="px-4 py-3 text-right font-medium">{inr(agg.billed)}</td>
                      <td className={`px-4 py-3 text-right font-medium ${agg.pending > 0 ? 'text-red-600' : 'text-stone-500'}`}>{inr(agg.pending)}</td>
                      <td className="px-4 py-3 text-stone-600">{agg.lastDate ? fmtDate(agg.lastDate) : '-'}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="icon" title="New invoice for tenant" onClick={() => navigate(`/invoices/new?tenant=${t.id}`)} data-testid={`tenant-new-invoice-${t.id}`}>
                            <FilePlus2 className="h-4 w-4 text-stone-500" />
                          </Button>
                          <Button variant="ghost" size="icon" title="Remove tenant" onClick={() => setPendingDelete(t)} data-testid={`tenant-delete-${t.id}`}>
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <AlertDialog open={!!pendingDelete} onOpenChange={(o) => !o && setPendingDelete(null)}>
        <AlertDialogContent className="bg-white">
          <AlertDialogHeader>
            <AlertDialogTitle>Remove tenant {pendingDelete?.name}?</AlertDialogTitle>
            <AlertDialogDescription>Only the tenant profile is removed. Their invoices remain in history.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="tenant-delete-cancel">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} data-testid="tenant-delete-confirm" className="bg-red-600 text-white hover:bg-red-700">Remove</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
