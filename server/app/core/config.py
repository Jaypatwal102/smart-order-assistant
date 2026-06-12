import os

from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:jay12345@localhost:5432/smart_order_assistant",
)
