from dotenv import load_dotenv
load_dotenv()  # Must run before API imports that read env vars

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import routes
from api.billing import billing_router
from api.webhooks import webhook_router
from api.issuing import issuing_router
from database import engine, Base

# Import ORM models so Base.metadata knows about all tables
import models.orm        # noqa: F401
import models.db_models  # noqa: F401

@asynccontextmanager
async def lifespan(app):
    # Startup: create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown: (nothing to clean up for now)

app = FastAPI(title="Orion LangGraph Agent API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Existing agent / transaction routes
app.include_router(routes.router, prefix="/api/v1")

# Stripe billing – Checkout Session creation
app.include_router(billing_router)

# Stripe webhooks – event ingestion
app.include_router(webhook_router)

# Stripe Issuing – one-time virtual card generation
app.include_router(issuing_router)


@app.get("/health")
def health_check():
    return {"status": "ok", "agent": "LangGraph Active"}
