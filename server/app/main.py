from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, orders, conversations
from app.core.database import create_tables
from fastapi.staticfiles import StaticFiles
import os

create_tables()

app = FastAPI(title="Smart Order Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("audios", exist_ok=True)
app.mount("/audios", StaticFiles(directory="audios"), name="audios")

app.include_router(auth.router)
app.include_router(conversations.router)
app.include_router(orders.router)

@app.get("/")
def root():
    return {"message": "Welcome to Smart Order Assistant API"}
