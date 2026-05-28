import asyncio
from collections.abc import Iterable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.database import Base, get_db
from models import Seat, SeatStatus, SeatType, Session
from routers.admin import router as admin_router
from routers.auth import router as auth_router
from routers.booking import router as booking_router
from routers.seats import router as seats_router
from routers.session import router as session_router


TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_cinemacon.sqlite3"

test_engine = create_async_engine(TEST_DATABASE_URL)
TestingSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def _run(coro):
    return asyncio.run(coro)


async def _reset_database() -> None:
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


@pytest.fixture(autouse=True)
def reset_database() -> None:
    _run(_reset_database())


@pytest.fixture(scope="session")
def app() -> FastAPI:
    app = FastAPI(title="CinemaCon Test API")

    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(session_router, prefix="/sessions", tags=["sessions"])
    app.include_router(booking_router, prefix="/bookings", tags=["bookings"])
    app.include_router(admin_router, prefix="/admin", tags=["admin"])
    app.include_router(seats_router, prefix="/seats", tags=["seats"])

    @app.get("/")
    def health_check():
        return {"message": "CinemaCon API is running!"}

    async def override_get_db():
        async with TestingSessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.fixture
def client(app: FastAPI) -> Iterable[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def seed_session():
    def _seed(
        movie_name: str = "Test Movie",
        rows: str = "AB",
        cols: range = range(1, 9),
        vip_rows: set[str] | None = None,
        vip_cols: set[int] | None = None,
        disability_positions: set[tuple[str, int]] | None = None,
        broken_positions: set[tuple[str, int]] | None = None,
    ) -> int:
        async def _insert() -> int:
            async with TestingSessionLocal() as db:
                session = Session(movie_name=movie_name)
                db.add(session)
                await db.flush()

                vip_rows_local = vip_rows or set()
                vip_cols_local = vip_cols or set()
                disability_local = disability_positions or set()
                broken_local = broken_positions or set()

                seats: list[Seat] = []
                for row in rows:
                    for col in cols:
                        position = (row, col)
                        if position in disability_local:
                            seat_type = SeatType.DISABILITY.value
                        elif row in vip_rows_local and col in vip_cols_local:
                            seat_type = SeatType.VIP.value
                        else:
                            seat_type = SeatType.REGULAR.value

                        status = (
                            SeatStatus.BROKEN.value
                            if position in broken_local
                            else SeatStatus.AVAILABLE.value
                        )
                        seats.append(
                            Seat(
                                session_id=session.id,
                                row=row,
                                col=col,
                                seat_type=seat_type,
                                status=status,
                            )
                        )

                db.add_all(seats)
                await db.commit()
                return session.id

        return _run(_insert())

    return _seed
