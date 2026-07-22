from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from db import get_db
from models import Order
from utils.paystack import verify_paystack_transaction_sync
import httpx
from config import PAYSTACK_SECRET_KEY, PAYSTACK_API_URL, PAYSTACK_PUBLIC_KEY
from datetime import datetime
import hmac
import hashlib
import os
import json
from pydantic import BaseModel

router = APIRouter()


class VerifyRequest(BaseModel):
    reference: str
    order_id: str


@router.post("/payments/verify")
def verify_payment(payload: VerifyRequest, db: Session = Depends(get_db)):
    """Verify a payment using Paystack and mark the order as paid.

    This endpoint should be called by the frontend after the Paystack callback
    to perform server-side verification using the secret key.
    """
    # Verify using Paystack API (sync wrapper)
    reference = payload.reference
    order_id = payload.order_id
    data = verify_paystack_transaction_sync(reference)

    # Basic checks
    if data.get("status") != "success":
        raise HTTPException(status_code=400, detail="Payment not successful")

    # Find order by order_id (custom string order_id)
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Idempotency: if already paid, return success
    if order.payment_status == "paid":
        return {"message": "Order already marked as paid"}

    # Optionally verify amount matches
    paystack_amount = data.get("amount")  # in kobo
    try:
        paystack_amount_n = float(paystack_amount) / 100.0
    except Exception:
        paystack_amount_n = None

    if paystack_amount_n is not None and abs(paystack_amount_n - float(order.total)) > 0.01:
        # Amount mismatch — log or raise
        raise HTTPException(status_code=400, detail="Payment amount does not match order total")

    # Update order
    order.payment_status = "paid"
    order.payment_reference = reference
    order.paid_at = datetime.utcnow()
    db.commit()
    db.refresh(order)

    return {"message": "Payment verified and order marked as paid", "order_id": order.order_id}



class InitializeRequest(BaseModel):
    email: str
    amount: float
    order_id: str


@router.post("/payments/initialize")
def initialize_payment(payload: InitializeRequest):
    """Initialize a Paystack transaction server-side so we can set callback_url and metadata.

    Returns authorization_url that the frontend can redirect the user to, or the access_token
    for inline transactions.
    """
    callback_url = os.getenv("PAYSTACK_CALLBACK_URL")
    if not callback_url:
        raise HTTPException(status_code=500, detail="PAYSTACK_CALLBACK_URL not configured in environment")

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    payload_data = {
        "email": payload.email,
        "amount": int(payload.amount * 100),
        "reference": payload.order_id,
        "callback_url": callback_url,
        "metadata": {"order_id": payload.order_id}
    }

    resp = httpx.post(f"{PAYSTACK_API_URL}/transaction/initialize", headers=headers, json=payload_data)
    if resp.status_code != 200 and resp.status_code != 201:
        raise HTTPException(status_code=400, detail="Failed to initialize payment")

    data = resp.json()
    return {"authorization_url": data.get("data", {}).get("authorization_url"), "data": data.get("data")}

# Import your connection manager if it is defined in another file (e.g., from main import manager)
# Or define/import your stock reduction function
# from utils.stock import reduce_product_stock 

@router.post("/payments/webhook")
async def paystack_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Paystack webhooks.

    Paystack sends POST requests to this endpoint for events such as charge.success.
    We verify the signature using the secret key and update the order accordingly.
    """
    # Read raw body for signature verification
    body = await request.body()
    signature = request.headers.get("x-paystack-signature") or request.headers.get("paystack-signature")

    secret = os.getenv("PAYSTACK_SECRET_KEY")
    if not secret:
        raise HTTPException(status_code=500, detail="Paystack secret not configured")

    computed = hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(computed, signature or ""):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    payload = json.loads(body.decode("utf-8"))
    event = payload.get("event")
    data = payload.get("data", {})

    # Handle charge.success
    if event == "charge.success":
        reference = data.get("reference")
        # Extract metadata/order id if you passed it
        order_code = data.get("metadata", {}).get("order_id") or data.get("reference")

        order = db.query(Order).filter(Order.order_id == order_code).first()
        
        # Check if the order exists and is not already paid to prevent double-deducting stock
        if order and order.payment_status != "paid":
            
            # ─── 1. CALL YOUR STOCK DEDUCTION UTILITY HERE ───
            # Adjust the function parameters to match your helper utility signature
            try:
                reduce_product_stock(order_id=order.id, db=db)
            except Exception as e:
                # Log the error but let the webhook complete so paystack stops retrying
                print(f"Failed to deduct stock for order {order_code}: {e}")

            # ─── 2. UPDATE YOUR DATABASE STATE ───
            order.payment_status = "paid"
            order.payment_reference = reference
            order.paid_at = datetime.utcnow()
            db.commit()

            # ─── 3. BROADCAST REAL-TIME UPDATE TO ADMIN WEBSOCKET ───
            # Checks if the WebSocket manager exists globally or in imports before running
            if 'manager' in globals():
                await manager.broadcast({"event": "order_updated", "reference": reference})
            elif 'admin_manager' in globals():
                await admin_manager.broadcast({"event": "order_updated", "reference": reference})

    # Always return 200 to acknowledge
    return {"status": "ok"}

