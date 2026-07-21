from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
from fastapi.responses import FileResponse
from fastapi.exceptions import HTTPException as StarletteHTTPException

# Local imports
from database_setup import create_tables
from routes.product import router as product_router
from routes.admin import router as admin_router
from routes.product_request import router as product_request_router
from routes.payment import router as payment_router
from routes.trade_in import router as trade_in_router

# Import necessary for admin creation
from sqlalchemy.orm import Session
from db import SessionLocal
from models import Admin
from auth import get_password_hash  # ensure get_password_hash exists in auth.py

# --- Configuration for the bootstrap admin ---
# Read defaults from environment or use sane local defaults for development
DEFAULT_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME",)
DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD",)  # change for production
# -------------------------------------------

# ✅ Lifespan setup (runs once at startup)
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Running lifespan startup tasks...")
    create_tables() # Ensure tables exist

    # --- Bootstrap Admin Logic ---
    db = SessionLocal()
    try:
        # Check if any admin exists
        existing_admin = db.query(Admin).first()
        if not existing_admin:
            print(f"No admin found. Creating default admin: {DEFAULT_ADMIN_USERNAME}")
            hashed_password = get_password_hash(DEFAULT_ADMIN_PASSWORD)
            new_admin = Admin(username=DEFAULT_ADMIN_USERNAME, password=hashed_password)
            db.add(new_admin)
            db.commit()
            print("Default admin created successfully.")
        else:
            print("Admin user(s) already exist. Skipping default admin creation.")
    except Exception as e:
        print(f"Error during admin bootstrap: {e}")
        # Depending on severity, you might want to raise the error or just log it.
        # For a simple bootstrap, logging and continuing might be okay.
    finally:
        db.close()
    # --- End Bootstrap Admin Logic ---

    yield
    print("Running lifespan shutdown tasks...")

# ✅ Create FastAPI app
app = FastAPI(lifespan=lifespan) # Make sure to pass the lifespan here
app.add_middleware(
    CORSMiddleware,
    # Keep deployed origin(s) explicit and allow any localhost/127.0.0.1 port for local testing
    allow_origins=[
        "https://sman-phones1.onrender.com"
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request, exc):
    if exc.status_code == 404:
        return FileResponse("404.html")
    raise exc


# ✅ Include routers under /api
app.include_router(product_router, prefix="/api", tags=["Products"])
app.include_router(admin_router, prefix="/api", tags=["Admin"])
app.include_router(product_request_router, prefix="/api", tags=["Product Requests"])
app.include_router(trade_in_router, prefix="/api", tags=["Trade-In"])
app.include_router(payment_router, prefix="/api", tags=["Payments"])

# ✅ Static files
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/", StaticFiles(directory=".", html=True), name="root")
@app.exception_handler(StarletteHTTPException)
async def custom_404_handler(request, exc):
    if exc.status_code == 404:
        return FileResponse("404.html")
    raise exc