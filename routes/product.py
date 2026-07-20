from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form, Query, Request
from sqlalchemy.orm import Session
from db import get_db, SessionLocal
from models import Product, Category
from schemas import ProductCreate, ProductOut
import os
import random
import cloudinary
import cloudinary.uploader

router = APIRouter()

@router.post("/products")
def create_product(
    name: str = Form(...),
    price: float = Form(...),
    description: str = Form(...),
    quantity: int = Form(...),
    category_ids: str = Form(...),  # comma-separated
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Upload to Cloudinary
    try:
        result = cloudinary.uploader.upload(
            image.file,
            folder="s_and_s_collection",
            resource_type="image",
            transformation=[
                {"width": 800, "height": 300, "crop": 'fill', quality: 'auto', fetch_format: 'auto'}
            ]
            
        )
        image_url = result["secure_url"]
        public_id = result["public_id"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image upload failed: {str(e)}")

    # Parse and validate category IDs
    ids = [int(i.strip()) for i in category_ids.split(",") if i.strip()]
    categories = db.query(Category).filter(Category.id.in_(ids)).all()
    if not categories:
        raise HTTPException(status_code=400, detail="Invalid category IDs")

    new_product = Product(
        name=name,
        price=price,
        description=description,
        quantity=quantity,
        image_url=image_url,
        cloudinary_public_id=public_id,
        categories=categories,
    )

    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    return {
        "message": "Product created successfully",
        "product": {
            "id": new_product.id,
            "name": new_product.name,
            "price": new_product.price,
            "description": new_product.description,
            "quantity": new_product.quantity,
            "categories": [{"id": c.id, "name": c.name} for c in new_product.categories],
            "image_url": new_product.image_url,
        }
    }


@router.get("/products", response_model=List[ProductOut])
def get_products(
    db: Session = Depends(get_db),
    sort_by: str = Query(None)
):
    query = db.query(Product)

    if sort_by == "price":
        query = query.order_by(Product.price)
    elif sort_by == "name":
        query = query.order_by(Product.name)
    else:
        query = query.order_by(Product.id.desc())

    return query.all()


@router.get("/products/random", response_model=List[ProductOut])
def get_random_products(db: Session = Depends(get_db)):
    all_products = db.query(Product).all()
    sample_size = min(6, len(all_products))
    return random.sample(all_products, sample_size) if all_products else []

@router.get("/categories", tags=["Categories"])
def get_categories(db: Session = Depends(get_db)):
    # Only return parent categories with their children nested inside
    parents = db.query(Category).filter(Category.parent_id == None).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "parent_id": None,
            "children": [{"id": ch.id, "name": ch.name} for ch in c.children]
        }
        for c in parents
    ]