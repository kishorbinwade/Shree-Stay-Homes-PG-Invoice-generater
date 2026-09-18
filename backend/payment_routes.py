from datetime import date
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
import database as db
import payment_store as store

router = APIRouter(prefix="/api")


class PaymentIn(BaseModel):
    paymentDate: str = Field(default_factory=lambda: date.today().isoformat())
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2, allow_inf_nan=False)
    paymentMethod: Literal['Cash', 'UPI', 'Bank Transfer', 'Card', 'Other'] = 'Cash'
    reference: str = Field(default='', max_length=200)
    notes: str = Field(default='', max_length=2000)

    @field_validator('paymentDate')
    @classmethod
    def date_valid(cls, value):
        return store.valid_date(value)


class PaymentCreate(PaymentIn):
    invoiceId: str = Field(min_length=1)


def mutate(action):
    with db._lock:
        conn = db.get_conn()
        try:
            conn.execute('BEGIN IMMEDIATE')
            result = action(conn)
            conn.commit()
            return result
        except (LookupError, ValueError) as exc:
            conn.rollback()
            raise HTTPException(status_code=404 if isinstance(exc, LookupError) else 422, detail=str(exc))
        except Exception:
            conn.rollback()
            raise


@router.get('/payments')
def all_payments():
    with db._lock:
        invoices = {i['id']: i for i in db.list_invoices()}
        return [{**p, 'invoiceNumber': invoices[p['invoiceId']]['invoiceNumber'],
                 'tenantName': invoices[p['invoiceId']]['tenantName']} for p in store.list_payments(db.get_conn())]


@router.get('/invoices/{invoice_id}/payments')
def invoice_payments(invoice_id: str):
    inv = db.get_invoice(invoice_id)
    if not inv:
        raise HTTPException(404, 'Invoice not found')
    return {key: inv[key] for key in ('payments', 'invoice_total', 'total_paid', 'balance_due', 'payment_status')}


@router.post('/payments', status_code=201)
def create_payment(payload: PaymentCreate):
    return mutate(lambda conn: store.insert(conn, payload.invoiceId, payload.model_dump()))


@router.put('/payments/{payment_id}')
def update_payment(payment_id: str, payload: PaymentIn):
    return mutate(lambda conn: store.edit(conn, payment_id, payload.model_dump()))


@router.delete('/payments/{payment_id}')
def delete_payment(payment_id: str):
    def remove(conn):
        row = conn.execute('SELECT invoice_id FROM payments WHERE id=?', (payment_id,)).fetchone()
        if not row:
            raise LookupError('Payment not found')
        conn.execute('DELETE FROM payments WHERE id=?', (payment_id,))
        return {'deleted': True, **store.sync_invoice(conn, row['invoice_id'])}
    return mutate(remove)


@router.get('/payments/{payment_id}/receipt')
def payment_receipt(payment_id: str):
    with db._lock:
        try:
            return store.receipt(db.get_conn(), payment_id)
        except LookupError as exc:
            raise HTTPException(404, str(exc))