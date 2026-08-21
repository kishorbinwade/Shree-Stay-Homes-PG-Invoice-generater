import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams, Link } from 'react-router-dom';
import { toast } from 'sonner';
import {
  FileCheck2, Eye, Download, Printer, Mail, Eraser, Loader2, CheckCircle2,
  AlertTriangle, XCircle, RotateCcw,
} from 'lucide-react';
import { useSettings } from '../context/SettingsContext';
import {
  fetchInvoice, fetchTenant, createInvoice as apiCreateInvoice,
  updateInvoice as apiUpdateInvoice, peekNextNumber,
} from '../lib/api';
import { buildInvoicePDF, downloadPDF, printPDF } from '../lib/pdf';
import { deliverInvoiceEmail } from '../lib/api';
import { inr, num, todayISO, currentMonth, computeTotals, paymentStatusOf, PAYMENT_MODES } from '../lib/format';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import InvoicePreview from '../components/InvoicePreview';

const EMPTY = {
  tenantName: '', tenantEmail: '', tenantMobile: '', roomNumber: '', bedNumber: '',
  checkIn: '', checkOut: '', occupation: '', emergencyContact: '',
  billingMonth: currentMonth(), dueDate: '',
  rent: '', securityDeposit: '', electricity: '', food: '', maintenance: '',
  otherCharges: '', discount: '', previousBalance: '',
  amountPaid: '', paymentMode: 'Cash', transactionId: '',
  sendToTenant: false, allowAdvance: false,
};

function Field({ label, required, error, children, testId }) {
  return (
    <div data-testid={testId ? `${testId}-field` : undefined}>
      <Label className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">
        {label} {required && <span className="text-terracotta-600">*</span>}
      </Label>
      <div className="mt-1.5">{children}</div>
      {error && <p className="mt-1 text-xs text-red-600" data-testid={testId ? `${testId}-error` : undefined}>{error}</p>}
    </div>
  );
}

const inputCls = 'bg-[#FDFCFB] border-[#E6E4E0] focus-visible:ring-terracotta-500';

