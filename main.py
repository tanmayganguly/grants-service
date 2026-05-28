from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.grants import router as grants_router
from app.core.config import settings
from app.core.logging import configure_logging, logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(debug=settings.DEBUG)
    logger.info("startup", database_url=settings.DATABASE_URL.split("@")[-1])
    yield
    logger.info("shutdown")


app = FastAPI(
    title="Document Access Grant Service",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(grants_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
