import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';
import { registerPdfFonts } from '../fonts/pdfFonts';
import { inrPlain, fmtDate, monthLabel } from './format';

const TERRA = [216, 92, 64];
const DARK = [28, 27, 26];
const GRAY = [92, 90, 87];
const LINE = [230, 228, 224];
const GREEN = [58, 125, 68];
const RED = [217, 56, 56];

export function buildInvoicePDF(inv, s) {
  const doc = new jsPDF({ unit: 'mm', format: 'a4' });
  const fontOk = registerPdfFonts(doc);
  const money = (n) =>
    fontOk
      ? inrPlain(n)
      : 'Rs. ' + new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2 }).format(Number(n) || 0);
  const F = (style) => {
    try {
      doc.setFont(fontOk ? 'PdfFont' : 'helvetica', fontOk && style === 'bold' ? 'bold' : style === 'bold' ? 'bold' : 'normal');
    } catch (e) {
      doc.setFont('helvetica', 'normal');
    }
  };

  let y = 16;
  const x = 14;

  if (s.logo) {
    try {
      doc.addImage(s.logo, 'PNG', x, y - 3, 20, 20);
    } catch (e) {
      try { doc.addImage(s.logo, 'JPEG', x, y - 3, 20, 20); } catch (e2) { /* skip */ }
    }
  }
  const bx = s.logo ? x + 26 : x;

  F('bold');
  doc.setFontSize(15);
  doc.setTextColor(...DARK);
  doc.text(String(s.businessName || 'SHREE STAY HOMES & PG'), bx, y + 3);
  F('normal');
  doc.setFontSize(9);
  doc.setTextColor(...GRAY);
  doc.text(String(s.subtitle || 'PG Accommodation & Stay Services'), bx, y + 9);

  let ay = y + 15;
  const contactLines = [
    s.address,
    [s.mobile && `Ph: ${s.mobile}`, s.email].filter(Boolean).join('   |   '),
    s.gstin && `GSTIN: ${s.gstin}`,
  ].filter(Boolean);
  contactLines.forEach((l) => {
    doc.text(String(l), bx, ay);
    ay += 4.5;
  });

  F('bold');
  doc.setFontSize(20);
  doc.setTextColor(...TERRA);
  doc.text('INVOICE', 196, y + 1, { align: 'right' });
  const meta = [
    ['Invoice No:', inv.invoiceNumber],
    ['Invoice Date:', fmtDate(inv.invoiceDate)],
    ['Billing Month:', monthLabel(inv.billingMonth)],
    ['Due Date:', fmtDate(inv.dueDate)],
  ];
  let my = y + 8;
  meta.forEach(([k, v]) => {
    F('normal');
    doc.setFontSize(9);
    doc.setTextColor(...GRAY);
    doc.text(k, 148, my);
    F('bold');
    doc.setTextColor(...DARK);
    doc.text(String(v || '—'), 196, my, { align: 'right' });
    my += 5.2;
  });

  const top = Math.max(ay, my) + 3;
  doc.setDrawColor(...LINE);
  doc.setLineWidth(0.4);
  doc.line(14, top, 196, top);

  F('bold');
  doc.setFontSize(8.5);
  doc.setTextColor(...TERRA);
  doc.text('BILLED TO', 14, top + 8);
  F('bold');
  doc.setFontSize(11.5);
  doc.setTextColor(...DARK);
  doc.text(String(inv.tenantName || ''), 14, top + 14.5);
  F('normal');
  doc.setFontSize(9);
  doc.setTextColor(...GRAY);
  const stay = inv.checkIn
    ? `Stay: ${fmtDate(inv.checkIn)}  to  ${inv.checkOut ? fmtDate(inv.checkOut) : 'Present'}`
    : '';
  const tlines = [
    inv.tenantEmail,
    inv.tenantMobile && `Ph: ${inv.tenantMobile}`,
    `Room ${inv.roomNumber || '-'}  /  Bed ${inv.bedNumber || '-'}`,
    inv.occupation && `Occupation: ${inv.occupation}`,
    stay,
    inv.emergencyContact && `Emergency Contact: ${inv.emergencyContact}`,
  ].filter(Boolean);
  let ty = top + 20;
  tlines.forEach((l) => {
    doc.text(String(l), 14, ty);
    ty += 4.6;
  });

  const rows = [];
  const add = (label, val, force) => {
    if (force || Number(val)) rows.push([String(rows.length + 1), label, money(val)]);
  };
  add('Monthly Rent', inv.rent, true);
  add('Security Deposit', inv.securityDeposit);
  add('Electricity Charges', inv.electricity);
  add('Food / Meal Charges', inv.food);
  add('Maintenance Charges', inv.maintenance);
  add('Other Charges', inv.otherCharges);
  add('Previous Balance', inv.previousBalance);

  autoTable(doc, {
    startY: ty + 3,
    head: [['#', 'Description', 'Amount']],
    body: rows,
    theme: 'plain',
    margin: { left: 14, right: 14, bottom: 24 },
    styles: {
      font: fontOk ? 'PdfFont' : 'helvetica',
      fontSize: 9.5,
      textColor: DARK,
      cellPadding: { top: 2.8, bottom: 2.8, left: 1, right: 1 },
      lineColor: LINE,
      lineWidth: { bottom: 0.2 },
    },
    headStyles: { fontStyle: 'bold', fontSize: 8.5, textColor: GRAY, lineWidth: { bottom: 0.5 } },
    columnStyles: {
      0: { cellWidth: 10, textColor: GRAY },
      2: { halign: 'right', cellWidth: 36 },
    },
  });

  let y2 = doc.lastAutoTable.finalY + 8;
  if (y2 > 240) {
    doc.addPage();
    y2 = 24;
  }
  const lx = 118;
  const vx = 196;
  const trow = (label, val, bold, color) => {
    F(bold ? 'bold' : 'normal');
    doc.setFontSize(bold ? 11 : 9.5);
    doc.setTextColor(...(color || DARK));
    doc.text(label, lx, y2);
    doc.text(val, vx, y2, { align: 'right' });
    y2 += bold ? 7 : 5.6;
  };
  trow('Subtotal', money(inv.subtotal));
  trow('Discount', Number(inv.discount) ? `- ${money(inv.discount)}` : money(0));
  doc.setDrawColor(...LINE);
  doc.line(lx - 2, y2 - 3.4, 196, y2 - 3.4);
  y2 += 1.5;
  trow('Total Amount', money(inv.total), true, TERRA);
  trow('Amount Paid', money(inv.amountPaid));
  const bal = Number(inv.balanceDue) || 0;
  trow(bal < 0 ? 'Advance / Credit' : 'Balance Due', money(Math.abs(bal)), true, bal > 0 ? RED : bal < 0 ? GREEN : DARK);

  y2 += 3;
  if (y2 > 250) {
    doc.addPage();
    y2 = 24;
  }
  F('bold');
  doc.setFontSize(8.5);
  doc.setTextColor(...TERRA);
  doc.text('PAYMENT DETAILS', 14, y2);
  y2 += 5.5;
  F('normal');
  doc.setFontSize(9);
  const statusColor = inv.paymentStatus === 'Paid' ? GREEN : inv.paymentStatus === 'Pending' ? RED : [232, 163, 23];
  const plines = [
    ['Status:', inv.paymentStatus || '—', statusColor],
    ['Payment Mode:', inv.paymentMode || '—', DARK],
    ['Transaction ID / UTR:', inv.transactionId || '—', DARK],
  ];
  plines.forEach(([k, v, c]) => {
    doc.setTextColor(...GRAY);
    doc.text(k, 14, y2);
    F('bold');
    doc.setTextColor(...c);
    doc.text(String(v), 52, y2);
    F('normal');
    y2 += 5.2;
  });

  const notesText = [s.paymentTerms && `Terms: ${s.paymentTerms}`, s.notes && `Note: ${s.notes}`].filter(Boolean).join('\n');
  if (notesText) {
    y2 += 2;
    if (y2 > 252) {
      doc.addPage();
      y2 = 24;
    }
    F('normal');
    doc.setFontSize(8.5);
    doc.setTextColor(...GRAY);
    const wrapped = doc.splitTextToSize(notesText, 120);
    doc.text(wrapped, 14, y2);
    y2 += wrapped.length * 4.2;
  }

  let sy = Math.max(y2 + 14, 246);
  if (sy > 258) {
    doc.addPage();
    sy = 40;
  }
  if (s.signature) {
    try {
      doc.addImage(s.signature, 'PNG', 158, sy, 36, 15);
    } catch (e) {
      try { doc.addImage(s.signature, 'JPEG', 158, sy, 36, 15); } catch (e2) { /* skip */ }
    }
  }
  doc.setDrawColor(...DARK);
  doc.setLineWidth(0.3);
  doc.line(150, sy + 17, 196, sy + 17);
  F('normal');
  doc.setFontSize(8.5);
  doc.setTextColor(...GRAY);
  doc.text('Authorized Signature', 173, sy + 22, { align: 'center' });

  const pages = doc.getNumberOfPages();
  for (let i = 1; i <= pages; i++) {
    doc.setPage(i);
    doc.saveGraphicsState();
    try {
      doc.setGState(new doc.GState({ opacity: 0.055 }));
    } catch (e) { /* older jspdf */ }
    F('bold');
    doc.setFontSize(48);
    doc.setTextColor(110, 108, 105);
    doc.text(String(s.watermarkText || s.businessName || 'SHREE STAY HOMES & PG'), 105, 170, {
      align: 'center',
      angle: 32,
    });
    doc.restoreGraphicsState();
    doc.setDrawColor(...LINE);
    doc.setLineWidth(0.3);
    doc.line(14, 284, 196, 284);
    F('normal');
    doc.setFontSize(8);
    doc.setTextColor(...GRAY);
    doc.text('This invoice is generated by Shree Stay Homes & PG.', 105, 289.5, { align: 'center' });
    doc.text(`Page ${i} of ${pages}`, 196, 289.5, { align: 'right' });
  }

  return doc;
}

export function pdfFilename(inv) {
  return `ShreeStayHomesPG_Invoice_${inv.invoiceNumber}.pdf`;
}

export function downloadPDF(doc, inv) {
  doc.save(pdfFilename(inv));
}

export function pdfToBase64(doc) {
  return doc.output('datauristring').split(',')[1];
}

export function printPDF(doc) {
  const blob = doc.output('blob');
  const url = URL.createObjectURL(blob);
  const iframe = document.createElement('iframe');
  iframe.style.position = 'fixed';
  iframe.style.right = '0';
  iframe.style.bottom = '0';
  iframe.style.width = '0';
  iframe.style.height = '0';
  iframe.style.border = '0';
  iframe.src = url;
  iframe.onload = () => {
    setTimeout(() => {
      try {
        iframe.contentWindow.focus();
        iframe.contentWindow.print();
      } catch (e) {
        window.open(url, '_blank');
      }
    }, 400);
  };
  document.body.appendChild(iframe);
}
