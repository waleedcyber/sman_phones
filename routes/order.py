from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db import get_db
from models import Order, Product
from datetime import datetime
from typing import List, Optional
from schemas import OrderOut  # Assuming you created this
from fastapi import Depends, HTTPException
from auth import get_current_admin
import json


router = APIRouter()


# ✅ View orders (all or by status)
@router.get("/orders", response_model=List[OrderOut])
def get_orders(status: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Order)
    if status:
        query = query.filter(Order.payment_status == status)
    return query.order_by(Order.timestamp.desc()).all()

 # mark as paid order
@router.patch("/orders/{order_id}/mark-paid")
def mark_order_paid(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.payment_status = "paid"
    order.paid_at = datetime.utcnow()
    db.commit()
    return {"message": "Order marked as paid"}


# ✅ View paid orders
@router.get("/paid-orders")
def get_paid_orders(db: Session = Depends(get_db)):
    orders = db.query(Order).filter(Order.payment_status == "paid").order_by(Order.paid_at.desc()).all()
    return orders


# ✅ Mark order as paid using integer ID
@router.put("/orders/by-id/{order_id}/mark-paid")
def mark_order_paid_by_id(order_id: int, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.payment_status = "paid"
    order.paid_at = datetime.utcnow()

    db.commit()
    db.refresh(order)
    return {"message": f"Order {order.id} marked as paid"}


# ✅ Mark order as paid using custom string order_id and ref
@router.post("/orders/by-code/{order_id}/mark-paid")
def mark_order_paid_by_code(
    order_id: str,
    reference: str,
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(
        Order.order_id == order_id
    ).first()

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    # Prevent duplicate stock deduction
    if order.paid:
        return {
            "message": "Order is already marked as paid"
        }

    # Check stock and deduct it
    reduce_product_stock(
        order_id=order.id,
        db=db
    )

    order.payment_status = "paid"
    order.payment_reference = reference
    order.paid = True
    order.paid_at = datetime.utcnow()

    db.commit()
    db.refresh(order)

    return {
        "message": "Order marked as paid and stock updated",
        "order": {
            "order_id": order.order_id,
            "payment_status": order.payment_status,
            "paid_at": order.paid_at.isoformat()
        }
    }


def reduce_product_stock(order_id: int, db: Session):
    """
    Deduct product quantities from stock for a paid order.
    Uses the product_id and quantity stored in Order.items.
    """

    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    try:
        items = json.loads(order.items)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid order items data"
        )

    # Check ALL products before deducting anything.
    # This prevents a multi-product order from partially
    # reducing stock if one product doesn't have enough stock.
    for item in items:
        product_id = item.get("product_id")
        requested_quantity = int(item.get("quantity", 0))

        if not product_id or requested_quantity < 1:
            raise HTTPException(
                status_code=400,
                detail="Invalid product information in order"
            )

        product = db.query(Product).filter(
            Product.id == product_id
        ).first()

        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Product {product_id} not found"
            )

        if product.quantity < requested_quantity:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Not enough stock for {product.name}. "
                    f"Only {product.quantity} left in stock."
                )
            )

    # All products have enough stock, so now deduct.
    for item in items:
        product = db.query(Product).filter(
            Product.id == item["product_id"]
        ).first()

        product.quantity -= int(item["quantity"])

    db.commit()

    return True

# ✅ Delete an order (admin-protected)
@router.delete("/orders/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db), admin: dict = Depends(get_current_admin)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    db.delete(order)
    db.commit()
    return {"message": "Order deleted"}


