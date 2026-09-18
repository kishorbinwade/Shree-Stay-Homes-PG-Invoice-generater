import { toast } from 'sonner';

export function notifyInvoiceEmail(status) {
  if (status.owner !== 'sent') {
    toast.error(status.errors?.owner || 'Owner email failed — use Retry Email');
  } else if (status.tenant === 'no-email') {
    toast.success('Owner email sent. Tenant email not available.');
  } else if (status.tenant === 'failed') {
    toast.warning('Owner email sent. Tenant CC failed — use Retry Email.');
  } else {
    toast.success('Invoice emailed to owner with tenant in CC and PDF attached.');
  }
}