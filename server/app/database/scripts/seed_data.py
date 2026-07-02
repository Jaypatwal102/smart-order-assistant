# server/scripts/seed_data.py

import uuid
from decimal import Decimal
from datetime import datetime
from app.core.database import SessionLocal
from app.models.users import User
from app.models.orders import Order
from app.models.products import Product
from app.utils.password import get_password_hash


def seed():
    db = SessionLocal()

    # Clear existing data
    db.query(Order).delete()
    db.query(User).delete()
    db.query(Product).delete()
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

    # Seed Products
    products = {
        "Ceramide Moisturizer": Product(
            product_id=uuid.uuid4(),
            name="Ceramide Moisturizer",
            description="Deeply hydrating cream with ceramides and hyaluronic acid to repair the skin barrier. Ideal for dry and sensitive skin.",
            category="Moisturizer",
            price=Decimal("899.00"),
        ),
        "Vitamin C Serum": Product(
            product_id=uuid.uuid4(),
            name="Vitamin C Serum",
            description="Brightening serum with 10% pure Vitamin C and ferulic acid to fade dark spots and improve radiance.",
            category="Serum",
            price=Decimal("1299.00"),
        ),
        "Hydrating Face Wash": Product(
            product_id=uuid.uuid4(),
            name="Hydrating Face Wash",
            description="Gentle foaming face wash for dry to normal skin, free from sulfates and fragrance. Hydrates while cleansing.",
            category="Cleanser",
            price=Decimal("599.00"),
        ),
        "Night Repair Cream": Product(
            product_id=uuid.uuid4(),
            name="Night Repair Cream",
            description="Overnight nourishing cream with retinol and peptides to reduce fine lines and boost skin renewal.",
            category="Moisturizer",
            price=Decimal("1499.00"),
        ),
        "Aloe Vera Gel": Product(
            product_id=uuid.uuid4(),
            name="Aloe Vera Gel",
            description="Pure, soothing organic aloe vera gel to calm irritated, sunburned, or acne-prone skin.",
            category="Gel",
            price=Decimal("449.00"),
        ),
        "Retinol Serum": Product(
            product_id=uuid.uuid4(),
            name="Retinol Serum",
            description="Anti-aging serum with 0.5% retinol to smooth skin texture and improve firmness. Use at night.",
            category="Serum",
            price=Decimal("1399.00"),
        ),
        "Daily Cleanser": Product(
            product_id=uuid.uuid4(),
            name="Daily Cleanser",
            description="Daily gentle cleanser that removes oil, dirt, and light makeup without stripping skin moisture.",
            category="Cleanser",
            price=Decimal("699.00"),
        ),
        "Hyaluronic Acid Cream": Product(
            product_id=uuid.uuid4(),
            name="Hyaluronic Acid Cream",
            description="Lightweight gel-cream infused with multi-weight hyaluronic acid for instant plumping and long-lasting moisture.",
            category="Moisturizer",
            price=Decimal("1099.00"),
        ),
        "Sunscreen SPF 50": Product(
            product_id=uuid.uuid4(),
            name="Sunscreen SPF 50",
            description="Lightweight, non-greasy gel sunscreen protecting against UVA & UVB rays. Leaves no white cast.",
            category="Sunscreen",
            price=Decimal("699.00"),
        ),
        "Dry Skin Repair Lotion": Product(
            product_id=uuid.uuid4(),
            name="Dry Skin Repair Lotion",
            description="Intensive body and face lotion formulated to relieve extremely dry, flaky skin with urea and shea butter.",
            category="Lotion",
            price=Decimal("799.00"),
        ),
        # New products to facilitate recommendations/alternatives
        "Niacinamide Serum": Product(
            product_id=uuid.uuid4(),
            name="Niacinamide Serum",
            description="10% Niacinamide serum to control sebum production, minimize pore appearance, and reduce redness.",
            category="Serum",
            price=Decimal("999.00"),
        ),
        "Salicylic Acid Cleanser": Product(
            product_id=uuid.uuid4(),
            name="Salicylic Acid Cleanser",
            description="Exfoliating gel cleanser with 2% salicylic acid to unclog pores and combat acne breakouts.",
            category="Cleanser",
            price=Decimal("749.00"),
        ),
        "Peptide Moisturizer": Product(
            product_id=uuid.uuid4(),
            name="Peptide Moisturizer",
            description="Advanced anti-aging moisturizer packed with multi-peptides to firm, lift, and rejuvenate skin elasticity.",
            category="Moisturizer",
            price=Decimal("1599.00"),
        ),
    }

    db.add_all(products.values())
    db.commit()

    orders = [
        # Delivered today (22 Jun)
        Order(
            user_id=abhishek.user_id,
            status="delivered",
            product_name="Ceramide Moisturizer",
            product_id=products["Ceramide Moisturizer"].product_id,
            shipping_address="Pune, Maharashtra 411001",
            total_amount=Decimal("899.00"),
            ordered_at=datetime(2026, 6, 18),
            delivered_at=datetime(2026, 6, 22),
        ),
        Order(
            user_id=abhishek.user_id,
            status="delivered",
            product_name="Vitamin C Serum",
            product_id=products["Vitamin C Serum"].product_id,
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
            product_id=products["Hydrating Face Wash"].product_id,
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
            product_id=products["Night Repair Cream"].product_id,
            shipping_address="Bengaluru, Karnataka 560001",
            total_amount=Decimal("1499.00"),
            ordered_at=datetime(2026, 6, 15),
            delivered_at=datetime(2026, 6, 20),
        ),
        Order(
            user_id=abhishek.user_id,
            status="delivered",
            product_name="Aloe Vera Gel",
            product_id=products["Aloe Vera Gel"].product_id,
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
            product_id=products["Retinol Serum"].product_id,
            shipping_address="Nagpur, Maharashtra 440001",
            total_amount=Decimal("1399.00"),
            ordered_at=datetime(2026, 5, 18),
            delivered_at=datetime(2026, 5, 22),
        ),
        Order(
            user_id=abhishek.user_id,
            status="delivered",
            product_name="Daily Cleanser",
            product_id=products["Daily Cleanser"].product_id,
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
            product_id=products["Hyaluronic Acid Cream"].product_id,
            shipping_address="Chennai, Tamil Nadu 600028",
            total_amount=Decimal("1099.00"),
            ordered_at=datetime(2026, 6, 21),
            delivered_at=None,
        ),
        Order(
            user_id=abhishek.user_id,
            status="pending",
            product_name="Sunscreen SPF 50",
            product_id=products["Sunscreen SPF 50"].product_id,
            shipping_address="Jaipur, Rajasthan 302001",
            total_amount=Decimal("699.00"),
            ordered_at=datetime(2026, 6, 22),
            delivered_at=None,
        ),
        Order(
            user_id=abhishek.user_id,
            status="shipping",
            product_name="Dry Skin Repair Lotion",
            product_id=products["Dry Skin Repair Lotion"].product_id,
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