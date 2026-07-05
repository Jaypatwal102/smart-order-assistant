# Complete replacement for seed.py

import uuid
from datetime import datetime, timedelta

from app.database.connection import SessionLocal
from app.database.tables.users import User, UserRole
from app.database.tables.orders import Order, OrderStatus
from app.database.tables.products import Product, ProductType
from app.utils.password import get_password_hash


def seed():
    db = SessionLocal()

    db.query(Order).delete()
    db.query(User).delete()
    db.query(Product).delete()
    db.commit()

    abhishek = User(
        uid=uuid.uuid4(),
        first_name="Abhishek",
        last_name="Kumbhar",
        email="user@gmail.com",
        hashed_password=get_password_hash("password123"),
        role=UserRole.USER,
    )

    jelle = User(
        uid=uuid.uuid4(),
        first_name="Jelle",
        last_name="Vukth",
        email="agent@gmail.com",
        hashed_password=get_password_hash("password123"),
        role=UserRole.HUMAN_AGENT,
    )

    db.add_all([abhishek, jelle])
    db.commit()

    def p(name, desc, t, price):
        return Product(
            pid=uuid.uuid4(),
            product_name=name,
            description=desc,
            product_type=t,
            price=price,
        )

    products = {
        # ---------------- COSMETICS (7) ----------------
        "CeraVe Face Wash": p("CeraVe Hydrating Face Wash","Hydrating cleanser.",ProductType.COSMETIC,699),
        "Cetaphil Face Wash": p("Cetaphil Gentle Skin Cleanser","Gentle cleanser.",ProductType.COSMETIC,649),
        "Minimalist Face Wash": p("Minimalist Oat Cleanser","Daily cleanser.",ProductType.COSMETIC,599),
        "Vitamin C Serum": p("Vitamin C Serum","Brightening serum.",ProductType.COSMETIC,1299),
        "Ceramide Moisturizer": p("Ceramide Moisturizer","Barrier repair moisturizer.",ProductType.COSMETIC,899),
        "Sunscreen SPF 50": p("Sunscreen SPF 50","Broad spectrum sunscreen.",ProductType.COSMETIC,799),
        "Lip Balm": p("Lip Balm","Moisturizing lip balm.",ProductType.COSMETIC,249),

        # ---------------- ELECTRONICS (7) ----------------
        "Logitech Mouse": p("Logitech Wireless Mouse","2.4GHz wireless mouse.",ProductType.ELECTRONIC,999),
        "HP Mouse": p("HP Wireless Mouse","Wireless optical mouse.",ProductType.ELECTRONIC,949),
        "Dell Mouse": p("Dell Wireless Mouse","Compact wireless mouse.",ProductType.ELECTRONIC,979),
        "Logitech Keyboard": p("Logitech Mechanical Keyboard","Mechanical keyboard.",ProductType.ELECTRONIC,3499),
        "Amazon Washing Machine": p("Amazon Basics Washing Machine","Front load washing machine.",ProductType.ELECTRONIC,23999),
        "Sony Earbuds": p("Sony Wireless Earbuds","Noise cancelling earbuds.",ProductType.ELECTRONIC,4999),
        "Anker Power Bank": p("Anker Power Bank","20000mAh power bank.",ProductType.ELECTRONIC,1999),

        # ---------------- FOOD (8) ----------------
        "Dabur Honey": p("Dabur Honey","Pure honey.",ProductType.FOOD,399),
        "Patanjali Honey": p("Patanjali Honey","Natural honey.",ProductType.FOOD,379),
        "Organic India Honey": p("Organic India Honey","Organic honey.",ProductType.FOOD,449),
        "Green Tea": p("Green Tea","Premium green tea.",ProductType.FOOD,299),
        "Protein Bars": p("Protein Bars","Pack of 6 bars.",ProductType.FOOD,799),
        "Basmati Rice": p("Basmati Rice 5kg","Premium rice.",ProductType.FOOD,699),
        "Almonds": p("California Almonds","500g almonds.",ProductType.FOOD,849),
        "Peanut Butter": p("Peanut Butter","Crunchy peanut butter.",ProductType.FOOD,349),
    }

    db.add_all(products.values())
    db.commit()

    now = datetime.now()

    orders = [
        Order(
            uid=abhishek.uid,
            pid=products["Ceramide Moisturizer"].pid,
            delivery_address="Pune, Maharashtra",
            order_price=products["Ceramide Moisturizer"].price,
            order_status=OrderStatus.DELIVERED,
            delivery_date=now - timedelta(days=1),
        ),
        Order(
            uid=abhishek.uid,
            pid=products["Logitech Mouse"].pid,
            delivery_address="Mumbai, Maharashtra",
            order_price=products["Logitech Mouse"].price,
            order_status=OrderStatus.DELIVERED,
            delivery_date=now - timedelta(days=10),
        ),
        Order(
            uid=abhishek.uid,
            pid=products["Sony Earbuds"].pid,
            delivery_address="Bengaluru, Karnataka",
            order_price=products["Sony Earbuds"].price,
            order_status=OrderStatus.ORDERED,
            delivery_date=now + timedelta(days=8),
        ),
        Order(
            uid=abhishek.uid,
            pid=products["Organic India Honey"].pid,
            delivery_address="Hyderabad, Telangana",
            order_price=products["Organic India Honey"].price,
            order_status=OrderStatus.ORDERED,
            delivery_date=now + timedelta(days=8),
        ),
        Order(
            uid=abhishek.uid,
            pid=products["HP Mouse"].pid,
            delivery_address="Delhi",
            order_price=products["HP Mouse"].price,
            order_status=OrderStatus.DISPATCHED,
            delivery_date=now + timedelta(days=4),
        ),
        Order(
            uid=abhishek.uid,
            pid=products["Vitamin C Serum"].pid,
            delivery_address="Chennai, Tamil Nadu",
            order_price=products["Vitamin C Serum"].price,
            order_status=OrderStatus.CANCELLED,
            delivery_date=None,
        ),
    ]

    db.add_all(orders)
    db.commit()

    print("Seed data inserted successfully.")
    db.close()


if __name__ == "__main__":
    seed()
