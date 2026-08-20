import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Save, Loader2, ImagePlus, Trash2 } from 'lucide-react';
import { useSettings } from '../context/SettingsContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Switch } from '../components/ui/switch';

const inputCls = 'bg-[#FDFCFB] border-[#E6E4E0] focus-visible:ring-terracotta-500';

function ImageUpload({ label, value, onChange, testId }) {
  const handleFile = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 800 * 1024) {
      toast.error('Image too large — please use an image under 800 KB');
      return;
    }
    const reader = new FileReader();
    reader.onload = () => onChange(reader.result);
    reader.readAsDataURL(file);
  };
  return (
    <div>
      <Label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">{label}</Label>
      <div className="mt-1.5 flex items-center gap-3">
        {value ? (
          <img src={value} alt={label} className="h-14 w-14 rounded-md border border-stone-200 bg-white object-contain" data-testid={`${testId}-preview`} />
        ) : (
          <div className="flex h-14 w-14 items-center justify-center rounded-md border border-dashed border-stone-300 text-stone-300">
            <ImagePlus className="h-5 w-5" />
          </div>
        )}
        <div className="flex gap-2">
          <label className="cursor-pointer">
            <input type="file" accept="image/png,image/jpeg,image/svg+xml" className="hidden" onChange={handleFile} data-testid={testId} />
            <span className="inline-flex h-9 items-center rounded-md border border-stone-200 bg-white px-3 text-sm font-medium text-stone-700 hover:bg-stone-50">Upload</span>
          </label>
          {value && (
            <Button type="button" variant="ghost" size="icon" onClick={() => onChange('')} data-testid={`${testId}-remove`}>
              <Trash2 className="h-4 w-4 text-red-500" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Settings() {
  const { settings, updateSettings } = useSettings();
  const [form, setForm] = useState(settings);
  const [saving, setSaving] = useState(false);

  useEffect(() => setForm(settings), [settings]);

  const set = (k) => (e) => {
    const v = e?.target ? e.target.value : e;
    setForm((f) => ({ ...f, [k]: v }));
  };

  const handleSave = async () => {
    if (form.ownerEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.ownerEmail)) {
      toast.error('Owner email is not valid');
      return;
    }
    if (!form.invoicePrefix.trim()) {
      toast.error('Invoice prefix cannot be empty');
      return;
    }
    setSaving(true);
    try {
      await updateSettings({ ...form, invoicePrefix: form.invoicePrefix.trim().toUpperCase(), startingNumber: Math.max(1, Number(form.startingNumber) || 1) });
      toast.success('Settings saved on this device');
    } catch (e) {
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div data-testid="settings-page" className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-extrabold tracking-tight text-stone-900 sm:text-4xl">Settings</h1>
          <p className="mt-1 text-sm text-stone-600">Business branding, email and invoice defaults. Stored only on this device.</p>
        </div>
        <Button onClick={handleSave} disabled={saving} data-testid="settings-save-btn" className="bg-terracotta-500 text-white hover:bg-terracotta-600">
          {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
          Save Settings
        </Button>
      </div>

      <section className="rounded-xl border border-[#E6E4E0] bg-white p-6 shadow-sm">
        <h2 className="font-heading text-lg font-bold text-stone-900">PG Information</h2>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <Label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Business Name</Label>
            <Input value={form.businessName} onChange={set('businessName')} data-testid="settings-business-name" className={`mt-1.5 ${inputCls}`} />
          </div>
          <div>
            <Label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Subtitle</Label>
            <Input value={form.subtitle} onChange={set('subtitle')} data-testid="settings-subtitle" className={`mt-1.5 ${inputCls}`} />
          </div>
          <div className="sm:col-span-2">
            <Label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">PG Address</Label>
            <Textarea value={form.address} onChange={set('address')} rows={2} data-testid="settings-address" className={`mt-1.5 ${inputCls}`} placeholder="Street, Area, City, PIN" />
          </div>
          <div>
            <Label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Owner Mobile</Label>
            <Input value={form.mobile} onChange={set('mobile')} data-testid="settings-mobile" className={`mt-1.5 ${inputCls}`} />
          </div>
          <div>
            <Label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Contact Email</Label>
            <Input type="email" value={form.email} onChange={set('email')} data-testid="settings-email" className={`mt-1.5 ${inputCls}`} />
          </div>
          <div>
            <Label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">GSTIN (if applicable)</Label>
            <Input value={form.gstin} onChange={set('gstin')} data-testid="settings-gstin" className={`mt-1.5 ${inputCls}`} />
          </div>
        </div>
        <div className="mt-5 grid grid-cols-1 gap-6 sm:grid-cols-2">
          <ImageUpload label="Logo" value={form.logo} onChange={(v) => setForm((f) => ({ ...f, logo: v }))} testId="settings-logo-upload" />
          <ImageUpload label="Signature" value={form.signature} onChange={(v) => setForm((f) => ({ ...f, signature: v }))} testId="settings-signature-upload" />
        </div>
      </section>

      <section className="rounded-xl border border-[#E6E4E0] bg-white p-6 shadow-sm">
        <h2 className="font-heading text-lg font-bold text-stone-900">Email</h2>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <Label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Owner Email (receives every invoice)</Label>
            <Input type="email" value={form.ownerEmail} onChange={set('ownerEmail')} data-testid="settings-owner-email" className={`mt-1.5 ${inputCls}`} />
          </div>
          <div className="flex flex-col justify-end gap-4 pb-1">
            <label className="flex items-center justify-between gap-3 text-sm text-stone-700">
              Email every invoice to owner automatically
              <Switch checked={form.autoOwnerEmail} onCheckedChange={(v) => set('autoOwnerEmail')(v)} data-testid="settings-auto-owner-email" />
            </label>
            <label className="flex items-center justify-between gap-3 text-sm text-stone-700">
              Show "Send invoice to tenant" option
              <Switch checked={form.tenantEmailEnabled} onCheckedChange={(v) => set('tenantEmailEnabled')(v)} data-testid="settings-tenant-email-option" />
            </label>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-[#E6E4E0] bg-white p-6 shadow-sm">
        <h2 className="font-heading text-lg font-bold text-stone-900">Invoice</h2>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <Label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Invoice Prefix</Label>
            <Input value={form.invoicePrefix} onChange={set('invoicePrefix')} maxLength={8} data-testid="settings-invoice-prefix" className={`mt-1.5 ${inputCls}`} />
            <p className="mt-1 text-[11px] text-stone-400">e.g. SHPG-2026-0001</p>
          </div>
          <div>
            <Label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Starting Invoice Number</Label>
            <Input type="number" min="1" value={form.startingNumber} onChange={set('startingNumber')} data-testid="settings-starting-number" className={`mt-1.5 ${inputCls}`} />
            <p className="mt-1 text-[11px] text-stone-400">Applies only if higher than the current sequence.</p>
          </div>
          <div>
            <Label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Default Payment Terms</Label>
            <Textarea value={form.paymentTerms} onChange={set('paymentTerms')} rows={2} data-testid="settings-payment-terms" className={`mt-1.5 ${inputCls}`} />
          </div>
          <div>
            <Label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Default Notes</Label>
            <Textarea value={form.notes} onChange={set('notes')} rows={2} data-testid="settings-notes" className={`mt-1.5 ${inputCls}`} />
          </div>
          <div className="sm:col-span-2">
            <Label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Watermark Text</Label>
            <Input value={form.watermarkText} onChange={set('watermarkText')} data-testid="settings-watermark-text" className={`mt-1.5 ${inputCls}`} />
          </div>
        </div>
      </section>
    </div>
  );
}
