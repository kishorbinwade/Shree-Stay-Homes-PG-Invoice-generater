import { inr, fmtDate, monthLabel } from '../lib/format';

function Row({ label, value, bold, accent, danger }) {
  return (
    <div className="flex justify-between py-1 text-sm">
      <span className="text-stone-500">{label}</span>
      <span className={`${bold ? 'font-bold' : 'font-medium'} ${accent ? 'text-terracotta-600 text-base' : danger ? 'text-red-600' : 'text-stone-900'}`}>
        {value}
      </span>
    </div>
  );
}

export default function InvoicePreview({ invoice: inv, settings: s }) {
  const charges = [
    ['Monthly Rent', inv.rent, true],
    ['Security Deposit', inv.securityDeposit],
    ['Electricity Charges', inv.electricity],
    ['Food / Meal Charges', inv.food],
    ['Maintenance Charges', inv.maintenance],
    ['Other Charges', inv.otherCharges],
    ['Previous Balance', inv.previousBalance],
  ].filter(([, v, force]) => force || Number(v));

  return (
    <div data-testid="invoice-preview" className="relative bg-white text-stone-900 overflow-hidden rounded-lg border border-stone-200">
      <div className="pointer-events-none absolute inset-0 flex items-center justify-center overflow-hidden">
        <span className="rotate-[32deg] whitespace-nowrap font-heading text-4xl font-extrabold text-stone-900/[0.05] select-none">
          {s.watermarkText || s.businessName}
        </span>
      </div>
      <div className="relative p-6 sm:p-8">
        <div className="flex flex-wrap justify-between gap-4">
          <div className="flex gap-3">
            {s.logo && <img src={s.logo} alt="logo" className="h-14 w-14 rounded-md object-cover border border-stone-200" />}
            <div>
              <div className="font-heading text-lg font-extrabold tracking-tight">{s.businessName}</div>
              <div className="text-xs text-stone-500">{s.subtitle}</div>
              {s.address && <div className="mt-1 text-xs text-stone-500 whitespace-pre-line">{s.address}</div>}
              <div className="text-xs text-stone-500">
                {[s.mobile && `Ph: ${s.mobile}`, s.email].filter(Boolean).join('  |  ')}
              </div>
              {s.gstin && <div className="text-xs text-stone-500">GSTIN: {s.gstin}</div>}
            </div>
          </div>
          <div className="text-right">
            <div className="font-heading text-2xl font-extrabold text-terracotta-500">INVOICE</div>
            <div className="mt-1 space-y-0.5 text-xs">
              <div><span className="text-stone-500">Invoice No: </span><span className="font-semibold">{inv.invoiceNumber}</span></div>
              <div><span className="text-stone-500">Invoice Date: </span><span className="font-semibold">{fmtDate(inv.invoiceDate)}</span></div>
              <div><span className="text-stone-500">Billing Month: </span><span className="font-semibold">{monthLabel(inv.billingMonth)}</span></div>
              <div><span className="text-stone-500">Due Date: </span><span className="font-semibold">{fmtDate(inv.dueDate)}</span></div>
            </div>
          </div>
        </div>

        <hr className="my-4 border-stone-200" />

        <div className="text-[11px] font-semibold uppercase tracking-wider text-terracotta-600">Billed To</div>
        <div className="mt-1 text-sm font-bold">{inv.tenantName}</div>
        <div className="text-xs text-stone-500">
          {[inv.tenantEmail, inv.tenantMobile && `Ph: ${inv.tenantMobile}`].filter(Boolean).join('  |  ')}
        </div>
        <div className="text-xs text-stone-500">Room {inv.roomNumber || '-'} / Bed {inv.bedNumber || '-'}</div>
        {inv.checkIn && (
          <div className="text-xs text-stone-500">Stay: {fmtDate(inv.checkIn)} to {inv.checkOut ? fmtDate(inv.checkOut) : 'Present'}</div>
        )}

        <table className="mt-4 w-full text-sm">
          <thead>
            <tr className="border-b border-stone-300 text-left text-[11px] uppercase tracking-wider text-stone-500">
              <th className="py-1.5 w-8">#</th>
              <th className="py-1.5">Description</th>
              <th className="py-1.5 text-right">Amount</th>
            </tr>
          </thead>
          <tbody>
            {charges.map(([label, val], i) => (
              <tr key={label} className="border-b border-stone-100">
                <td className="py-2 text-stone-400">{i + 1}</td>
                <td className="py-2">{label}</td>
                <td className="py-2 text-right font-medium">{inr(val)}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="mt-4 flex flex-col gap-1 sm:ml-auto sm:w-64">
          <Row label="Subtotal" value={inr(inv.subtotal)} />
          <Row label="Discount" value={Number(inv.discount) ? `- ${inr(inv.discount)}` : inr(0)} />
          <div className="border-t border-stone-200 pt-1">
            <Row label="Total Amount" value={inr(inv.total)} bold accent />
          </div>
          <Row label="Amount Paid" value={inr(inv.amountPaid)} />
          <Row
            label={Number(inv.balanceDue) < 0 ? 'Advance / Credit' : 'Balance Due'}
            value={inr(Math.abs(Number(inv.balanceDue) || 0))}
            bold
            danger={Number(inv.balanceDue) > 0}
          />
        </div>

        <div className="mt-4 text-xs text-stone-500">
          Status: <span className="font-semibold text-stone-800">{inv.paymentStatus}</span>
          {'  |  '}Mode: <span className="font-semibold text-stone-800">{inv.paymentMode || '—'}</span>
          {inv.transactionId && <>  |  Txn: <span className="font-semibold text-stone-800">{inv.transactionId}</span></>}
        </div>

        <div className="mt-8 flex items-end justify-between">
          <div className="max-w-[55%] text-[11px] text-stone-400">
            {s.paymentTerms && <div>Terms: {s.paymentTerms}</div>}
            {s.notes && <div className="mt-1">Note: {s.notes}</div>}
          </div>
          <div className="text-center">
            {s.signature && <img src={s.signature} alt="signature" className="mx-auto h-10 object-contain" />}
            <div className="mt-1 w-40 border-t border-stone-400 pt-1 text-[11px] text-stone-500">Authorized Signature</div>
          </div>
        </div>

        <div className="mt-6 border-t border-stone-200 pt-2 text-center text-[10px] text-stone-400">
          This invoice is generated by Shree Stay Homes & PG.
        </div>
      </div>
    </div>
  );
}
