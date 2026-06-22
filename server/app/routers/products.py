from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid

from app.core.database import get_db
from app.models.products import Product

router = APIRouter(prefix="/products", tags=["products"])


@router.get("")
def list_products(db: Session = Depends(get_db)):
    """Retrieve all active products in the catalog."""
    db_products = db.query(Product).filter(Product.is_active == True).all()
    return [
        {
            "product_id": str(p.product_id),
            "name": p.name,
            "description": p.description,
            "category": p.category,
            "price": float(p.price),
        }
        for p in db_products
    ]


@router.get("/{product_id}")
def get_product(product_id: str, db: Session = Depends(get_db)):
    """Retrieve details for a single product."""
    try:
        product_uuid = uuid.UUID(product_id.strip('"').strip("'"))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid product_id format. Must be a valid UUID."
        )

    db_product = db.query(Product).filter(Product.product_id == product_uuid).first()
    if not db_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product '{product_id}' not found."
        )

    return {
        "product_id": str(db_product.product_id),
        "name": db_product.name,
        "description": db_product.description,
        "category": db_product.category,
        "price": float(db_product.price)
    }