export default function CreateInvoice() {
  const { settings } = useSettings();
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [form, setForm] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [emailing, setEmailing] = useState(false);
  const [result, setResult] = useState(null);
  const [nextNumber, setNextNumber] = useState('');
  const [previewOpen, setPreviewOpen] = useState(false);
  const [editId, setEditId] = useState(null);

  useEffect(() => {
    peekNextNumber().then((d) => setNextNumber(d.nextNumber)).catch(() => {});
  }, [result?.invoiceNumber]);

  useEffect(() => {
    const load = async () => {
      if (id) {
        const inv = await fetchInvoice(id);
        if (inv) {
          setForm({ ...EMPTY, ...inv, sendToTenant: !!inv.sendToTenant, allowAdvance: Number(inv.amountPaid) > Number(inv.total) });
          setResult(inv);
          setEditId(inv.id);
        } else {
          toast.error('Invoice not found');
          navigate('/history');
        }
      } else if (searchParams.get('from')) {
        const src = await fetchInvoice(searchParams.get('from'));
        if (src) {
          setForm({ ...EMPTY, ...src, amountPaid: '', transactionId: '', paymentMode: 'Cash', sendToTenant: false });
          toast.success('Invoice duplicated — adjust details and generate');
        }
      } else if (searchParams.get('tenant')) {
        const t = await fetchTenant(searchParams.get('tenant'));
        if (t) {
          setForm((f) => ({
            ...f, tenantName: t.name, tenantEmail: t.email, tenantMobile: t.mobile,
            roomNumber: t.roomNumber, bedNumber: t.bedNumber, occupation: t.occupation,
            emergencyContact: t.emergencyContact, checkIn: t.checkIn, checkOut: t.checkOut,
          }));
        }
      }
    };
    load().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const set = (k) => (e) => {
    const v = e?.target ? e.target.value : e;
    setForm((f) => ({ ...f, [k]: v }));
    setErrors((er) => ({ ...er, [k]: undefined }));
  };

  const totals = useMemo(() => computeTotals(form), [form]);
  const status = paymentStatusOf(totals.total, form.amountPaid);

  const validate = () => {
    const e = {};
    if (!form.tenantName.trim()) e.tenantName = 'Tenant name is required';
    if (!/^[6-9]\d{9}$/.test(form.tenantMobile.trim())) e.tenantMobile = 'Enter a valid 10-digit mobile number';
    if (form.tenantEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.tenantEmail.trim())) e.tenantEmail = 'Enter a valid email address';
    if (!form.billingMonth) e.billingMonth = 'Billing month is required';
    if (form.checkIn && form.checkOut && form.checkOut < form.checkIn) e.checkOut = 'Check-out cannot be before check-in';
    ['rent', 'securityDeposit', 'electricity', 'food', 'maintenance', 'otherCharges', 'discount', 'previousBalance', 'amountPaid']
      .forEach((k) => { if (num(form[k]) < 0) e[k] = 'Amount cannot be negative'; });
    if (num(form.discount) > totals.subtotal) e.discount = 'Discount cannot exceed subtotal';
    if (!form.allowAdvance && num(form.amountPaid) > totals.total) e.amountPaid = 'Amount paid exceeds total — tick "Allow advance" if intentional';
    if (form.sendToTenant && !form.tenantEmail.trim()) e.tenantEmail = 'Tenant email required to send invoice to tenant';
    return e;
  };

  const buildInvoice = (invoiceNumber, existing) => {
    const now = new Date().toISOString();
    return {
      ...existing,
      ...form,
      rent: num(form.rent), securityDeposit: num(form.securityDeposit), electricity: num(form.electricity),
      food: num(form.food), maintenance: num(form.maintenance), otherCharges: num(form.otherCharges),
      discount: num(form.discount), previousBalance: num(form.previousBalance), amountPaid: num(form.amountPaid),
      tenantName: form.tenantName.trim(),
      tenantEmail: form.tenantEmail.trim(),
      tenantMobile: form.tenantMobile.trim(),
      id: existing?.id || crypto.randomUUID(),
      invoiceNumber,
      invoiceDate: existing?.invoiceDate || todayISO(),
      subtotal: totals.subtotal,
      total: totals.total,
      balanceDue: totals.balanceDue,
      paymentStatus: paymentStatusOf(totals.total, form.amountPaid),
      emailStatus: existing?.emailStatus || { owner: 'pending', tenant: form.sendToTenant ? 'pending' : 'skipped' },
      createdAt: existing?.createdAt || now,
      updatedAt: now,
    };
  };

  const runEmail = async (invoice) => {
    setEmailing(true);
    try {
      const res = await deliverInvoiceEmail(invoice, settings);
      const updated = {
        ...invoice,
        emailStatus: { owner: res.owner, tenant: res.tenant, at: new Date().toISOString() },
      };
      await apiUpdateInvoice(invoice.id, updated);
      setResult(updated);
      if (res.owner === 'sent') toast.success(`Invoice emailed to owner (${settings.ownerEmail}) with PDF attached`);
      else toast.error(res.errors?.owner || 'Owner email failed — use Retry Email');
      if (invoice.sendToTenant) {
        if (res.tenant === 'sent') toast.success(`Copy emailed to tenant (${invoice.tenantEmail})`);
        else if (res.tenant === 'no-email') toast.warning('Tenant email not provided');
        else if (res.tenant !== 'skipped') toast.error('Tenant email failed');
      }
    } catch (err) {
      const updated = { ...invoice, emailStatus: { owner: 'failed', tenant: invoice.sendToTenant ? 'failed' : 'skipped', error: err.message } };
      await apiUpdateInvoice(invoice.id, updated);
      setResult(updated);
      toast.error(err.message || 'Email failed');
    } finally {
      setEmailing(false);
    }
  };

  const handleGenerate = async () => {
    const e = validate();
    setErrors(e);
    if (Object.values(e).some(Boolean)) {
      toast.error('Please fix the highlighted fields');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        ...form,
        rent: num(form.rent), securityDeposit: num(form.securityDeposit), electricity: num(form.electricity),
        food: num(form.food), maintenance: num(form.maintenance), otherCharges: num(form.otherCharges),
        discount: num(form.discount), previousBalance: num(form.previousBalance), amountPaid: num(form.amountPaid),
        tenantName: form.tenantName.trim(), tenantEmail: form.tenantEmail.trim(), tenantMobile: form.tenantMobile.trim(),
        invoiceDate: result?.invoiceDate || todayISO(),
      };
      const saved = editId ? await apiUpdateInvoice(editId, payload) : await apiCreateInvoice(payload);
      setResult(saved);
      setEditId(saved.id);
      peekNextNumber().then((d) => setNextNumber(d.nextNumber)).catch(() => {});
      toast.success(`Invoice ${saved.invoiceNumber} generated and saved`);
      if (settings.autoOwnerEmail || (settings.tenantEmailEnabled && form.sendToTenant)) {
        await runEmail(saved);
      }
    } catch (err) {
      toast.error(err.message || 'Failed to generate invoice');
    } finally {
      setSaving(false);
    }
  };

  const currentInvoice = () => {
    if (result && !isDirty) return result;
    return buildInvoice(result?.invoiceNumber || nextNumber, result);
  };
  const isDirty = useMemo(() => {
    if (!result) return true;
    const keys = Object.keys(EMPTY);
    return keys.some((k) => String(form[k] ?? '') !== String(result[k] ?? ''));
  }, [form, result]);

  const handleDownload = () => downloadPDF(buildInvoicePDF(currentInvoice(), settings), currentInvoice());
  const handlePrint = () => printPDF(buildInvoicePDF(currentInvoice(), settings));

  const handleClear = () => {
    setForm(EMPTY);
    setErrors({});
    setResult(null);
    setEditId(null);
    if (id) navigate('/invoices/new');
  };

  const emailBadge = (st) => {
    if (st === 'sent') return <span className="flex items-center gap-1.5 text-sm text-green-700"><CheckCircle2 className="h-4 w-4" /> Sent</span>;
    if (st === 'failed') return <span className="flex items-center gap-1.5 text-sm text-red-600"><XCircle className="h-4 w-4" /> Failed</span>;
    if (st === 'no-email') return <span className="flex items-center gap-1.5 text-sm text-amber-700"><AlertTriangle className="h-4 w-4" /> Tenant email not provided</span>;
    return <span className="text-sm text-stone-400">Not sent</span>;
  };

  return (
    <div data-testid="create-invoice-page" className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-extrabold tracking-tight text-stone-900 sm:text-4xl">
            {id ? 'Edit Invoice' : 'Create Invoice'}
          </h1>
          <p className="mt-1 text-sm text-stone-600">
            Next invoice number: <span className="font-semibold text-stone-800" data-testid="next-invoice-number">{result?.invoiceNumber || nextNumber}</span>
            {' · '}Date: {todayISO()}
          </p>
        </div>
        <Button variant="outline" onClick={handleClear} data-testid="clear-form-btn" className="border-stone-200">
          <Eraser className="mr-2 h-4 w-4" /> Clear Form
        </Button>
      </div>

      {result && (
        <div className="rounded-xl border border-green-200 bg-green-50 p-5" data-testid="generate-success-message">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-green-800">
              <CheckCircle2 className="h-5 w-5" />
              <span className="font-semibold">Invoice {result.invoiceNumber} saved successfully.</span>
            </div>
            <div className="flex items-center gap-6 text-sm" data-testid="email-status-panel">
              <span className="flex items-center gap-2 text-stone-500">Owner: <span data-testid="email-status-owner">{emailBadge(result.emailStatus?.owner)}</span></span>
              <span className="flex items-center gap-2 text-stone-500">Tenant: <span data-testid="email-status-tenant">{emailBadge(result.emailStatus?.tenant)}</span></span>
              {(result.emailStatus?.owner === 'failed' || result.emailStatus?.tenant === 'failed') && (
                <Button size="sm" variant="outline" onClick={() => runEmail(result)} disabled={emailing} data-testid="retry-email-btn" className="border-stone-200 bg-white">
                  {emailing ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="mr-1.5 h-3.5 w-3.5" />}
                  Retry Email
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="space-y-6 lg:col-span-8">
          <section className="rounded-xl border border-[#E6E4E0] bg-white p-6 shadow-sm">
            <h2 className="font-heading text-lg font-bold text-stone-900">Invoice Details</h2>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Billing Month" required error={errors.billingMonth} testId="billing-month">
                <Input type="month" value={form.billingMonth} onChange={set('billingMonth')} data-testid="billing-month" className={inputCls} />
              </Field>
              <Field label="Payment Due Date" testId="due-date">
                <Input type="date" value={form.dueDate} onChange={set('dueDate')} data-testid="due-date" className={inputCls} />
              </Field>
            </div>
          </section>

          <section className="rounded-xl border border-[#E6E4E0] bg-white p-6 shadow-sm">
            <h2 className="font-heading text-lg font-bold text-stone-900">Tenant Details</h2>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Tenant / Guest Name" required error={errors.tenantName} testId="tenant-name">
                <Input value={form.tenantName} onChange={set('tenantName')} placeholder="e.g. Rahul Sharma" data-testid="tenant-name" className={inputCls} />
              </Field>
              <Field label="Tenant Mobile" required error={errors.tenantMobile} testId="tenant-mobile">
                <Input value={form.tenantMobile} onChange={set('tenantMobile')} placeholder="10-digit mobile" maxLength={10} data-testid="tenant-mobile" className={inputCls} />
              </Field>
              <Field label="Tenant Email" error={errors.tenantEmail} testId="tenant-email">
                <Input type="email" value={form.tenantEmail} onChange={set('tenantEmail')} placeholder="optional" data-testid="tenant-email" className={inputCls} />
              </Field>
              <Field label="Occupation" testId="occupation">
                <Input value={form.occupation} onChange={set('occupation')} placeholder="e.g. Student, IT Professional" data-testid="occupation" className={inputCls} />
              </Field>
              <Field label="Room Number" testId="room-number">
                <Input value={form.roomNumber} onChange={set('roomNumber')} placeholder="e.g. 101" data-testid="room-number" className={inputCls} />
              </Field>
              <Field label="Bed Number" testId="bed-number">
                <Input value={form.bedNumber} onChange={set('bedNumber')} placeholder="e.g. B" data-testid="bed-number" className={inputCls} />
              </Field>
              <Field label="Check-in Date" testId="check-in">
                <Input type="date" value={form.checkIn} onChange={set('checkIn')} data-testid="check-in" className={inputCls} />
              </Field>
              <Field label="Check-out Date" error={errors.checkOut} testId="check-out">
                <Input type="date" value={form.checkOut} onChange={set('checkOut')} data-testid="check-out" className={inputCls} />
              </Field>
              <Field label="Emergency Contact" testId="emergency-contact">
                <Input value={form.emergencyContact} onChange={set('emergencyContact')} placeholder="optional" data-testid="emergency-contact" className={inputCls} />
              </Field>
            </div>
          </section>

          <section className="rounded-xl border border-[#E6E4E0] bg-white p-6 shadow-sm">
            <h2 className="font-heading text-lg font-bold text-stone-900">Charges (₹)</h2>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              {[
                ['rent', 'Rent', 'charge-rent'],
                ['securityDeposit', 'Security Deposit', 'charge-security-deposit'],
                ['electricity', 'Electricity Charges', 'charge-electricity'],
                ['food', 'Food / Meal Charges', 'charge-food'],
                ['maintenance', 'Maintenance Charges', 'charge-maintenance'],
                ['otherCharges', 'Other Charges', 'charge-other'],
                ['discount', 'Discount', 'charge-discount'],
                ['previousBalance', 'Previous Balance', 'charge-previous-balance'],
              ].map(([key, label, tid]) => (
                <Field key={key} label={label} error={errors[key]} testId={tid}>
                  <Input type="number" min="0" step="0.01" inputMode="decimal" value={form[key]} onChange={set(key)} placeholder="0.00" data-testid={tid} className={inputCls} />
                </Field>
              ))}
            </div>
          </section>

          <section className="rounded-xl border border-[#E6E4E0] bg-white p-6 shadow-sm">
            <h2 className="font-heading text-lg font-bold text-stone-900">Payment</h2>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Amount Paid (₹)" error={errors.amountPaid} testId="amount-paid">
                <Input type="number" min="0" step="0.01" inputMode="decimal" value={form.amountPaid} onChange={set('amountPaid')} placeholder="0.00" data-testid="amount-paid" className={inputCls} />
              </Field>
              <Field label="Payment Mode" testId="payment-mode">
                <Select value={form.paymentMode} onValueChange={set('paymentMode')}>
                  <SelectTrigger data-testid="payment-mode" className={inputCls}><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {PAYMENT_MODES.map((m) => <SelectItem key={m} value={m} data-testid={`payment-mode-${m.toLowerCase().replace(/\s/g, '-')}`}>{m}</SelectItem>)}
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Transaction ID / UTR" testId="transaction-id">
                <Input value={form.transactionId} onChange={set('transactionId')} placeholder="optional" data-testid="transaction-id" className={inputCls} />
              </Field>
              <div className="flex flex-col justify-end gap-3 pb-1">
                <label className="flex items-center gap-2 text-sm text-stone-700">
                  <Checkbox checked={form.allowAdvance} onCheckedChange={(v) => set('allowAdvance')(!!v)} data-testid="allow-advance" />
                  Allow advance / credit (paid &gt; total)
                </label>
                {settings.tenantEmailEnabled && (
                  <label className="flex items-center gap-2 text-sm text-stone-700">
                    <Checkbox checked={form.sendToTenant} onCheckedChange={(v) => set('sendToTenant')(!!v)} data-testid="send-to-tenant" />
                    Send invoice to tenant
                  </label>
                )}
              </div>
            </div>
          </section>
        </div>

        <div className="lg:col-span-4">
          <div className="sticky top-6 space-y-4">
            <div className="rounded-xl border border-[#E6E4E0] bg-white p-6 shadow-sm" data-testid="live-summary">
              <h3 className="font-heading text-base font-bold text-stone-900">Live Summary</h3>
              <div className="mt-3 space-y-1.5 text-sm">
                <div className="flex justify-between"><span className="text-stone-500">Subtotal</span><span className="font-medium" data-testid="summary-subtotal">{inr(totals.subtotal)}</span></div>
                <div className="flex justify-between"><span className="text-stone-500">Discount</span><span className="font-medium" data-testid="summary-discount">- {inr(num(form.discount))}</span></div>
                <div className="flex justify-between border-t border-stone-200 pt-2"><span className="font-semibold text-stone-800">Total Amount</span><span className="font-heading text-lg font-extrabold text-terracotta-600" data-testid="summary-total">{inr(totals.total)}</span></div>
                <div className="flex justify-between"><span className="text-stone-500">Amount Paid</span><span className="font-medium" data-testid="summary-paid">{inr(num(form.amountPaid))}</span></div>
                <div className="flex justify-between border-t border-stone-200 pt-2">
                  <span className="font-semibold text-stone-800">{totals.balanceDue < 0 ? 'Advance / Credit' : 'Balance Due'}</span>
                  <span className={`font-bold ${totals.balanceDue > 0 ? 'text-red-600' : 'text-green-700'}`} data-testid="summary-balance">{inr(Math.abs(totals.balanceDue))}</span>
                </div>
              </div>
              <div className="mt-3" data-testid="summary-status">
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${status === 'Paid' ? 'bg-green-50 text-green-700' : status === 'Pending' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700'}`}>
                  {status}
                </span>
              </div>
            </div>

            <div className="rounded-xl border border-[#E6E4E0] bg-white p-4 shadow-sm">
              <div className="grid grid-cols-2 gap-2">
                <Button onClick={handleGenerate} disabled={saving || emailing} data-testid="generate-invoice-btn" className="col-span-2 bg-terracotta-500 text-white hover:bg-terracotta-600">
                  {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileCheck2 className="mr-2 h-4 w-4" />}
                  {saving ? 'Generating…' : id ? 'Update Invoice' : 'Generate Invoice'}
                </Button>
                <Button variant="outline" onClick={() => setPreviewOpen(true)} data-testid="preview-invoice-btn" className="border-stone-200">
                  <Eye className="mr-2 h-4 w-4" /> Preview
                </Button>
                <Button variant="outline" onClick={handleDownload} data-testid="download-pdf-btn" className="border-stone-200">
                  <Download className="mr-2 h-4 w-4" /> Download
                </Button>
                <Button variant="outline" onClick={handlePrint} data-testid="print-invoice-btn" className="border-stone-200">
                  <Printer className="mr-2 h-4 w-4" /> Print
                </Button>
                <Button
                  variant="outline"
                  onClick={() => result && runEmail(result)}
                  disabled={!result || emailing}
                  data-testid="email-invoice-btn"
                  className="border-stone-200"
                >
                  {emailing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Mail className="mr-2 h-4 w-4" />}
                  Email Invoice
                </Button>
              </div>
              <p className="mt-3 text-[11px] leading-relaxed text-stone-400">
                Generating saves the invoice on this device and emails the PDF to {settings.ownerEmail}
                {form.sendToTenant ? ' and the tenant.' : '.'}
              </p>
            </div>
          </div>
        </div>
      </div>

      <Dialog open={previewOpen} onOpenChange={setPreviewOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto bg-stone-100">
          <DialogHeader>
            <DialogTitle className="font-heading">Invoice Preview</DialogTitle>
          </DialogHeader>
          <InvoicePreview invoice={currentInvoice()} settings={settings} />
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={handlePrint} data-testid="preview-print-btn" className="border-stone-200 bg-white"><Printer className="mr-2 h-4 w-4" /> Print</Button>
            <Button onClick={handleDownload} data-testid="preview-download-btn" className="bg-terracotta-500 text-white hover:bg-terracotta-600"><Download className="mr-2 h-4 w-4" /> Download PDF</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
