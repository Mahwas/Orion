from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import routes
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Orion Shopping Assistant API")

# Allow all origins for the MVP/hackathon
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
    return {"status": "ok"}
