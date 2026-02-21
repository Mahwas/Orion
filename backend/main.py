from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import routes
from core.database import engine, Base
from dotenv import load_dotenv

load_dotenv()

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Orion LangGraph Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "ok", "agent": "LangGraph Active"}
