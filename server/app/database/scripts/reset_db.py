from app.core.database import Base, engine, create_tables

# Import all models so SQLAlchemy knows about them
from app.models import *  # noqa

from scripts.seed_data import seed


def reset_db():
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)

    print("Creating all tables...")
    create_tables()

    print("Seeding database...")
    seed()

    print("Database reset complete.")


if __name__ == "__main__":
    reset_db()