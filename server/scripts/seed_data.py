# server/scripts/seed_data.py

import uuid
from decimal import Decimal
from datetime import datetime
from app.core.database import SessionLocal
from app.models.users import User
from app.models.orders import Order
from app.utils.password import get_password_hash


def seed():
    db = SessionLocal()

    # Clear existing data (optional)
    db.query(Order).delete()
    db.query(User).delete()
    db.commit()

    # Users
    abhishek = User(
        user_id=uuid.uuid4(),
        first_name="Abhishek",
        last_name="Kumbhar",
        email="kumbharabhishek2004@gmail.com",
        password_hash=get_password_hash("password123"),
        role="customer",
    )

    jelle = User(
        user_id=uuid.uuid4(),
        first_name="Jelle",
        last_name="Vukth",
        email="jellevanvukth303@gmail.com",
        password_hash=get_password_hash("password123"),
        role="human_agent",
    )

    db.add(abhishek)
    db.add(jelle)
    db.commit()

    orders = [
        # Delivered today (22 Jun)
        Order(
            user_id=abhishek.user_id,
            status="delivered",
            product_name="Ceramide Moisturizer",
            shipping_address="Pune, Maharashtra 411001",
            total_amount=Decimal("899.00"),
            ordered_at=datetime(2026, 6, 18),
            delivered_at=datetime(2026, 6, 22),
        ),
        Order(
            user_id=abhishek.user_id,
            status="delivered",
            product_name="Vitamin C Serum",
            shipping_address="Mumbai, Maharashtra 400001",
            total_amount=Decimal("1299.00"),
            ordered_at=datetime(2026, 6, 17),
            delivered_at=datetime(2026, 6, 22),
        ),

        # Delivered yesterday (21 Jun)
        Order(
            user_id=abhishek.user_id,
            status="delivered",
            product_name="Hydrating Face Wash",
            shipping_address="Nashik, Maharashtra 422003",
            total_amount=Decimal("599.00"),
            ordered_at=datetime(2026, 6, 16),
            delivered_at=datetime(2026, 6, 21),
        ),

        # Delivered day before yesterday (20 Jun)
        Order(
            user_id=abhishek.user_id,
            status="delivered",
            product_name="Night Repair Cream",
            shipping_address="Bengaluru, Karnataka 560001",
            total_amount=Decimal("1499.00"),
            ordered_at=datetime(2026, 6, 15),
            delivered_at=datetime(2026, 6, 20),
        ),
        Order(
            user_id=abhishek.user_id,
            status="delivered",
            product_name="Aloe Vera Gel",
            shipping_address="Hyderabad, Telangana 500081",
            total_amount=Decimal("449.00"),
            ordered_at=datetime(2026, 6, 14),
            delivered_at=datetime(2026, 6, 20),
        ),

        # Delivered one month ago
        Order(
            user_id=abhishek.user_id,
            status="delivered",
            product_name="Retinol Serum",
            shipping_address="Nagpur, Maharashtra 440001",
            total_amount=Decimal("1399.00"),
            ordered_at=datetime(2026, 5, 18),
            delivered_at=datetime(2026, 5, 22),
        ),
        Order(
            user_id=abhishek.user_id,
            status="delivered",
            product_name="Daily Cleanser",
            shipping_address="Delhi 110001",
            total_amount=Decimal("699.00"),
            ordered_at=datetime(2026, 5, 17),
            delivered_at=datetime(2026, 5, 22),
        ),

        # Not delivered
        Order(
            user_id=abhishek.user_id,
            status="pending",
            product_name="Hyaluronic Acid Cream",
            shipping_address="Chennai, Tamil Nadu 600028",
            total_amount=Decimal("1099.00"),
            ordered_at=datetime(2026, 6, 21),
            delivered_at=None,
        ),
        Order(
            user_id=abhishek.user_id,
            status="pending",
            product_name="Sunscreen SPF 50",
            shipping_address="Jaipur, Rajasthan 302001",
            total_amount=Decimal("699.00"),
            ordered_at=datetime(2026, 6, 22),
            delivered_at=None,
        ),
        Order(
            user_id=abhishek.user_id,
            status="shipping",
            product_name="Dry Skin Repair Lotion",
            shipping_address="Kochi, Kerala 682001",
            total_amount=Decimal("799.00"),
            ordered_at=datetime(2026, 6, 19),
            delivered_at=None,
        ),
    ]

    db.add_all(orders)
    db.commit()

    print("Seed data inserted successfully.")
    print(f"Abhishek User ID: {abhishek.user_id}")
    print(f"Jelle User ID: {jelle.user_id}")

    db.close()


if __name__ == "__main__":
    seed()