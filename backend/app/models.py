# Data modeli - implementiraćemo kasnije
from pydantic import BaseModel

class InvoiceData(BaseModel):
    invoice_number: str
    date: str
    total_amount: str
    vendor_name: str
