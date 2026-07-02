import os
import sys

# Add the root directory to PYTHONPATH so imports work correctly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from app.database.connection import Base, engine
from app.database.tables.users import User
from app.database.tables.orders import Order
from app.database.tables.products import Product
from app.database.tables.messages import Message
from app.database.tables.conversations import Conversation
from app.database.tables.audit_logs import AuditLog

from app.database.scripts.seed_data import seed

def reset_db():
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)

    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)

    print("Seeding database...")
    seed()

    print("Database reset complete.")

if __name__ == "__main__":
    reset_db()
