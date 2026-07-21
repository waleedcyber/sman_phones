from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from db import get_db
from fastapi.security import OAuth2PasswordRequestForm
from models import Product, Order, Category, ProductRequest
from schemas import ProductRequestResponseSchema, CategoryCreate
from models import Admin
from auth import get_current_admin
from auth import verify_password, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from datetime import datetime, timedelta
from typing import List, Optional
import cloudinary
import cloudinary.uploader
import os

router = APIRouter()

# Cloudinary config
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)


@router.post("/admin/login")
def admin_login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.username == form_data.username).first()
    if not admin:
        raise HTTPException(status_code=400, detail="Invalid username or password")
    if not verify_password(form_data.password, admin.password):
        raise HTTPException(status_code=400, detail="Invalid username or password")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": admin.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}



@router.post("/admin/upload", tags=["Admin"])
def upload_product(
    name: str = Form(...),
    description: str = Form(...),
    price: float = Form(...),
    original_price: float = Form(None),
    quantity: int = Form(...),
    category_ids: str = Form(...),
    brand: str = Form(None),
    condition: str = Form(None),
    storage: str = Form(None),
    color: str = Form(None),
    battery_health: int = Form(None),
    is_featured: bool = Form(False),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    file_ext = os.path.splitext(image.filename)[1].lower()
    if file_ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        raise HTTPException(status_code=400, detail="Invalid image format")

    try:
        ids = [int(i.strip()) for i in category_ids.split(",") if i.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid category IDs")

    categories = db.query(Category).filter(Category.id.in_(ids)).all()

    try:
        result = cloudinary.uploader.upload(image.file, folder="sman_apple_comms", resource_type="image")
        image_url = result["secure_url"]
        public_id = result["public_id"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image upload failed: {str(e)}")

    product = Product(
        name=name, description=description,
        price=price, original_price=original_price,
        quantity=quantity, image_url=image_url,
        cloudinary_public_id=public_id,
        brand=brand, condition=condition,
        storage=storage, color=color,
        battery_health=battery_health,
        is_featured=is_featured,
        categories=categories,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return {"message": "Product uploaded successfully", "product": product}


@router.get("/admin/products", tags=["Admin"])
def get_all_products(db: Session = Depends(get_db), admin: dict = Depends(get_current_admin)):
    products = db.query(Product).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "quantity": p.quantity,
            "description": p.description,
            "image_url": p.image_url,
            "categories": [{"id": c.id, "name": c.name} for c in p.categories],
        }
        for p in products
    ]


@router.delete("/admin/products/{product_id}", status_code=204, tags=["Admin"])
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if product.cloudinary_public_id:
        try:
            cloudinary.uploader.destroy(product.cloudinary_public_id)
        except Exception:
            pass

    db.delete(product)
    db.commit()
    return {"message": "Product deleted successfully"}


@router.get("/admin/products/{product_id}", tags=["Admin"])
def get_product(product_id: int, db: Session = Depends(get_db), admin: dict = Depends(get_current_admin)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return {
        "id": product.id,
        "name": product.name,
        "price": product.price,
        "quantity": product.quantity,
        "description": product.description,
        "image_url": product.image_url,
        "categories": [{"id": c.id, "name": c.name} for c in product.categories],
    }


@router.put("/admin/products/{product_id}", tags=["Admin"])
def update_product(
    product_id: int,
    name: str = Form(...),
    description: str = Form(None),
    price: float = Form(...),
    quantity: int = Form(...),
    category_ids: str = Form(...),  # comma-separated
    image: UploadFile = File(None),
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.name = name
    product.description = description
    product.price = price
    product.quantity = quantity

    # Update categories
    try:
        ids = [int(i.strip()) for i in category_ids.split(",") if i.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid category IDs")

    categories = db.query(Category).filter(Category.id.in_(ids)).all()
    product.categories = categories  # ✅ replaces old categories

    if image is not None:
        file_ext = os.path.splitext(image.filename)[1].lower()
        if file_ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            raise HTTPException(status_code=400, detail="Invalid image format")

        if product.cloudinary_public_id:
            try:
                cloudinary.uploader.destroy(product.cloudinary_public_id)
            except Exception:
                pass

        try:
            result = cloudinary.uploader.upload(
                image.file,
                folder="s_and_s_collection",
                resource_type="image",
            )
            product.image_url = result["secure_url"]
            product.cloudinary_public_id = result["public_id"]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Image upload failed: {str(e)}")

    db.commit()
    db.refresh(product)
    return {
        "message": "Product updated",
        "product": {
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "quantity": product.quantity,
            "image_url": product.image_url,
            "categories": [{"id": c.id, "name": c.name} for c in product.categories],
        }
    }


@router.post("/admin/categories", status_code=201, tags=["Admin Categories"])
def create_category(
    category: CategoryCreate,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    existing = db.query(Category).filter(Category.name == category.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Category already exists")
    
    # Validate parent if provided
    if category.parent_id:
        parent = db.query(Category).filter(Category.id == category.parent_id).first()
        if not parent:
            raise HTTPException(status_code=400, detail="Parent category not found")
        # prevent nesting more than one level
        if parent.parent_id is not None:
            raise HTTPException(status_code=400, detail="Cannot nest more than one level deep")

    new_category = Category(name=category.name, parent_id=category.parent_id)
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    return {
        "message": "Category created",
        "category": {
            "id": new_category.id,
            "name": new_category.name,
            "parent_id": new_category.parent_id,
        }
    }


@router.get("/admin/categories", tags=["Admin Categories"])
def list_categories(db: Session = Depends(get_db), admin: dict = Depends(get_current_admin)):
    categories = db.query(Category).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "parent_id": c.parent_id,
            "children": [{"id": ch.id, "name": ch.name} for ch in c.children]
        }
        for c in categories
    ]


@router.put("/admin/categories/{category_id}", tags=["Admin Categories"])
def update_category(
    category_id: int,
    category: CategoryCreate,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    cat.name = category.name
    cat.parent_id = category.parent_id
    db.commit()
    db.refresh(cat)
    return {
        "id": cat.id,
        "name": cat.name,
        "parent_id": cat.parent_id,
    }


@router.delete("/admin/categories/{category_id}", tags=["Admin Categories"])
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    db.delete(cat)
    db.commit()
    return {"detail": "Category deleted"}


@router.get("/products/random", tags=["Products"])
def get_random_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "quantity": p.quantity,
            "description": p.description,
            "image_url": p.image_url,
            "categories": [{"id": c.id, "name": c.name} for c in p.categories],
        }
        for p in products
    ]


@router.get("/product-requests", response_model=None, tags=["Admin"])
def get_all_product_requests(
    db: Session = Depends(get_db), admin: dict = Depends(get_current_admin)
):
    requests = db.query(ProductRequest).all()
    result = []
    for r in requests:
        # Join product name
        product = db.query(Product).filter(Product.id == r.product_id).first()
        product_name = product.name if product else "Unknown Product"
        result.append({
            "id": r.id,
            "product_id": r.product_id,
            "product_name": product_name,
            "customer_name": r.customer_name,
            "customer_email": r.customer_email,
            "message": r.message or "No message provided.",
        })
    return result


@router.put("/orders/{order_id}/mark_paid", tags=["Admin"])
def mark_order_paid(
    order_id: int, db: Session = Depends(get_db), admin: dict = Depends(get_current_admin)
):
    order = db.query(Order).get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    # Prevent deducting stock twice if the order was already paid
    if order.paid:
        return {"message": "Order is already marked as paid"}

    # ─── CALL THE STOCK DEDUCTION UTILITY HERE ───
    reduce_product_stock(order_id=order.id, db=db)

    order.payment_status = "Paid"
    order.paid = True
    order.paid_at = datetime.utcnow()
    db.commit()
    return {"message": "Marked as paid and stock updated"}



import os
import hmac
import hashlib

# Assuming router and get_db are imported globally in this file
@router.post("/paystack-webhook", tags=["Payments"])
async def paystack_webhook(
    request: Request, 
    x_paystack_signature: str = Header(None), 
    db: Session = Depends(get_db)
):
    # 1. Reject requests missing the signature header
    if not x_paystack_signature:
        raise HTTPException(status_code=401, detail="Missing signature header")
        
    # 2. Read raw request payload
    payload_body = await request.body()
    
    # 3. Verify that the webhook request genuinely came from Paystack
    PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "sk_test_your_secret_key")
    computed_signature = hmac.new(
        PAYSTACK_SECRET_KEY.encode('utf-8'),
        payload_body,
        hashlib.sha512
    ).hexdigest()
    
    if not hmac.compare_digest(computed_signature, x_paystack_signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
        
    # 4. Parse the payload data
    event_data = await request.json()
    
    # 5. Handle successful checkout transactions
    if event_data.get("event") == "charge.success":
        data = event_data["data"]
        
        # Paystack provides the transaction reference string
        reference = data.get("reference") 
        
        # Locate the order using your database order reference column
        order = db.query(Order).filter(Order.reference == reference).first()
        
        if not order:
            # We return a 200/201 status even if order isn't found so Paystack stops retrying
            return {"status": "ignored", "message": "Order reference not found"}
            
        # 6. Apply identical updates as your manual admin endpoint
        order.payment_status = "Paid"
        order.paid = True
        order.paid_at = datetime.utcnow()
        db.commit()
        
        return {"status": "success", "message": f"Order {reference} automated as paid."}
        
    return {"status": "ignored", "message": "Event type not processed"}


@router.put("/orders/{order_id}/mark_delivered", tags=["Admin"])
def mark_order_delivered(
    order_id: int, db: Session = Depends(get_db), admin: dict = Depends(get_current_admin)
):
    order = db.query(Order).get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = "Delivered"
    db.commit()
    return {"message": "Marked as delivered"}