from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db import get_db
from models import ProductRequest, Product, Order
from schemas import OrderCreate, OrderOut, ProductRequestSchema
from datetime import datetime, timezone
from typing import List
import string
import random
import json

router = APIRouter()


def generate_unique_order_id(db):
    while True:
        order_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        exists = db.query(Order).filter(Order.order_id == order_id).first()
        if not exists:
            return order_id

@router.get("/orders/grouped")
def grouped_orders(db: Session = Depends(get_db)):
    data = db.query(Order).all()
    result = {
        "pending": [],
        "delivered": [],
        "cancelled": [],
        "other": []
    }
    for order in data:
        out = OrderOut.model_validate(order)
        if order.status.lower() == "pending":
            result["pending"].append(out)
        elif order.status.lower() == "delivered":
            result["delivered"].append(out)
        elif order.status.lower() == "cancelled":
            result["cancelled"].append(out)
        else:
            result["other"].append(out)
    return result
@router.post("/orders", response_model=OrderOut)
def create_order(
    order: OrderCreate,
    db: Session = Depends(get_db)
):
    # ---------------------------------------------------------
    # Validate product stock BEFORE creating the order
    # ---------------------------------------------------------

    for item in order.items:
        product = db.query(Product).filter(
            Product.id == item.product_id
        ).first()

        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Product {item.product_id} not found"
            )

        if item.quantity < 1:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid quantity for {product.name}"
            )

        if product.quantity < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Not enough stock for {product.name}. "
                    f"Only {product.quantity} left in stock."
                )
            )

    # ---------------------------------------------------------
    # Create order
    # ---------------------------------------------------------

    order_id = generate_unique_order_id(db)

    new_order = Order(
        order_id=order_id,
        customer_name=order.name,
        customer_phone=order.phone,
        customer_email=order.email,
        customer_address=order.address,

        item_names=", ".join(
            [item.name for item in order.items]
        ),

        items=json.dumps(
            [item.dict() for item in order.items]
        ),

        total=order.total,
        status="Pending",
        payment_status="Unpaid",
        timestamp=datetime.now(timezone.utc),
    )

    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    return OrderOut.model_validate(new_order)

@router.get("/orders", response_model=List[OrderOut])
def get_all_orders(db: Session = Depends(get_db)):
    orders = db.query(Order).all()
    now = datetime.utcnow()  # Use naive datetime to match stored timestamps
    output = []
    for order in orders:
        delta = now - order.timestamp
        if delta.days > 0:
            time_ago = f"{delta.days} day(s) ago"
        elif delta.seconds >= 3600:
            time_ago = f"{delta.seconds // 3600} hour(s) ago"
        elif delta.seconds >= 60:
            time_ago = f"{delta.seconds // 60} minute(s) ago"
        else:
            time_ago = "just now"
        out = OrderOut.model_validate(order)
        out.time_ago = time_ago
        output.append(out)
    return output

@router.post("/request-product")
def request_product(data: ProductRequestSchema, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    request_entry = ProductRequest(
        product_id=data.product_id,
        customer_name=data.customer_name,
        customer_email=data.customer_email,
        message=data.message
    )
    db.add(request_entry)
    db.commit()
    db.refresh(request_entry)
    return {"message": "Request submitted successfully"}

