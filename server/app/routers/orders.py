from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid

from app.core.database import get_db
from app.models.orders import Order

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderCreate(BaseModel):
    user_id: str
    product_name: str
    total_amount: float = 0.0
    shipping_address: str | None = None


class AddressUpdate(BaseModel):
    new_address: str


@router.post("", status_code=status.HTTP_201_CREATED)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    """Creates a new order in the database."""
    try:
        user_uuid = uuid.UUID(payload.user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user_id format. Must be a valid UUID."
        )

    db_order = Order(
        user_id=user_uuid,
        product_name=payload.product_name,
        total_amount=payload.total_amount,
        shipping_address=payload.shipping_address,
        status="pending"
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    return {
        "order_id": str(db_order.order_id),
        "user_id": str(db_order.user_id),
        "product_name": db_order.product_name,
        "total_amount": float(db_order.total_amount),
        "shipping_address": db_order.shipping_address,
        "status": db_order.status,
        "created_at": db_order.created_at.isoformat() if db_order.created_at else None
    }


@router.get("")
def list_orders(
    user_id: str | None = None,
    payload: dict | None = Body(default=None),
    db: Session = Depends(get_db)
):
    """Lists all orders belonging to a specific user_id."""
    effective_user_id = user_id
    if not effective_user_id and payload:
        effective_user_id = payload.get("user_id")

    if not effective_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id is required either as a query parameter (?user_id=...) or in the JSON request body."
        )

    try:
        user_uuid = uuid.UUID(effective_user_id.strip('"').strip("'"))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user_id format. Must be a valid UUID."
        )

    db_orders = db.query(Order).filter(Order.user_id == user_uuid).all()
    return [
        {
            "order_id": str(order.order_id),
            "user_id": str(order.user_id),
            "status": order.status,
            "product_name": order.product_name,
            "total_amount": float(order.total_amount),
            "shipping_address": order.shipping_address,
            "created_at": order.created_at.isoformat() if order.created_at else None
        }
        for order in db_orders
    ]


@router.get("/lookup")
def lookup_order(product_name: str, user_id: str, db: Session = Depends(get_db)):
    """Looks up an order by product name and user_id."""
    try:
        user_uuid = uuid.UUID(user_id.strip('"').strip("'"))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user_id format. Must be a valid UUID."
        )

    db_order = db.query(Order).filter(
        Order.user_id == user_uuid,
        Order.product_name.ilike(f"%{product_name}%")
    ).first()

    if not db_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No order found for product '{product_name}' associated with this account."
        )

    return {
        "order_id": str(db_order.order_id),
        "user_id": str(db_order.user_id),
        "status": db_order.status,
        "product_name": db_order.product_name,
        "total_amount": float(db_order.total_amount),
        "shipping_address": db_order.shipping_address
    }


@router.get("/{order_id}")
def get_order(order_id: str, db: Session = Depends(get_db)):
    """Fetches details for a specific order."""
    try:
        order_uuid = uuid.UUID(order_id.strip('"').strip("'"))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid order_id format. Must be a valid UUID."
        )

    db_order = db.query(Order).filter(Order.order_id == order_uuid).first()
    if not db_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found."
        )

    return {
        "order_id": str(db_order.order_id),
        "user_id": str(db_order.user_id),
        "status": db_order.status,
        "product_name": db_order.product_name,
        "total_amount": float(db_order.total_amount),
        "shipping_address": db_order.shipping_address
    }


@router.put("/{order_id}/address")
def update_order_address(order_id: str, payload: AddressUpdate, db: Session = Depends(get_db)):
    """Updates the shipping address for the given order in the database."""
    try:
        order_uuid = uuid.UUID(order_id.strip('"').strip("'"))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid order_id format. Must be a valid UUID."
        )

    db_order = db.query(Order).filter(Order.order_id == order_uuid).first()
    if not db_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found."
        )

    db_order.shipping_address = payload.new_address
    db.commit()
    db.refresh(db_order)

    return {
        "status": "success",
        "message": f"Successfully updated shipping address for order '{order_id}' to '{payload.new_address}'.",
        "order": {
            "order_id": str(db_order.order_id),
            "user_id": str(db_order.user_id),
            "status": db_order.status,
            "product_name": db_order.product_name,
            "shipping_address": db_order.shipping_address
        }
    }
