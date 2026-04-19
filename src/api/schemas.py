from typing import Literal

from pydantic import BaseModel

transaction_example = {
    "transaction_id": "txn_9f3a2c1b4e7d",
    "user_id": "usr_00142",
    "merchant_id": "mrc_88231",
    "amount": 249.99,
    "currency": "USD",
    "payment_method": "credit_card",
    "timestamp": "2024-03-15T14:32:07Z",
    "country": "US",
    "city": "New York",
    "device_id": "dev_a1b2c3d4",
    "ip_address": "192.168.1.101",
    "device_type": "mobile",
    "merchant_category": "electronics",
    "is_international": False,
    "is_fraud": False,
}


class ReviewCaseRequest(BaseModel):
    analyst_status: Literal["CONFIRMED_FRAUD", "FALSE_POSITIVE", "APPROVED"]
    analyst_notes: str | None = None


class WorkflowAuditEventRequest(BaseModel):
    case_id: int | None = None
    workflow_name: str
    workflow_action: str
    status: str = "SUCCESS"
    escalation_priority: str | None = None
    message: str | None = None
    payload: dict | str | None = None
    source: str = "n8n"
