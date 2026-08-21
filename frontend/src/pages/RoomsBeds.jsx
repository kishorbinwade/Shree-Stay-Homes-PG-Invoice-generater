import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { BedDouble, Pencil, Loader2 } from 'lucide-react';
import { fetchTenants, updateTenant } from '../lib/api';
import { inr, num, fmtDate } from '../lib/format';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';

const inputCls = 'bg-[#FDFCFB] border-[#E6E4E0] focus-visible:ring-terracotta-500';
const EMPTY = { roomNumber: '', bedNumber: '', rent: '', deposit: '', joiningDate: '', status: 'Pending Admission' };

export default function RoomsBeds() {
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);

  const reload = () => fetchTenants().then(setTenants).catch((e) => toast.error(e.message));
  useEffect(() => { reload().finally(() => setLoading(false)); }, []);

  const openEdit = (t) => {
    setEditing(t);
    setForm({
      roomNumber: t.roomNumber || '', bedNumber: t.bedNumber || '',
      rent: t.rent || '', deposit: t.deposit || '',
      joiningDate: t.joiningDate || t.checkIn || '', status: t.status || 'Pending Admission',
    });
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await updateTenant(editing.id, {
        ...form, rent: num(form.rent), deposit: num(form.deposit),
        status: form.roomNumber ? 'Active' : form.status,
      });
      toast.success(`${editing.name} updated`);
      setEditing(null);
      reload();
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div data-testid="rooms-page" className="space-y-6">
      <div>
        <h1 className="font-heading text-3xl font-extrabold tracking-tight text-stone-900 sm:text-4xl">Rooms &amp; Beds</h1>
        <p className="mt-1 text-sm text-stone-600">Assign rooms, beds, rent and deposits. Tenants with a room are billed in Monthly Billing.</p>
      </div>

      <div className="rounded-xl border border-[#E6E4E0] bg-white shadow-sm">
        {loading ? (
          <div className="py-24 text-center text-sm text-stone-400">Loading…</div>
        ) : tenants.length === 0 ? (
          <div className="flex flex-col items-center py-24 text-center" data-testid="rooms-empty">
            <BedDouble className="h-12 w-12 text-stone-300" />
            <p className="mt-3 text-sm text-stone-500">No tenants yet. Create an invoice or import a Google Forms CSV.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="rooms-table">
              <thead>
                <tr className="border-b border-stone-200 text-left text-xs uppercase tracking-wider text-stone-500">
                  <th className="px-4 py-3">Tenant</th><th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Room</th><th className="px-4 py-3">Bed</th>
                  <th className="px-4 py-3 text-right">Rent</th><th className="px-4 py-3 text-right">Deposit</th>
                  <th className="px-4 py-3">Joining</th><th className="px-4 py-3 text-right">Assign</th>
                </tr>
              </thead>
              <tbody>
                {tenants.map((t) => (
                  <tr key={t.id} className="border-b border-stone-100" data-testid={`room-row-${t.id}`}>
                    <td className="px-4 py-3 font-semibold text-stone-900">{t.name}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${t.status === 'Active' ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'}`}>
                        {t.status || 'Pending Admission'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-stone-600">{t.roomNumber || '—'}</td>
                    <td className="px-4 py-3 text-stone-600">{t.bedNumber || '—'}</td>
                    <td className="px-4 py-3 text-right">{t.rent ? inr(t.rent) : '—'}</td>
                    <td className="px-4 py-3 text-right">{t.deposit ? inr(t.deposit) : '—'}</td>
                    <td className="px-4 py-3 text-stone-600">{fmtDate(t.joiningDate || t.checkIn)}</td>
                    <td className="px-4 py-3 text-right">
                      <Button variant="outline" size="sm" onClick={() => openEdit(t)} data-testid={`room-edit-${t.id}`} className="border-stone-200">
                        <Pencil className="mr-1.5 h-3.5 w-3.5" /> Assign
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="bg-white" data-testid="room-assign-dialog">
          <DialogHeader><DialogTitle className="font-heading">Assign — {editing?.name}</DialogTitle></DialogHeader>
          <div className="grid grid-cols-2 gap-3">
            {[['roomNumber', 'Room Number'], ['bedNumber', 'Bed Number'], ['rent', 'Monthly Rent (₹)'], ['deposit', 'Security Deposit (₹)']].map(([k, label]) => (
              <div key={k}>
                <Label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">{label}</Label>
                <Input value={form[k]} onChange={(e) => setForm((f) => ({ ...f, [k]: e.target.value }))}
                  type={k === 'rent' || k === 'deposit' ? 'number' : 'text'} min="0"
                  data-testid={`assign-${k}`} className={`mt-1.5 ${inputCls}`} />
              </div>
            ))}
            <div>
              <Label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Joining Date</Label>
              <Input type="date" value={form.joiningDate} onChange={(e) => setForm((f) => ({ ...f, joiningDate: e.target.value }))} data-testid="assign-joiningDate" className={`mt-1.5 ${inputCls}`} />
            </div>
            <div>
              <Label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Status</Label>
              <Select value={form.status} onValueChange={(v) => setForm((f) => ({ ...f, status: v }))}>
                <SelectTrigger data-testid="assign-status" className={`mt-1.5 ${inputCls}`}><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="Pending Admission">Pending Admission</SelectItem>
                  <SelectItem value="Active">Active</SelectItem>
                  <SelectItem value="Vacated">Vacated</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setEditing(null)} className="border-stone-200">Cancel</Button>
            <Button onClick={handleSave} disabled={saving} data-testid="room-save-btn" className="bg-terracotta-500 text-white hover:bg-terracotta-600">
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null} Save
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
