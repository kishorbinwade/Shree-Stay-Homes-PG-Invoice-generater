import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { FileUp, Loader2, CheckCircle2, AlertTriangle, XCircle, Upload } from 'lucide-react';
import { previewImport, commitImport, fetchImports } from '../lib/api';
import { fmtDate } from '../lib/format';
import { Button } from '../components/ui/button';

const FIELD_LABELS = {
  name: 'Full Name', mobile: 'Mobile', email: 'Email', emergencyContact: 'Emergency Contact',
  emergencyContactRelationship: 'Emergency Relationship', occupation: 'Occupation', company: 'Company',
  permanentAddress: 'Permanent Address', idType: 'ID Type', idNumber: 'ID Number',
  dateOfBirth: 'Date of Birth', joiningDate: 'Joining Date', roomNumber: 'Room Number',
  bedNumber: 'Bed Number', rent: 'Monthly Rent', deposit: 'Security Deposit',
};

function StatusBadge({ status }) {
  const map = {
    new: ['bg-green-50 text-green-700', 'New'],
    duplicate: ['bg-amber-50 text-amber-700', 'Duplicate'],
    invalid: ['bg-red-50 text-red-700', 'Invalid'],
  };
  const [cls, label] = map[status] || map.new;
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>{label}</span>;
}

