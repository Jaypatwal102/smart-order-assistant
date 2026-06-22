from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid

from app.core.database import get_db
from app.models.orders import Order, ShippingLog, OrderUpdateLog

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderCreate(BaseModel):
    user_id: str
    product_name: str
    total_amount: float = 0.0
    shipping_address: str | None = None


class AddressUpdate(BaseModel):
    new_address: str


class OrderReplace(BaseModel):
    replacement_product_name: str | None = None



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
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "ordered_at": order.ordered_at.isoformat() if order.ordered_at else None,
            "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None
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
        "shipping_address": db_order.shipping_address,
        "ordered_at": db_order.ordered_at.isoformat() if db_order.ordered_at else None,
        "delivered_at": db_order.delivered_at.isoformat() if db_order.delivered_at else None
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

    old_address = db_order.shipping_address
    db_order.shipping_address = payload.new_address
    
    # Create ShippingLog entry
    shipping_log = ShippingLog(
        user_id=db_order.user_id,
        order_id=db_order.order_id,
        old_shipping_add=old_address,
        new_shipping_add=payload.new_address
    )
    db.add(shipping_log)
    
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


@router.put("/{order_id}/cancel")
def cancel_order(order_id: str, db: Session = Depends(get_db)):
    """Cancels the given order in the database."""
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

    if db_order.status.lower() == "delivered":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order '{order_id}' cannot be cancelled because it has already been delivered."
        )
        
    if db_order.status.lower() == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order '{order_id}' is already cancelled."
        )

    old_status = db_order.status
    db_order.status = "cancelled"
    
    update_log = OrderUpdateLog(
        order_id=db_order.order_id,
        old_status=old_status,
        new_status="cancelled",
        reason="User requested cancellation"
    )
    db.add(update_log)
    
    db.commit()
    db.refresh(db_order)

    return {
        "status": "success",
        "message": f"Successfully cancelled order '{order_id}'.",
        "order": {
            "order_id": str(db_order.order_id),
            "user_id": str(db_order.user_id),
            "status": db_order.status,
            "product_name": db_order.product_name,
            "shipping_address": db_order.shipping_address
        }
    }

@router.post("/{order_id}/refund")
def process_refund(order_id: str, db: Session = Depends(get_db)):
    """Processes a refund for the given order."""
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

    # In a real system, you would call a payment gateway API here to process the refund.
    # For now, we update the status and return success.
    if db_order.status.lower() == "refunded":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order '{order_id}' has already been refunded."
        )

    old_status = db_order.status
    db_order.status = "refunded"
    
    update_log = OrderUpdateLog(
        order_id=db_order.order_id,
        old_status=old_status,
        new_status="refunded",
        reason="Automated refund processed via AI agent"
    )
    db.add(update_log)
    
    db.commit()
    db.refresh(db_order)

    return {
        "status": "success",
        "message": f"Successfully processed refund for order '{order_id}'.",
        "order": {
            "order_id": str(db_order.order_id),
            "user_id": str(db_order.user_id),
            "status": db_order.status,
            "product_name": db_order.product_name,
            "total_amount": float(db_order.total_amount)
        }
    }


@router.post("/{order_id}/replace")
def replace_order(order_id: str, payload: OrderReplace, db: Session = Depends(get_db)):
    """Processes a replacement/exchange for the given order."""
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

    if db_order.status.lower() in ["replaced", "refunded", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order '{order_id}' cannot be replaced because its status is '{db_order.status}'."
        )

    old_status = db_order.status
    db_order.status = "replaced"
    
    update_log = OrderUpdateLog(
        order_id=db_order.order_id,
        old_status=old_status,
        new_status="replaced",
        reason="Replacement/exchange processed via AI agent"
    )
    db.add(update_log)
    
    # Determine the product to reorder
    prod_name = payload.replacement_product_name or db_order.product_name
    from app.models.products import Product
    product = db.query(Product).filter(Product.name.ilike(f"%{prod_name}%")).first()
    
    # Create the new replacement order
    new_order = Order(
        user_id=db_order.user_id,
        product_name=product.name if product else prod_name,
        product_id=product.product_id if product else db_order.product_id,
        total_amount=product.price if product else db_order.total_amount,
        shipping_address=db_order.shipping_address,
        status="pending"
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    db.refresh(db_order)

    return {
        "status": "success",
        "message": f"Successfully processed replacement for order '{order_id}'.",
        "new_order_id": str(new_order.order_id),
        "order": {
            "order_id": str(db_order.order_id),
            "status": db_order.status,
            "product_name": db_order.product_name
        },
        "new_order": {
            "order_id": str(new_order.order_id),
            "status": new_order.status,
            "product_name": new_order.product_name,
            "total_amount": float(new_order.total_amount)
        }
    }

