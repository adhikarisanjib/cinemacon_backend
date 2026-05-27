from pydantic import BaseModel
from pydantic import Field

from typing import List, Optional

from models import UserRole, Session, Booking


class RegisterForm(BaseModel):
    email: str
    name: str
    password: str
    role: UserRole = UserRole.STAFF


class LoginForm(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: UserRole

    class Config:
        from_attributes = True


class SessionForm(BaseModel):
    movie_name: str


class SessionResponse(BaseModel):
    id: int
    movie_name: str
    total_seats_count: int
    booked_seats_count: int
    available_seats_count: int
    occupancy_rate: float

    class Config:
        from_attributes = True


def serialize_session(session: Session) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        movie_name=session.movie_name,
        total_seats_count=session.total_seats_count(),
        booked_seats_count=session.booked_seats_count(),
        available_seats_count=session.available_seats_count(),
        occupancy_rate=session.occupancy_rate(),
    )


class BookingForm(BaseModel):
    name: str
    session_id: int
    group_size: int = Field(default=1, ge=1, le=7, description="Group size must be between 1 and 7 inclusive")
    seat_preference: str | None = Field(default=None, description="Preference: 'vip', 'regular', 'disability', or 'any'")
    regular_count: int = Field(default=0, ge=0, le=7, description="Mixed booking: number of regular seats")
    vip_count: int = Field(default=0, ge=0, le=7, description="Mixed booking: number of VIP seats")
    accessible_count: int = Field(default=0, ge=0, le=7, description="Mixed booking: number of accessibility seats")
    
    # If admin_override is True the caller can pin exact seats
    admin_override: bool = Field(
        default=False,
        description="If true, bypass all seating rules (admin only)"
    )
    pinned_seats: Optional[List[str]] = Field(
        default=None,
        description="Explicit seat IDs for admin override, e.g. ['A1','A2']"
    )


class BookingResponse(BaseModel):
    id: int
    name: str
    session_id: int
    group_size: int
    seat_preferences: Optional[str]
    seat_mix: Optional[str]
    booked_seats: List[str]

    class Config:
        from_attributes = True


def serialize_booking(booking: Booking) -> BookingResponse:
    return BookingResponse(
        id=booking.id,
        name=booking.name,
        session_id=booking.session_id,
        group_size=booking.group_size,
        seat_preferences=booking.seat_preferences,
        seat_mix=booking.seat_mix,
        booked_seats=[booked_seat.seat_number for booked_seat in booking.booked_seats],
    )


class SeatResponse(BaseModel):
    id: int
    session_id: int
    row: str
    col: int
    seat_type: str
    status: str

    class Config:
        from_attributes = True


class MarkBrokenSeatForm(BaseModel):
    session_id: int
    seat_ids: List[int]


class ResetSessionForm(BaseModel):
    session_id: int
