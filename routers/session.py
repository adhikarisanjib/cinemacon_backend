from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from config.database import get_db
from models import Session
from schemas import SessionResponse, SessionForm, serialize_session
from services.seat_initializer import build_seat_template


router = APIRouter(tags=["sessions"])


@router.get("/", response_model=list[SessionResponse])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).options(selectinload(Session.seats)))
    sessions = result.scalars().all()
    
    return [serialize_session(session) for session in sessions]


@router.post("/", response_model=SessionResponse)
async def create_session(session_form: SessionForm, db: AsyncSession = Depends(get_db)):

    session = Session(movie_name=session_form.movie_name)
    db.add(session)
    await db.commit()
    await db.refresh(session)

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


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Session)
        .options(selectinload(Session.seats))
        .where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return serialize_session(session)


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await db.delete(session)
    await db.commit()
    
    return