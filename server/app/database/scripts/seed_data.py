import uuid
from datetime import datetime
from app.database.connection import SessionLocal
from app.database.tables.users import User, UserRole
from app.database.tables.orders import Order, OrderStatus
from app.database.tables.products import Product, ProductType
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
        uid=uuid.uuid4(),
        first_name="Abhishek",
        last_name="Kumbhar",
        email="kumbharabhishek2004@gmail.com",
        hashed_password=get_password_hash("password123"),
        role=UserRole.USER,
    )

    jelle = User(
        uid=uuid.uuid4(),
        first_name="Jelle",
        last_name="Vukth",
        email="jellevanvukth303@gmail.com",
        hashed_password=get_password_hash("password123"),
        role=UserRole.HUMAN_AGENT,
    )

    db.add(abhishek)
    db.add(jelle)
    db.commit()

    # Seed Products
    products = {
        "Ceramide Moisturizer": Product(
            pid=uuid.uuid4(),
            product_name="Ceramide Moisturizer",
            description="Deeply hydrating cream with ceramides and hyaluronic acid to repair the skin barrier. Ideal for dry and sensitive skin.",
            product_type=ProductType.COSMETIC,
            price=899.00,
        ),
        "Vitamin C Serum": Product(
            pid=uuid.uuid4(),
            product_name="Vitamin C Serum",
            description="Brightening serum with 10% pure Vitamin C and ferulic acid to fade dark spots and improve radiance.",
            product_type=ProductType.COSMETIC,
            price=1299.00,
        ),
        "Hydrating Face Wash": Product(
            pid=uuid.uuid4(),
            product_name="Hydrating Face Wash",
            description="Gentle foaming face wash for dry to normal skin, free from sulfates and fragrance. Hydrates while cleansing.",
            product_type=ProductType.COSMETIC,
            price=599.00,
        ),
        "Wireless Earbuds": Product(
            pid=uuid.uuid4(),
            product_name="Wireless Earbuds",
            description="True wireless earbuds with active noise cancellation and 24-hour battery life.",
            product_type=ProductType.ELECTRONIC,
            price=2999.00,
        ),
        "Smart Watch": Product(
            pid=uuid.uuid4(),
            product_name="Smart Watch",
            description="Fitness tracker with heart rate monitor, sleep tracking, and built-in GPS.",
            product_type=ProductType.ELECTRONIC,
            price=4999.00,
        ),
        "Power Bank": Product(
            pid=uuid.uuid4(),
            product_name="Power Bank",
            description="10000mAh portable charger with fast charging and dual USB ports.",
            product_type=ProductType.ELECTRONIC,
            price=999.00,
        ),
        "Laptop Stand": Product(
            pid=uuid.uuid4(),
            product_name="Laptop Stand",
            description="Adjustable aluminum laptop stand for ergonomic viewing and typing.",
            product_type=ProductType.ELECTRONIC,
            price=1499.00,
        ),
        "Organic Honey": Product(
            pid=uuid.uuid4(),
            product_name="Organic Honey",
            description="Pure, raw, unfiltered organic honey sourced from local farms.",
            product_type=ProductType.FOOD,
            price=399.00,
        ),
        "Green Tea": Product(
            pid=uuid.uuid4(),
            product_name="Green Tea",
            description="Premium organic green tea leaves rich in antioxidants.",
            product_type=ProductType.FOOD,
            price=299.00,
        ),
        "Protein Bars": Product(
            pid=uuid.uuid4(),
            product_name="Protein Bars",
            description="Pack of 6 protein bars with 20g protein and low sugar content.",
            product_type=ProductType.FOOD,
            price=799.00,
        ),
    }

    db.add_all(products.values())
    db.commit()

    # 10 Orders with various statuses
    orders = [
        Order(
            uid=abhishek.uid,
            pid=products["Ceramide Moisturizer"].pid,
            delivery_address="Pune, Maharashtra 411001",
            order_price=products["Ceramide Moisturizer"].price,
            order_status=OrderStatus.DELIVERED,
            delivery_date=datetime(2026, 6, 22),
        ),
        Order(
            uid=abhishek.uid,
            pid=products["Wireless Earbuds"].pid,
            delivery_address="Mumbai, Maharashtra 400001",
            order_price=products["Wireless Earbuds"].price,
            order_status=OrderStatus.ORDERED,
            delivery_date=None,
        ),
        Order(
            uid=abhishek.uid,
            pid=products["Organic Honey"].pid,
            delivery_address="Nashik, Maharashtra 422003",
            order_price=products["Organic Honey"].price,
            order_status=OrderStatus.DISPATCHED,
            delivery_date=None,
        ),
        Order(
            uid=abhishek.uid,
            pid=products["Smart Watch"].pid,
            delivery_address="Bengaluru, Karnataka 560001",
            order_price=products["Smart Watch"].price,
            order_status=OrderStatus.ORDERED,
            delivery_date=None,
        ),
        Order(
            uid=abhishek.uid,
            pid=products["Hydrating Face Wash"].pid,
            delivery_address="Hyderabad, Telangana 500081",
            order_price=products["Hydrating Face Wash"].price,
            order_status=OrderStatus.REPLACED,
            delivery_date=None,
        ),
        Order(
            uid=abhishek.uid,
            pid=products["Protein Bars"].pid,
            delivery_address="Nagpur, Maharashtra 440001",
            order_price=products["Protein Bars"].price,
            order_status=OrderStatus.ORDERED,
            delivery_date=None,
        ),
        Order(
            uid=abhishek.uid,
            pid=products["Laptop Stand"].pid,
            delivery_address="Delhi 110001",
            order_price=products["Laptop Stand"].price,
            order_status=OrderStatus.DELIVERED,
            delivery_date=datetime(2026, 5, 22),
        ),
        Order(
            uid=abhishek.uid,
            pid=products["Green Tea"].pid,
            delivery_address="Chennai, Tamil Nadu 600028",
            order_price=products["Green Tea"].price,
            order_status=OrderStatus.ORDERED,
            delivery_date=None,
        ),
        Order(
            uid=abhishek.uid,
            pid=products["Power Bank"].pid,
            delivery_address="Jaipur, Rajasthan 302001",
            order_price=products["Power Bank"].price,
            order_status=OrderStatus.DISPATCHED,
            delivery_date=None,
        ),
        Order(
            uid=abhishek.uid,
            pid=products["Vitamin C Serum"].pid,
            delivery_address="Kochi, Kerala 682001",
            order_price=products["Vitamin C Serum"].price,
            order_status=OrderStatus.REPLACED,
            delivery_date=None,
        ),
    ]

    db.add_all(orders)
    db.commit()

    print("Seed data inserted successfully.")

    db.close()


if __name__ == "__main__":
    seed()