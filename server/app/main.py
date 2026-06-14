from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth
from app.core.database import create_tables

create_tables()

app = FastAPI(title="Smart Order Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.routers import auth, conversations

app.include_router(auth.router)
app.include_router(conversations.router)

@app.get("/")
def root():
    return {"message": "Welcome to Smart Order Assistant API"}
