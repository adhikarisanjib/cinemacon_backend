from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import models
from config.settings import settings
from config.database import engine, Base

from routers.auth import router as auth_router
from routers.booking import router as booking_router
from routers.session import router as session_router
from routers.admin import router as admin_router
from routers.seats import router as seats_router


# Create tables on startup
async def create_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await create_tables()
    yield
    await engine.dispose()


app = FastAPI(title="CinemaCon API", lifespan=lifespan)
app.mount("/media", StaticFiles(directory=settings.MEDIA_DIR), name="media")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(session_router, prefix="/sessions", tags=["sessions"])
app.include_router(booking_router, prefix="/bookings", tags=["bookings"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])
app.include_router(seats_router, prefix="/seats", tags=["seats"])


@app.get("/")
def health_check():
    return {"message": "CinemaCon API is running!"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
