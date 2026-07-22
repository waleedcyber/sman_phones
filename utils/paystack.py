import httpx
from fastapi import HTTPException
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "sk_test_fd548f112d32d3fa6782a3e1daada4781ad289c0")
PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY", "pk_test_e5ca24ace5786aad1f6f343bb59406dfecd9a542")
PAYSTACK_BASE_URL = "https://api.paystack.co"

async def verify_paystack_transaction(reference: str) -> dict:
    """
    Verify a Paystack transaction using the reference.
    Returns the verification response if successful.
    Raises HTTPException if verification fails.
    """
    if not PAYSTACK_SECRET_KEY:
        raise HTTPException(
            status_code=500,
            detail="Paystack secret key not configured"
        )

    async with httpx.AsyncClient() as client:
        headers = {
            "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        response = await client.get(
            f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}",
            headers=headers
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail="Failed to verify payment"
            )
            
        result = response.json()
        
        if not result["status"] or not result["data"]["status"] == "success":
            raise HTTPException(
                status_code=400,
                detail="Payment verification failed"
            )
            
        return result["data"]

# ─── 1. FIXED VERIFICATION FUNCTION (TRUE ASYNC) ───
async def verify_paystack_transaction(reference: str) -> dict:
    """Asynchronous verification for a Paystack transaction."""
    if not PAYSTACK_SECRET_KEY:
        raise HTTPException(
            status_code=500,
            detail="Paystack secret key not configured"
        )

    headers = {
        "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    # Use AsyncClient with await so it doesn't freeze your FastAPI app
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}", 
            headers=headers
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail="Failed to verify payment"
        )

    result = response.json()
    if not result.get("status") or result.get("data", {}).get("status") != "success":
        raise HTTPException(
            status_code=400,
            detail="Payment verification failed"
        )

    return result["data"]