export default function ImportCSV() {
  const fileRef = useRef(null);
  const [file, setFile] = useState(null);
  const [csvText, setCsvText] = useState('');
  const [preview, setPreview] = useState(null);
  const [mapping, setMapping] = useState({});
  const [decisions, setDecisions] = useState({});
  const [busy, setBusy] = useState('');
  const [history, setHistory] = useState([]);

  const loadHistory = () => fetchImports().then(setHistory).catch(() => {});
  useEffect(() => { loadHistory(); }, []);

  const handleFile = async (e) => {
    const f = e.target.files?.[0];
    e.target.value = '';
    if (!f) return;
    const text = await f.text();
    setFile(f);
    setCsvText(text);
    setBusy('preview');
    try {
      const p = await previewImport(f.name, text);
      setPreview(p);
      setMapping(p.mapping);
      const d = {};
      p.rows.forEach((r) => { if (r.status === 'duplicate') d[String(r.rowIndex)] = 'skip'; });
      setDecisions(d);
    } catch (err) {
      toast.error(err.message || 'Could not parse CSV');
      setPreview(null);
    } finally {
      setBusy('');
    }
  };

  const handleImport = async () => {
    setBusy('import');
    try {
      const res = await commitImport({ filename: file.name, csvText, mapping, decisions });
      toast.success(`Imported ${res.imported} tenant(s) — ${res.duplicates} updated, ${res.skipped} skipped, ${res.invalid} invalid`);
      setPreview(null);
      setFile(null);
      loadHistory();
    } catch (err) {
      toast.error(err.message || 'Import failed');
    } finally {
      setBusy('');
    }
  };

  return (
    <div data-testid="import-page" className="space-y-6">
      <div>
        <h1 className="font-heading text-3xl font-extrabold tracking-tight text-stone-900 sm:text-4xl">Import Google Forms CSV</h1>
        <p className="mt-1 text-sm text-stone-600">
          Download your Google Form responses as CSV (Responses → ⋮ → Download responses) and import the file here.
          No Google API needed — the file never leaves this computer.
        </p>
      </div>

      <div className="rounded-xl border border-[#E6E4E0] bg-white p-6 shadow-sm">
        <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={handleFile} data-testid="import-file-input" />
        <Button onClick={() => fileRef.current?.click()} disabled={!!busy} data-testid="import-choose-btn" className="bg-terracotta-500 text-white hover:bg-terracotta-600">
          {busy === 'preview' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileUp className="mr-2 h-4 w-4" />}
          Choose CSV File
        </Button>
        {file && <span className="ml-3 text-sm text-stone-600">{file.name}</span>}
      </div>

      {preview && (
        <>
          <div className="rounded-xl border border-[#E6E4E0] bg-white p-5 shadow-sm" data-testid="import-preview-summary">
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
              <span className="font-semibold text-stone-900">{preview.filename}</span>
              <span data-testid="import-summary-total">{preview.summary.total} records found</span>
              <span className="flex items-center gap-1 text-green-700"><CheckCircle2 className="h-4 w-4" /> <span data-testid="import-summary-new">{preview.summary.new} new tenants</span></span>
              <span className="flex items-center gap-1 text-amber-700"><AlertTriangle className="h-4 w-4" /> <span data-testid="import-summary-duplicates">{preview.summary.duplicates} duplicate(s)</span></span>
              <span className="flex items-center gap-1 text-red-600"><XCircle className="h-4 w-4" /> <span data-testid="import-summary-invalid">{preview.summary.invalid} invalid</span></span>
            </div>
          </div>

          <div className="rounded-xl border border-[#E6E4E0] bg-white p-5 shadow-sm">
            <h2 className="font-heading text-base font-bold text-stone-900">Column Mapping</h2>
            <p className="text-xs text-stone-500">Auto-mapped from common Google Form questions. Adjust or skip any column.</p>
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {preview.columns.map((col, idx) => (
                <div key={idx} className="flex items-center justify-between gap-2 rounded-md border border-stone-100 bg-[#FDFCFB] px-3 py-2">
                  <span className="truncate text-xs font-medium text-stone-700" title={col}>{col}</span>
                  <select
                    value={mapping[String(idx)] || ''}
                    onChange={(e) => setMapping((m) => { const n = { ...m }; if (e.target.value) n[String(idx)] = e.target.value; else delete n[String(idx)]; return n; })}
                    data-testid={`import-mapping-${idx}`}
                    className="w-36 rounded border border-stone-200 bg-white px-1.5 py-1 text-xs"
                  >
                    <option value="">Skip</option>
                    {preview.importableFields.map((f) => <option key={f} value={f}>{FIELD_LABELS[f]}</option>)}
                  </select>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-[#E6E4E0] bg-white shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="import-preview-table">
                <thead>
                  <tr className="border-b border-stone-200 text-left text-xs uppercase tracking-wider text-stone-500">
                    <th className="px-4 py-2.5">#</th><th className="px-4 py-2.5">Name</th>
                    <th className="px-4 py-2.5">Mobile</th><th className="px-4 py-2.5">Room</th>
                    <th className="px-4 py-2.5">Rent</th><th className="px-4 py-2.5">Status</th>
                    <th className="px-4 py-2.5">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((r) => (
                    <tr key={r.rowIndex} className="border-b border-stone-100 align-top" data-testid={`import-row-${r.rowIndex}`}>
                      <td className="px-4 py-2.5 text-stone-400">{r.rowIndex + 1}</td>
                      <td className="px-4 py-2.5 font-medium text-stone-900">{r.data.name || '—'}</td>
                      <td className="px-4 py-2.5 text-stone-600">{r.data.mobile || '—'}</td>
                      <td className="px-4 py-2.5 text-stone-600">{r.data.roomNumber || '—'}</td>
                      <td className="px-4 py-2.5 text-stone-600">{r.data.rent || '—'}</td>
                      <td className="px-4 py-2.5"><StatusBadge status={r.status} /></td>
                      <td className="px-4 py-2.5">
                        {r.status === 'duplicate' && (
                          <div className="space-y-1.5">
                            <div className="text-xs text-stone-500">Already exists: {r.existing.name} ({r.existing.mobile || 'no mobile'})</div>
                            <label className="flex items-center gap-1.5 text-xs">
                              <input type="radio" checked={(decisions[String(r.rowIndex)] || 'skip') === 'skip'}
                                onChange={() => setDecisions((d) => ({ ...d, [String(r.rowIndex)]: 'skip' }))}
                                data-testid={`import-decision-skip-${r.rowIndex}`} /> Skip
                            </label>
                            <label className="flex items-center gap-1.5 text-xs">
                              <input type="radio" checked={decisions[String(r.rowIndex)] === 'update'}
                                onChange={() => setDecisions((d) => ({ ...d, [String(r.rowIndex)]: 'update' }))}
                                data-testid={`import-decision-update-${r.rowIndex}`} /> Update Existing Tenant
                            </label>
                            {decisions[String(r.rowIndex)] === 'update' && (
                              <div className="rounded bg-amber-50 p-2 text-[11px] text-amber-800" data-testid={`import-changes-${r.rowIndex}`}>
                                {Object.keys(r.changes || {}).length === 0
                                  ? 'No field changes — incoming data matches.'
                                  : Object.entries(r.changes).map(([f, c]) => (
                                    <div key={f}>{FIELD_LABELS[f] || f}: “{String(c.from) || '—'}” → “{String(c.to)}”</div>
                                  ))}
                              </div>
                            )}
                          </div>
                        )}
                        {r.status === 'invalid' && <span className="text-xs text-red-600">{(r.errors || []).join(', ')}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex justify-end gap-2 border-t border-stone-200 p-4">
              <Button variant="outline" onClick={() => { setPreview(null); setFile(null); }} data-testid="import-cancel-btn" className="border-stone-200">Cancel</Button>
              <Button onClick={handleImport} disabled={busy === 'import'} data-testid="import-commit-btn" className="bg-terracotta-500 text-white hover:bg-terracotta-600">
                {busy === 'import' ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Upload className="mr-2 h-4 w-4" />}
                Import Valid Records
              </Button>
            </div>
          </div>
        </>
      )}

      <div className="rounded-xl border border-[#E6E4E0] bg-white shadow-sm">
        <div className="border-b border-stone-200 px-5 py-3 text-sm font-semibold text-stone-800">Import History</div>
        {history.length === 0 ? (
          <div className="py-12 text-center text-sm text-stone-400" data-testid="import-history-empty">No imports yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="import-history-table">
              <thead>
                <tr className="border-b border-stone-200 text-left text-xs uppercase tracking-wider text-stone-500">
                  <th className="px-4 py-2.5">Date</th><th className="px-4 py-2.5">File</th>
                  <th className="px-4 py-2.5 text-right">Rows</th><th className="px-4 py-2.5 text-right">Imported</th>
                  <th className="px-4 py-2.5 text-right">Duplicates</th><th className="px-4 py-2.5 text-right">Invalid</th>
                  <th className="px-4 py-2.5 text-right">Skipped</th><th className="px-4 py-2.5">Details</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.id} className="border-b border-stone-100" data-testid={`import-history-${h.id}`}>
                    <td className="px-4 py-2.5 text-stone-600">{fmtDate((h.importedAt || '').slice(0, 10))}</td>
                    <td className="px-4 py-2.5 font-medium text-stone-900">{h.filename}</td>
                    <td className="px-4 py-2.5 text-right">{h.totalRows}</td>
                    <td className="px-4 py-2.5 text-right text-green-700">{h.imported}</td>
                    <td className="px-4 py-2.5 text-right text-amber-700">{h.duplicates}</td>
                    <td className="px-4 py-2.5 text-right text-red-600">{h.invalid}</td>
                    <td className="px-4 py-2.5 text-right text-stone-500">{h.skipped}</td>
                    <td className="px-4 py-2.5">
                      <details className="text-xs text-stone-500">
                        <summary className="cursor-pointer text-terracotta-600" data-testid={`import-details-${h.id}`}>View</summary>
                        <div className="mt-1 space-y-0.5">
                          {(h.details || []).map((d) => <div key={d.row}>Row {d.row}: {d.name} — {d.result}{d.fields?.length ? ` (${d.fields.join(', ')})` : ''}</div>)}
                        </div>
                      </details>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
