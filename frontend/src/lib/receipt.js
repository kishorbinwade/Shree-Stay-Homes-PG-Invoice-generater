import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';
import { registerPdfFonts } from '../fonts/pdfFonts';
import { fmtDate, inrPlain } from './format';

export function buildPaymentReceipt(data, settings) {
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  const font = registerPdfFonts(doc) ? 'PdfFont' : 'helvetica';
  const { payment } = data;
  doc.setFont(font, 'bold');
  doc.setFontSize(17);
  doc.text(doc.splitTextToSize(settings.businessName || 'Shree Stay Homes & PG', 180), 14, 22);
  doc.setFontSize(14);
  doc.setTextColor(216, 92, 64);
  doc.text('PAYMENT RECEIPT', 14, 40);
  const body = [
    ['Receipt No', payment.receiptNumber], ['Invoice No', data.invoiceNumber],
    ['Tenant', data.tenantName], ['Payment Date', fmtDate(payment.paymentDate)],
    ['Invoice Amount', inrPlain(data.invoice_total)], ['Previous Paid', inrPlain(data.previousPaid)],
    ['Current Payment', inrPlain(payment.amount)], ['Total Paid', inrPlain(data.total_paid)],
    ['Balance Due', inrPlain(data.balance_due)], ['Payment Method', payment.paymentMethod],
    ['Reference', payment.reference || '—'], ['Status', data.payment_status],
    ['Notes', payment.notes || '—'],
  ];
  if (payment.dateInferred) body.push(['Payment date source', 'Inferred from legacy invoice; actual payment date was not recorded.']);
  autoTable(doc, { startY: 49, margin: { left: 14, right: 14, bottom: 24 }, body,
    styles: { font, fontSize: 10, cellPadding: 3.8, overflow: 'linebreak', textColor: [28, 27, 26] },
    columnStyles: { 0: { cellWidth: 53, fontStyle: 'bold' }, 1: { cellWidth: 129 } }, theme: 'striped' });
  for (let i = 1; i <= doc.getNumberOfPages(); i++) {
    doc.setPage(i);
    doc.saveGraphicsState();
    doc.setGState(new doc.GState({ opacity: 0.045 }));
    doc.setFontSize(36);
    doc.text('PAYMENT RECEIPT', 105, 174, { align: 'center', angle: 32 });
    doc.restoreGraphicsState();
    doc.setFont(font, 'normal');
    doc.setFontSize(8);
    doc.setTextColor(100, 100, 100);
    doc.text('Payment acknowledgement only — not a new invoice.', 14, 286);
  }
  return doc;
}

export function downloadPaymentReceipt(data, settings) {
  buildPaymentReceipt(data, settings).save(`ShreeStayHomesPG_Receipt_${data.payment.receiptNumber}.pdf`);
}