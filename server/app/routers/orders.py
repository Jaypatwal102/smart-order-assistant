from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid

from app.database.connection import get_db
from app.database.tables.orders import Order, OrderStatus
from app.database.tables.audit_logs import AuditLog, ActionType
from app.database.data_types.orders import OrderCreate, OrderResponse
from app.database.tables.products import Product

router = APIRouter(prefix="/orders", tags=["orders"])


class AddressUpdate(BaseModel):
    new_address: str


class OrderReplace(BaseModel):
    replacement_pid: str | None = None


@router.post("", status_code=status.HTTP_201_CREATED, response_model=OrderResponse)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    """Creates a new order in the database."""
    db_order = Order(
        uid=payload.uid,
        pid=payload.pid,
        delivery_address=payload.delivery_address,
        delivery_date=payload.delivery_date,
        order_price=payload.order_price,
        order_status=payload.order_status or OrderStatus.ORDERED
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order


@router.get("", response_model=list[OrderResponse])
def list_orders(
    uid: str | None = None,
    payload: dict | None = Body(default=None),
    db: Session = Depends(get_db)
):
    """Lists all orders belonging to a specific user (uid)."""
    effective_uid = uid
    if not effective_uid and payload:
        effective_uid = payload.get("uid")

    if not effective_uid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="uid is required either as a query parameter (?uid=...) or in the JSON request body."
        )

    try:
        user_uuid = uuid.UUID(effective_uid.strip('"').strip("'"))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid uid format. Must be a valid UUID."
        )

    db_orders = db.query(Order).filter(Order.uid == user_uuid).all()
    return db_orders


@router.get("/{order_id}", response_model=OrderResponse)
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

    return db_order


@router.put("/{order_id}/address", response_model=OrderResponse)
def update_order_address(order_id: str, payload: AddressUpdate, db: Session = Depends(get_db)):
    """Updates the shipping address for the given order and creates an AuditLog."""
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

    old_address = db_order.delivery_address
    db_order.delivery_address = payload.new_address
    
    # Create AuditLog entry
    audit_log = AuditLog(
        uid=db_order.uid,
        order_id=db_order.order_id,
        action_type=ActionType.SHIPPING_ADDRESS_UPDATE,
        details=f"Address changed from '{old_address}' to '{payload.new_address}'",
    )
    db.add(audit_log)
    
    db.commit()
    db.refresh(db_order)
    return db_order


@router.put("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(order_id: str, db: Session = Depends(get_db)):
    """Cancels the given order and creates an AuditLog."""
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

    if db_order.order_status == OrderStatus.DELIVERED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order '{order_id}' cannot be cancelled because it has already been delivered."
        )
        
    if db_order.order_status == OrderStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order '{order_id}' is already cancelled."
        )

    db_order.order_status = OrderStatus.CANCELLED
    
    audit_log = AuditLog(
        uid=db_order.uid,
        order_id=db_order.order_id,
        action_type=ActionType.CANCEL_ORDER,
        details="User requested cancellation"
    )
    db.add(audit_log)
    
    db.commit()
    db.refresh(db_order)
    return db_order


@router.post("/{order_id}/refund", response_model=OrderResponse)
def process_refund(order_id: str, db: Session = Depends(get_db)):
    """Processes a refund for the given order and creates an AuditLog."""
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

    if db_order.order_status == OrderStatus.REFUNDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order '{order_id}' has already been refunded."
        )

    db_order.order_status = OrderStatus.REFUNDED
    
    audit_log = AuditLog(
        uid=db_order.uid,
        order_id=db_order.order_id,
        action_type=ActionType.REFUND_ORDER,
        details="Refund processed"
    )
    db.add(audit_log)
    
    db.commit()
    db.refresh(db_order)
    return db_order


@router.post("/{order_id}/replace")
def replace_order(order_id: str, payload: OrderReplace, db: Session = Depends(get_db)):
    """Processes a replacement/exchange for the given order and creates an AuditLog."""
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

    if db_order.order_status in [OrderStatus.REPLACED, OrderStatus.REFUNDED, OrderStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order '{order_id}' cannot be replaced because its status is '{db_order.order_status}'."
        )

    db_order.order_status = OrderStatus.REPLACED
    
    audit_log = AuditLog(
        uid=db_order.uid,
        order_id=db_order.order_id,
        action_type=ActionType.REPLACE_ORDER,
        details="Replacement processed"
    )
    db.add(audit_log)
    
    # Create the new replacement order
    new_pid = db_order.pid
    new_price = db_order.order_price
    
    if payload.replacement_pid:
        try:
            replacement_uuid = uuid.UUID(payload.replacement_pid)
            product = db.query(Product).filter(Product.pid == replacement_uuid).first()
            if product:
                new_pid = product.pid
                new_price = product.price
        except ValueError:
            pass

    new_order = Order(
        uid=db_order.uid,
        pid=new_pid,
        delivery_address=db_order.delivery_address,
        order_price=new_price,
        order_status=OrderStatus.ORDERED
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    db.refresh(db_order)

    return {
        "status": "success",
        "message": f"Successfully processed replacement for order '{order_id}'.",
        "new_order_id": str(new_order.order_id)
    }
