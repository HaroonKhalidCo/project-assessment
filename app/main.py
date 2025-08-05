from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Environment variable loading
load_dotenv()

from app.core.config import settings
from app.api.v1 import api_router_v1

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=settings.API_V1_STR
)

# CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router_v1, prefix=settings.API_V1_STR)

@app.get("/")
async def read_root():
    return {"message": f"Welcome to the {settings.PROJECT_NAME} API!"}