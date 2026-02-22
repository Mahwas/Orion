from dotenv import load_dotenv
load_dotenv()  # Must run before API imports that read env vars

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import routes
from api.billing import billing_router
from api.webhooks import webhook_router
from database import engine, Base

app = FastAPI(title="Orion LangGraph Agent API")

@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        # This will create all tables defined in models that share the same Base
        await conn.run_sync(Base.metadata.create_all)

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


@app.get("/health")
def health_check():
    return {"status": "ok", "agent": "LangGraph Active"}
