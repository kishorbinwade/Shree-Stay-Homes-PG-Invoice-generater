import { useRef, useState } from 'react';
import { toast } from 'sonner';
import { Download, Upload, Trash2, Loader2, ShieldAlert, DatabaseBackup } from 'lucide-react';
import { exportAllData, importAllData, clearAllData } from '../lib/db';
import { exportInvoicesCSV, downloadFile } from '../lib/backup';
import { Button } from '../components/ui/button';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../components/ui/alert-dialog';

export default function Backup() {
  const fileRef = useRef(null);
  const [busy, setBusy] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);

  const handleExportJSON = async () => {
    setBusy('json');
    try {
      const data = await exportAllData();
      downloadFile(JSON.stringify(data, null, 2), `ShreeStayHomesPG_Backup_${new Date().toISOString().slice(0, 10)}.json`, 'application/json');
      toast.success(`Backup exported (${data.invoices.length} invoices, ${data.tenants.length} tenants)`);
    } catch (e) {
      toast.error('Export failed');
    } finally {
      setBusy('');
    }
  };

  const handleExportCSV = async () => {
    setBusy('csv');
    try {
      const count = await exportInvoicesCSV();
      toast.success(`CSV exported (${count} invoices)`);
    } catch (e) {
      toast.error('Export failed');
    } finally {
      setBusy('');
    }
  };

  const handleImport = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setBusy('import');
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      const res = await importAllData(data);
      toast.success(`Restored ${res.invoices} invoices and ${res.tenants} tenants`);
    } catch (err) {
      toast.error('Import failed — please select a valid backup JSON file');
    } finally {
      setBusy('');
    }
  };

  const handleDeleteAll = async () => {
    setConfirmDelete(false);
    setBusy('delete');
    try {
      await clearAllData();
      toast.success('All local data deleted');
      setTimeout(() => window.location.reload(), 800);
    } catch (e) {
      toast.error('Failed to delete data');
    } finally {
      setBusy('');
    }
  };

  return (
    <div data-testid="backup-page" className="space-y-6">
      <div>
        <h1 className="font-heading text-3xl font-extrabold tracking-tight text-stone-900 sm:text-4xl">Backup &amp; Restore</h1>
        <p className="mt-1 text-sm text-stone-600">All data lives in this browser (IndexedDB). Export backups regularly.</p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="rounded-xl border border-[#E6E4E0] bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2">
            <DatabaseBackup className="h-5 w-5 text-terracotta-500" />
            <h2 className="font-heading text-lg font-bold text-stone-900">Export Backup</h2>
          </div>
          <p className="mt-1 text-sm text-stone-500">Download all invoice and tenant records stored on this device.</p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Button onClick={handleExportJSON} disabled={!!busy} data-testid="export-json-btn" className="bg-terracotta-500 text-white hover:bg-terracotta-600">
              {busy === 'json' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
              Export JSON
            </Button>
            <Button variant="outline" onClick={handleExportCSV} disabled={!!busy} data-testid="export-csv-btn" className="border-stone-200">
              {busy === 'csv' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Download className="mr-2 h-4 w-4" />}
              Export CSV (invoices)
            </Button>
          </div>
        </section>

        <section className="rounded-xl border border-[#E6E4E0] bg-white p-6 shadow-sm">
          <div className="flex items-center gap-2">
            <Upload className="h-5 w-5 text-terracotta-500" />
            <h2 className="font-heading text-lg font-bold text-stone-900">Import / Restore</h2>
          </div>
          <p className="mt-1 text-sm text-stone-500">Restore a previously exported JSON backup on this or another device. Records are merged by invoice number.</p>
          <div className="mt-4">
            <input ref={fileRef} type="file" accept="application/json,.json" className="hidden" onChange={handleImport} data-testid="import-json-input" />
            <Button variant="outline" onClick={() => fileRef.current?.click()} disabled={!!busy} data-testid="import-json-btn" className="border-stone-200">
              {busy === 'import' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
              Choose Backup File
            </Button>
          </div>
        </section>
      </div>

      <section className="rounded-xl border border-red-200 bg-red-50 p-6">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-5 w-5 text-red-600" />
          <h2 className="font-heading text-lg font-bold text-red-800">Danger Zone</h2>
        </div>
        <p className="mt-2 text-sm text-red-700" data-testid="delete-warning-text">
          Deleting browser/site data may permanently remove locally stored invoices. Please create a backup before deleting data.
        </p>
        <Button variant="outline" onClick={() => setConfirmDelete(true)} disabled={!!busy} data-testid="delete-all-data-btn" className="mt-4 border-red-300 bg-white text-red-700 hover:bg-red-100">
          <Trash2 className="mr-2 h-4 w-4" /> Delete All Local Data
        </Button>
      </section>

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent className="bg-white">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete ALL local data?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently deletes every invoice, tenant record and setting stored on this device. Deleting browser/site data may permanently remove locally stored invoices. Please create a backup before deleting data.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="delete-all-cancel-btn">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteAll} data-testid="delete-all-confirm-btn" className="bg-red-600 text-white hover:bg-red-700">
              Yes, Delete Everything
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
