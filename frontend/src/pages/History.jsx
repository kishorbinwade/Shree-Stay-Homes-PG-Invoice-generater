import { useCallback, useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Search, Eye, Download, Printer, Mail, Copy, Pencil, Trash2, ArrowUpDown,
  FileText, Loader2, FilePlus2,
} from 'lucide-react';
import { fetchInvoices, removeInvoice, updateInvoice } from '../lib/api';
import { inr, fmtDate, monthLabel } from '../lib/format';
import { buildInvoicePDF, downloadPDF, printPDF } from '../lib/pdf';
import { deliverInvoiceEmail } from '../lib/api';
import { useSettings } from '../context/SettingsContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../components/ui/alert-dialog';
import InvoicePreview from '../components/InvoicePreview';

function StatusBadge({ status }) {
  const cls = status === 'Paid' ? 'bg-green-50 text-green-700' : status === 'Pending' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700';
  return <span className={`whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>{status}</span>;
}

function EmailBadge({ es }) {
  if (es?.owner === 'sent') return <span className="whitespace-nowrap rounded-full bg-green-50 px-2.5 py-0.5 text-xs font-medium text-green-700">Emailed</span>;
  if (es?.owner === 'failed') return <span className="whitespace-nowrap rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-700">Failed</span>;
  return <span className="whitespace-nowrap rounded-full bg-stone-100 px-2.5 py-0.5 text-xs font-medium text-stone-500">Not sent</span>;
}

export default function History() {
  const { settings } = useSettings();
  const navigate = useNavigate();
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState('');
  const [month, setMonth] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [sortAsc, setSortAsc] = useState(false);
  const [viewing, setViewing] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [busyId, setBusyId] = useState('');

  const reload = useCallback(
    () =>
      fetchInvoices({
        q: q.trim() || undefined,
        month: month || undefined,
        status: statusFilter,
        order: sortAsc ? 'asc' : 'desc',
      })
        .then(setInvoices)
        .catch((e) => toast.error(e.message)),
    [q, month, statusFilter, sortAsc],
  );
  useEffect(() => {
    setLoading(true);
    const t = setTimeout(() => reload().finally(() => setLoading(false)), 250);
    return () => clearTimeout(t);
  }, [reload]);

  const handleDelete = async () => {
    if (!pendingDelete) return;
    await removeInvoice(pendingDelete.id);
    toast.success(`Invoice ${pendingDelete.invoiceNumber} deleted`);
    setPendingDelete(null);
    reload();
  };

  const handleResend = async (inv) => {
    setBusyId(inv.id);
    try {
      const res = await deliverInvoiceEmail({ ...inv, sendToTenant: !!inv.sendToTenant }, settings);
      await updateInvoice(inv.id, { ...inv, emailStatus: { owner: res.owner, tenant: res.tenant, at: new Date().toISOString() } });
      if (res.owner === 'sent') toast.success(`Resent to owner (${settings.ownerEmail}) with PDF attached`);
      else toast.error(res.errors?.owner || 'Resend failed');
      if (res.tenant === 'sent') toast.success('Copy sent to tenant');
      reload();
    } catch (e) {
      toast.error(e.message || 'Resend failed');
    } finally {
      setBusyId('');
    }
  };

  const handleDownload = (inv) => downloadPDF(buildInvoicePDF(inv, settings), inv);
  const handlePrint = (inv) => printPDF(buildInvoicePDF(inv, settings));

  return (
    <div data-testid="history-page" className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-3xl font-extrabold tracking-tight text-stone-900 sm:text-4xl">Invoice History</h1>
          <p className="mt-1 text-sm text-stone-600">{invoices.length} invoices</p>
        </div>
        <Button asChild className="bg-terracotta-500 text-white hover:bg-terracotta-600">
          <Link to="/invoices/new" data-testid="history-new-invoice-btn"><FilePlus2 className="mr-2 h-4 w-4" /> New Invoice</Link>
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-xl border border-[#E6E4E0] bg-white p-4 shadow-sm">
        <div className="relative min-w-56 flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search tenant or invoice number…" data-testid="history-search" className="border-[#E6E4E0] bg-[#FDFCFB] pl-9" />
        </div>
        <Input type="month" value={month} onChange={(e) => setMonth(e.target.value)} data-testid="history-month-filter" className="w-44 border-[#E6E4E0] bg-[#FDFCFB]" />
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger data-testid="history-status-filter" className="w-40 border-[#E6E4E0] bg-[#FDFCFB]"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="Paid">Paid</SelectItem>
            <SelectItem value="Partially Paid">Partially Paid</SelectItem>
            <SelectItem value="Pending">Pending</SelectItem>
          </SelectContent>
        </Select>
        <Button variant="outline" onClick={() => setSortAsc((s) => !s)} data-testid="history-sort-btn" className="border-stone-200">
          <ArrowUpDown className="mr-2 h-4 w-4" /> {sortAsc ? 'Oldest first' : 'Newest first'}
        </Button>
      </div>

      <div className="rounded-xl border border-[#E6E4E0] bg-white shadow-sm">
        {loading ? (
          <div className="py-24 text-center text-sm text-stone-400" data-testid="history-loading">Loading invoices…</div>
        ) : invoices.length === 0 ? (
          <div className="flex flex-col items-center py-24 text-center" data-testid="history-empty-state">
            <FileText className="h-12 w-12 text-stone-300" />
            <p className="mt-3 text-sm text-stone-500">No invoices found. Create one or adjust your filters.</p>
            <Button asChild className="mt-4 bg-terracotta-500 text-white hover:bg-terracotta-600">
              <Link to="/invoices/new" data-testid="history-create-first-btn">Create First Invoice</Link>
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="history-table">
              <thead>
                <tr className="border-b border-stone-200 text-left text-xs uppercase tracking-wider text-stone-500">
                  <th className="px-4 py-3">Invoice No</th>
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Tenant</th>
                  <th className="px-4 py-3">Room/Bed</th>
                  <th className="px-4 py-3">Month</th>
                  <th className="px-4 py-3 text-right">Total</th>
                  <th className="px-4 py-3 text-right">Paid</th>
                  <th className="px-4 py-3 text-right">Balance</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <tr key={inv.id} className="border-b border-stone-100 transition-colors duration-150 hover:bg-stone-50" data-testid={`history-row-${inv.invoiceNumber}`}>
                    <td className="px-4 py-3 font-semibold text-stone-900">{inv.invoiceNumber}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-stone-600">{fmtDate(inv.invoiceDate)}</td>
                    <td className="px-4 py-3 text-stone-900">{inv.tenantName}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-stone-600">{inv.roomNumber || '-'}/{inv.bedNumber || '-'}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-stone-600">{monthLabel(inv.billingMonth)}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-right font-medium">{inr(inv.total)}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-green-700">{inr(inv.amountPaid)}</td>
                    <td className={`whitespace-nowrap px-4 py-3 text-right font-medium ${Number(inv.balanceDue) > 0 ? 'text-red-600' : 'text-stone-500'}`}>{inr(Math.max(Number(inv.balanceDue) || 0, 0))}</td>
                    <td className="px-4 py-3"><StatusBadge status={inv.paymentStatus} /></td>
                    <td className="px-4 py-3"><EmailBadge es={inv.emailStatus} /></td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="icon" title="View" onClick={() => setViewing(inv)} data-testid={`view-invoice-${inv.invoiceNumber}`}><Eye className="h-4 w-4 text-stone-500" /></Button>
                        <Button variant="ghost" size="icon" title="Download PDF" onClick={() => handleDownload(inv)} data-testid={`download-invoice-${inv.invoiceNumber}`}><Download className="h-4 w-4 text-stone-500" /></Button>
                        <Button variant="ghost" size="icon" title="Print" onClick={() => handlePrint(inv)} data-testid={`print-invoice-${inv.invoiceNumber}`}><Printer className="h-4 w-4 text-stone-500" /></Button>
                        <Button variant="ghost" size="icon" title="Resend Email" disabled={busyId === inv.id} onClick={() => handleResend(inv)} data-testid={`resend-invoice-${inv.invoiceNumber}`}>
                          {busyId === inv.id ? <Loader2 className="h-4 w-4 animate-spin text-stone-500" /> : <Mail className="h-4 w-4 text-stone-500" />}
                        </Button>
                        <Button variant="ghost" size="icon" title="Duplicate" onClick={() => navigate(`/invoices/new?from=${inv.id}`)} data-testid={`duplicate-invoice-${inv.invoiceNumber}`}><Copy className="h-4 w-4 text-stone-500" /></Button>
                        <Button variant="ghost" size="icon" title="Edit" onClick={() => navigate(`/invoices/${inv.id}/edit`)} data-testid={`edit-invoice-${inv.invoiceNumber}`}><Pencil className="h-4 w-4 text-stone-500" /></Button>
                        <Button variant="ghost" size="icon" title="Delete" onClick={() => setPendingDelete(inv)} data-testid={`delete-invoice-${inv.invoiceNumber}`}><Trash2 className="h-4 w-4 text-red-500" /></Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Dialog open={!!viewing} onOpenChange={(o) => !o && setViewing(null)}>
        <DialogContent className="max-h-[90vh] max-w-3xl overflow-y-auto bg-stone-100">
          <DialogHeader><DialogTitle className="font-heading">Invoice {viewing?.invoiceNumber}</DialogTitle></DialogHeader>
          {viewing && <InvoicePreview invoice={viewing} settings={settings} />}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => viewing && handlePrint(viewing)} data-testid="history-view-print-btn" className="border-stone-200 bg-white"><Printer className="mr-2 h-4 w-4" /> Print</Button>
            <Button onClick={() => viewing && handleDownload(viewing)} data-testid="history-view-download-btn" className="bg-terracotta-500 text-white hover:bg-terracotta-600"><Download className="mr-2 h-4 w-4" /> Download PDF</Button>
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!pendingDelete} onOpenChange={(o) => !o && setPendingDelete(null)}>
        <AlertDialogContent className="bg-white">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete invoice {pendingDelete?.invoiceNumber}?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the invoice from this device. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="delete-cancel-btn">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} data-testid="delete-confirm-btn" className="bg-red-600 text-white hover:bg-red-700">Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
