import { useCallback, useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { ArrowLeft, Plus, Download, Mail, Eye, Loader2, RotateCcw } from 'lucide-react';
import { toast } from 'sonner';
import { fetchInvoice, removePayment, fetchPaymentReceipt, deliverInvoiceEmail } from '../lib/api';
import { buildInvoicePDF, downloadPDF } from '../lib/pdf';
import { downloadPaymentReceipt } from '../lib/receipt';
import { notifyInvoiceEmail } from '../lib/emailStatus';
import { inr } from '../lib/format';
import { useSettings } from '../context/SettingsContext';
import { PaymentForm } from '../components/PaymentForm';
import { PaymentHistory } from '../components/PaymentHistory';
import InvoicePreview from '../components/InvoicePreview';
import { Button } from '../components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { AlertDialog, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction } from '../components/ui/alert-dialog';

export default function InvoiceDetails() {
  const { id } = useParams();
  const [search, setSearch] = useSearchParams();
  const { settings } = useSettings();
  const [invoice, setInvoice] = useState(null);
  const [error, setError] = useState('');
  const [formOpen, setFormOpen] = useState(search.get('record') === '1');
  const [editing, setEditing] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [busy, setBusy] = useState(false);
  const [emailing, setEmailing] = useState(false);
  const [preview, setPreview] = useState(false);
  const load = useCallback(async () => {
    try { setInvoice(await fetchInvoice(id)); setError(''); }
    catch (e) { setError(e.message); }
  }, [id]);
  useEffect(() => { load(); }, [load]);
  const closeForm = () => { setFormOpen(false); setEditing(null); setSearch({}, { replace: true }); };
  const saved = () => { closeForm(); load(); };
  const deletePayment = async () => {
    setBusy(true);
    try { await removePayment(deleting.id); setDeleting(null); await load(); toast.success('Payment deleted'); }
    catch (e) { toast.error(e.message); }
    finally { setBusy(false); }
  };
  const receipt = async (p) => {
    try { downloadPaymentReceipt(await fetchPaymentReceipt(p.id), settings); }
    catch (e) { toast.error(e.message); }
  };
  const email = async () => {
    setEmailing(true);
    try { notifyInvoiceEmail(await deliverInvoiceEmail(invoice, settings)); }
    catch (e) { toast.error(e.message); }
    finally { await load(); setEmailing(false); }
  };
  if (error) return <div role="alert" data-testid="invoice-details-error" className="space-y-4 text-red-700">{error}<Button onClick={load} variant="outline" data-testid="invoice-details-retry">Retry</Button></div>;
  if (!invoice) return <p role="status" data-testid="invoice-details-loading">Loading invoice…</p>;
  const emailFailed = invoice.emailStatus?.owner === 'failed' || invoice.emailStatus?.tenant === 'failed';
  return (
    <div className="min-w-0 space-y-8" data-testid="invoice-details-page">
      <Link to="/history" className="inline-flex items-center gap-2 text-sm text-stone-600" data-testid="invoice-details-back"><ArrowLeft className="h-4 w-4" />Invoice History</Link>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0"><h1 className="break-words font-heading text-3xl font-extrabold sm:text-4xl" data-testid="invoice-details-number">{invoice.invoiceNumber}</h1><p className="mt-2 break-words text-stone-600" data-testid="invoice-details-tenant">{invoice.tenantName}</p></div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setPreview(true)} data-testid="invoice-details-preview"><Eye className="mr-2 h-4 w-4" />Preview</Button>
          <Button variant="outline" onClick={() => downloadPDF(buildInvoicePDF(invoice, settings), invoice)} data-testid="invoice-details-download"><Download className="mr-2 h-4 w-4" />Invoice PDF</Button>
          <Button variant="outline" onClick={email} disabled={emailing} data-testid="invoice-details-email">{emailing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : emailFailed ? <RotateCcw className="mr-2 h-4 w-4" /> : <Mail className="mr-2 h-4 w-4" />}{emailFailed ? 'Retry Email' : 'Email Invoice'}</Button>
        </div>
      </header>
      <section className="space-y-4" data-testid="payment-summary">
        <div className="flex flex-wrap items-center justify-between gap-3"><h2 className="font-heading text-lg font-bold">Payment Summary</h2><Button disabled={invoice.balanceDue <= 0} onClick={() => setFormOpen(true)} data-testid="record-payment-button" className="bg-terracotta-500 text-white hover:bg-terracotta-600"><Plus className="mr-2 h-4 w-4" />Record Payment</Button></div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[['Invoice Total', inr(invoice.total), 'invoice-total'], ['Total Paid', inr(invoice.amountPaid), 'invoice-paid'], ['Balance Due', inr(invoice.balanceDue), 'invoice-balance'], ['Status', invoice.payment_status, 'invoice-payment-status']].map(([label, value, tid]) => (
            <div key={tid} className="min-w-0 rounded-lg border border-stone-200 bg-white p-5"><div className="text-xs font-semibold uppercase text-stone-500">{label}</div><div data-testid={tid} className={`mt-3 break-words font-heading font-bold ${tid === 'invoice-payment-status' ? 'text-base' : 'text-2xl'}`}>{value}</div></div>
          ))}
        </div>
        {invoice.creditBalance > 0 && <p className="text-sm text-green-700" data-testid="invoice-credit-balance">Existing advance / credit: {inr(invoice.creditBalance)}</p>}
      </section>
      <PaymentHistory payments={invoice.payments || []} onEdit={(p) => { setEditing(p); setFormOpen(true); }} onDelete={setDeleting} onReceipt={receipt} />
      <section className="space-y-2 border-t border-stone-200 pt-5 text-sm" data-testid="invoice-details-email-status">
        <h2 className="font-heading text-lg font-bold">Email recipients</h2>
        <p className="break-words" data-testid="invoice-details-email-to">To: {settings.ownerEmail}</p><p className="break-words" data-testid="invoice-details-email-cc">Tenant CC: {invoice.tenantEmail || 'No email provided'}</p>
        <p data-testid="invoice-details-email-result">Owner: {invoice.emailStatus?.owner || 'Not sent'} · Tenant CC: {invoice.emailStatus?.tenant || 'Not sent'}</p>
      </section>
      {formOpen && <PaymentForm invoice={invoice} payment={editing} onClose={closeForm} onSaved={saved} />}
      <AlertDialog open={!!deleting} onOpenChange={(o) => { if (!o && !busy) setDeleting(null); }}><AlertDialogContent data-testid="delete-payment-dialog" className="bg-white"><AlertDialogHeader><AlertDialogTitle>Delete this payment?</AlertDialogTitle><AlertDialogDescription>The payment of {inr(deleting?.amount)} will be removed. The invoice amount stays unchanged.</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel disabled={busy} data-testid="delete-payment-cancel">Cancel</AlertDialogCancel><AlertDialogAction disabled={busy} onClick={(e) => { e.preventDefault(); deletePayment(); }} data-testid="delete-payment-confirm" className="bg-red-600 text-white">{busy ? 'Deleting…' : 'Delete Payment'}</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
      <Dialog open={preview} onOpenChange={setPreview}><DialogContent data-testid="invoice-details-preview-dialog" className="max-h-[90vh] max-w-3xl overflow-y-auto bg-stone-100"><DialogHeader><DialogTitle>Invoice Preview</DialogTitle></DialogHeader><InvoicePreview invoice={invoice} settings={settings} /></DialogContent></Dialog>
    </div>
  );
}