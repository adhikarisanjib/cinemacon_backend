from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


from config.database import get_db
from models import Seat, Session
from schemas import SeatResponse
from services.seating_algorithm import analyse_scatter


router = APIRouter(tags=["seats"])


@router.get("/{session_id}/scatter-report")
async def scatter_report(session_id: str, db: AsyncSession = Depends(get_db)):
    """
    Diagnostic: returns rows that currently have isolated single empty seats.
    Useful for stress-testing the algorithm.
    """
    session = await db.execute(
        select(Session)
        .options(selectinload(Session.seats))
        .where(Session.id == session_id)
    )
    session = session.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    report = analyse_scatter(session)
    total_isolated = sum(len(isolated_seats) for isolated_seats in report.values())
    return {
        "session_id": session_id,
        "total_isolated_seats": total_isolated,
        "rows_affected": report
    }

@router.get("/{session_id}/seats", response_model=list[SeatResponse])
async def list_seats(session_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Seat).where(Seat.session_id == session_id)
    )
    seats = result.scalars().all()
    
    return seats


@router.get("/{session_id}/{seat_id}", response_model=SeatResponse)
async def get_seat(session_id: int, seat_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Seat).where(Seat.session_id == session_id, Seat.id == seat_id)
    )
    seat = result.scalar_one_or_none()
    if not seat:
        raise HTTPException(status_code=404, detail="Seat not found")
    return seat
