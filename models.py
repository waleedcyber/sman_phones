from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, Boolean, Table
from sqlalchemy.orm import relationship, backref
from datetime import datetime
from db import Base

product_categories = Table(
    "product_categories",
    Base.metadata,
    Column("product_id", Integer, ForeignKey("products.id"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id"), primary_key=True),
)

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    children = relationship("Category", backref=backref("parent", remote_side=[id]))
    products = relationship("Product", secondary=product_categories, back_populates="categories")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String)
    price = Column(Float, nullable=False)
    original_price = Column(Float, nullable=True)       # ✅ for strikethrough
   # stock = Column(Integer, default=0)
    image_url = Column(String)
    cloudinary_public_id = Column(String, nullable=True)
    quantity = Column(Integer, default=0)
    # Phone specific fields
    brand = Column(String, nullable=True)               # ✅ iPhone, Samsung etc
    condition = Column(String, nullable=True)           # ✅ New, Open Box, Used
    storage = Column(String, nullable=True)             # ✅ 128GB, 256GB etc
    color = Column(String, nullable=True)               # ✅ Black, White etc
    battery_health = Column(Integer, nullable=True)     # ✅ percentage for used phones
    is_featured = Column(Boolean, default=False)        # ✅ show on homepage
    categories = relationship("Category", secondary=product_categories, back_populates="products")

class TradeIn(Base):
    __tablename__ = "trade_ins"
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, nullable=False)
    customer_email = Column(String, nullable=True)
    phone_brand = Column(String, nullable=False)
    phone_model = Column(String, nullable=False)
    phone_storage = Column(String, nullable=True)
    phone_condition = Column(String, nullable=False)
    battery_health = Column(Integer, nullable=True)
    issues = Column(Text, nullable=True)
    desired_phone = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")          # pending, reviewed, completed

class ProductRequest(Base):
    __tablename__ = "product_requests"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    customer_name = Column(String)
    customer_email = Column(String)
    message = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    product = relationship("Product")

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, index=True, nullable=False)
    customer_name = Column(String, nullable=False)
    customer_email = Column(String, nullable=False)
    customer_phone = Column(String, nullable=False)
    customer_address = Column(String, nullable=True)
    item_names = Column(Text, nullable=False)
    items = Column(Text, nullable=False)
    total = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")
    payment_status = Column(String, default="pending")
    payment_reference = Column(String, nullable=True)
    paid = Column(Boolean, default=False)
    paid_at = Column(DateTime, nullable=True)

class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)