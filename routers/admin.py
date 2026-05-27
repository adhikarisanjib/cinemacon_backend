from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload


from config.database import get_db
from models import Session, Booking, BookedSeat
from schemas import MarkBrokenSeatForm, serialize_session
from services.seat_initializer import build_seat_template


router = APIRouter(tags=["admin"])

@router.post("/mark-broken")
async def mark_broken_seat(data: MarkBrokenSeatForm, db: AsyncSession = Depends(get_db)):
    session = await db.execute(
        select(Session)
        .options(selectinload(Session.seats))
        .where(Session.id == data.session_id)
    )
    session = session.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    for seat_id in data.seat_ids:
        seat = next((s for s in session.seats if s.id == seat_id), None)
        if not seat:
            raise HTTPException(status_code=404, detail=f"Seat with id {seat_id} not found in session")
        seat.is_broken = True
        db.add(seat)

    await db.commit()

    return {"message": "Seats marked as broken successfully"}


@router.post("/reset-session")
async def reset_session(data: int, db: AsyncSession = Depends(get_db)):
    session = await db.execute(
        select(Session)
        .options(selectinload(Session.seats))
        .where(Session.id == data)
    )
    session = session.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    bookings = await db.execute(select(Booking).where(Booking.session_id == session.id))
    for booking in bookings.scalars().all():
        await db.delete(booking)
    
    seats = await db.execute(select(BookedSeat).where(BookedSeat.session_id == session.id))
    for booked_seat in seats.scalars().all():
        await db.delete(booked_seat)
    

    seat_template = build_seat_template(session_id=session.id)
    db.add_all(seat_template)
    await db.commit() 

    result = await db.execute(
        select(Session)
        .options(selectinload(Session.seats))
        .where(Session.id == session.id)
    )
    session = result.scalar_one()

    return serialize_session(session)


@router.get("/sessions/stats/{session_id}")
async def get_session_stats(session_id: int, db: AsyncSession = Depends(get_db)):
    session = await db.execute(
        select(Session)
        .options(selectinload(Session.seats))
        .where(Session.id == session_id)
    )
    session = session.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    breakdown = {}
    for seat in session.seats:
        breakdown.setdefault(seat.seat_type, {}).setdefault(seat.status, 0)
        breakdown[seat.seat_type][seat.status] += 1

    return {
        "session_id": session_id,
        "movie_name": session.movie_name,
        "occupancy_rate": session.occupancy_rate(),
        "breakdown": breakdown,
    }