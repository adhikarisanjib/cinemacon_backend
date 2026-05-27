from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload


from config.database import get_db
from models import Session, Booking, BookedSeat
from schemas import BookingForm, BookingResponse, serialize_booking
from services.seating_algorithm import allocate_seats, allocate_mixed_seats


VALID_PREFERENCES = {
    "vip", 
    "regular",
    "disability", 
    "any"
}


router = APIRouter(tags=["bookings"])


@router.post("/", response_model=BookingResponse)
async def create_booking(data: BookingForm, db: AsyncSession = Depends(get_db)) -> BookingResponse:
    seat_preference = (data.seat_preference or "any").lower()
    if seat_preference not in VALID_PREFERENCES:
        raise HTTPException(status_code=400, detail="Invalid seat preference")
    
    session = await db.execute(
        select(Session)
        .options(selectinload(Session.seats))
        .where(Session.id == data.session_id)
    )
    session = session.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if data.admin_override and data.pinned_seats:
        if len(data.pinned_seats) > data.group_size:
            raise HTTPException(status_code=400, detail="Pinned seats cannot exceed group size")
        
    mixed_total = data.regular_count + data.vip_count + data.accessible_count
    is_mixed_request = mixed_total > 0

    if is_mixed_request and data.admin_override:
        raise HTTPException(status_code=400, detail="admin_override is not supported for mixed booking requests")
    if is_mixed_request and data.pinned_seats:
        raise HTTPException(status_code=400, detail="pinned_seats is not supported for mixed booking requests")
    if is_mixed_request and (mixed_total < 1 or mixed_total > 7):
        raise HTTPException(status_code=400, detail="Mixed booking total must be between 1 and 7 seats")
    if is_mixed_request and data.group_size != mixed_total:
        raise HTTPException(status_code=400, detail="group_size must equal regular_count + vip_count + accessible_count for mixed bookings")
    

    booking = Booking(
        name=data.name,
        session_id=data.session_id,
        group_size=(mixed_total if is_mixed_request else data.group_size),
        seat_preferences=seat_preference,
        seat_mix=(
            f"regular={data.regular_count},vip={data.vip_count},accessible={data.accessible_count}"
            if is_mixed_request
            else None
        ),
    )
    db.add(booking)

    try:
        if is_mixed_request:
            booked_recommendation = allocate_mixed_seats(
                session=session,
                regular_count=data.regular_count,
                vip_count=data.vip_count,
                accessible_count=data.accessible_count,
            )
        else:
            booked_recommendation = allocate_seats(
                session=session,
                group_size=data.group_size,
                seat_preference=seat_preference,
                admin_override=data.admin_override,
                pinned_seats=data.pinned_seats,
            )

        booking.booked_seats = booked_recommendation
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A booking with this name already exists for this session. Use a different booking name.",
        )
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))

    result = await db.execute(
        select(Booking)
        .options(selectinload(Booking.booked_seats).selectinload(BookedSeat.seat))
        .where(Booking.id == booking.id)
    )
    booking = result.scalar_one()

    return serialize_booking(booking)


@router.delete("/cancel/{booking_id}", status_code=204)
async def cancel_booking(booking_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    await db.delete(booking)
    await db.commit()
    
    return


@router.get("/{session_id}", response_model=list[BookingResponse])
async def list_bookings(session_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Booking)
        .where(Booking.session_id == session_id)
        .options(selectinload(Booking.booked_seats).selectinload(BookedSeat.seat))
    )
    bookings = result.scalars().all()
    
    return [serialize_booking(booking) for booking in bookings]
