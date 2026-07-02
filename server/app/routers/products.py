from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid

from app.database.connection import get_db
from app.database.tables.products import Product
from app.database.data_types.products import ProductResponse

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductResponse])
def list_products(db: Session = Depends(get_db)):
    """Retrieve all active products in the catalog."""
    db_products = db.query(Product).all()
    return db_products


@router.get("/{pid}", response_model=ProductResponse)
def get_product(pid: str, db: Session = Depends(get_db)):
    """Retrieve details for a single product."""
    try:
        product_uuid = uuid.UUID(pid.strip('"').strip("'"))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pid format. Must be a valid UUID."
        )

    db_product = db.query(Product).filter(Product.pid == product_uuid).first()
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{pid}' not found."
        )

    return db_product
