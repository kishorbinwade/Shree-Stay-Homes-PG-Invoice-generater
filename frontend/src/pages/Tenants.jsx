import { useEffect, useMemo, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { toast } from 'sonner';
import { Users, FilePlus2, Trash2, Search, BookOpen, Pencil, Loader2 } from 'lucide-react';
import { fetchTenants, fetchInvoices, removeTenant, updateTenant } from '../lib/api';
import { inr, fmtDate, num } from '../lib/format';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
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
  const [editing, setEditing] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [editErrors, setEditErrors] = useState({});
  const [savingEdit, setSavingEdit] = useState(false);

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

  const EDIT_FIELDS = [
    ['name', 'Name', 'text'], ['mobile', 'Mobile', 'text'], ['email', 'Email', 'email'],
    ['occupation', 'Occupation', 'text'], ['emergencyContact', 'Emergency Contact', 'text'],
    ['roomNumber', 'Room Number', 'text'], ['bedNumber', 'Bed Number', 'text'],
    ['rent', 'Monthly Rent (₹)', 'number'], ['deposit', 'Security Deposit (₹)', 'number'],
    ['checkIn', 'Check-in Date', 'date'], ['checkOut', 'Check-out Date', 'date'],
  ];

  const openEdit = (t) => {
    setEditing(t);
    setEditErrors({});
    setEditForm({
      name: t.name || '', mobile: t.mobile || '', email: t.email || '',
      occupation: t.occupation || '', emergencyContact: t.emergencyContact || '',
      roomNumber: t.roomNumber || '', bedNumber: t.bedNumber || '',
      rent: t.rent ?? '', deposit: t.deposit ?? '',
      checkIn: t.checkIn || '', checkOut: t.checkOut || '',
    });
  };

  const setEditField = (k) => (e) => {
    setEditForm((f) => ({ ...f, [k]: e.target.value }));
    setEditErrors((er) => ({ ...er, [k]: undefined }));
  };

  const handleEditSave = async () => {
    const e = {};
    if (!editForm.name.trim()) e.name = 'Name is required';
    if (editForm.mobile && !/^[6-9]\d{9}$/.test(editForm.mobile.trim())) e.mobile = 'Enter a valid 10-digit mobile number';
    if (editForm.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(editForm.email.trim())) e.email = 'Enter a valid email address';
    if (num(editForm.rent) < 0) e.rent = 'Amount cannot be negative';
    if (num(editForm.deposit) < 0) e.deposit = 'Amount cannot be negative';
    if (editForm.checkIn && editForm.checkOut && editForm.checkOut < editForm.checkIn) e.checkOut = 'Check-out cannot be before check-in';
    setEditErrors(e);
    if (Object.values(e).some(Boolean)) return;
    setSavingEdit(true);
    try {
      await updateTenant(editing.id, {
        ...editForm,
        name: editForm.name.trim(), mobile: editForm.mobile.trim(), email: editForm.email.trim(),
        rent: num(editForm.rent), deposit: num(editForm.deposit),
      });
      toast.success(`${editForm.name.trim()} updated — new details will auto-fill on the next invoice`);
      setEditing(null);
      reload();
    } catch (err) {
      toast.error(err.message || 'Failed to update tenant');
    } finally {
      setSavingEdit(false);
    }
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
                        <Link to={`/tenants/${encodeURIComponent(t.id)}/ledger`} className="font-semibold text-stone-900 hover:text-terracotta-600" data-testid={`tenant-name-link-${t.id}`}>{t.name}</Link>
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
                          <Button variant="ghost" size="icon" title="View ledger" onClick={() => navigate(`/tenants/${encodeURIComponent(t.id)}/ledger`)} data-testid={`tenant-ledger-${t.id}`}>
                            <BookOpen className="h-4 w-4 text-terracotta-600" />
                          </Button>
                          <Button variant="ghost" size="icon" title="Edit tenant details" onClick={() => openEdit(t)} data-testid={`tenant-edit-${t.id}`}>
                            <Pencil className="h-4 w-4 text-stone-500" />
                          </Button>
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

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto bg-white" data-testid="tenant-edit-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading">Edit Tenant — {editing?.name}</DialogTitle>
          </DialogHeader>
          <p className="text-xs text-stone-500">Updated details auto-fill when you select this tenant while creating an invoice.</p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {EDIT_FIELDS.map(([k, label, type]) => (
              <div key={k}>
                <Label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">{label}</Label>
                <Input
                  type={type}
                  min={type === 'number' ? '0' : undefined}
                  step={type === 'number' ? '0.01' : undefined}
                  maxLength={k === 'mobile' ? 10 : undefined}
                  value={editForm[k] ?? ''}
                  onChange={setEditField(k)}
                  data-testid={`edit-${k}`}
                  className={`mt-1.5 bg-[#FDFCFB] border-[#E6E4E0] focus-visible:ring-terracotta-500 ${editErrors[k] ? 'border-red-400' : ''}`}
                />
                {editErrors[k] && <p className="mt-1 text-xs text-red-600" data-testid={`edit-${k}-error`}>{editErrors[k]}</p>}
              </div>
            ))}
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="outline" onClick={() => setEditing(null)} data-testid="tenant-edit-cancel" className="border-stone-200">Cancel</Button>
            <Button onClick={handleEditSave} disabled={savingEdit} data-testid="tenant-edit-save" className="bg-terracotta-500 text-white hover:bg-terracotta-600">
              {savingEdit ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {savingEdit ? 'Saving…' : 'Save Changes'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

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
