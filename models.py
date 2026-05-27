from enum import Enum
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint

from config.database import Base


class UserRole(str, Enum):
    STAFF = "staff"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    role: Mapped[UserRole] = mapped_column(String, default=UserRole.STAFF.value)

    def __str__(self):
        return self.name
    

class SeatType(str, Enum):
    REGULAR = "regular"
    VIP = "vip"
    DISABILITY = "disability"
    BROKEN = "broken"


class SeatStatus(str, Enum):
    AVAILABLE = "available"
    BOOKED = "booked"
    BROKEN = "broken"
    RESERVED = "reserved"
    

class Session(Base):
    __tablename__ = "sessions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    movie_name: Mapped[str] = mapped_column(String(255), index=True)

    seats = relationship("Seat", back_populates="session", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="session", cascade="all, delete-orphan")

    def __str__(self):
        return self.movie_name
    
    def total_seats_count(self) -> int:
        return len(self.seats)
    
    def booked_seats_count(self) -> int:
        return sum(1 for seat in self.seats if seat.status == SeatStatus.BOOKED.value)
    
    def available_seats_count(self) -> int:
        return sum(1 for seat in self.seats if seat.status == SeatStatus.AVAILABLE.value)
    
    def occupancy_rate(self) -> float:
        total = self.total_seats_count()
        if total == 0:
            return 0.0
        return (self.booked_seats_count() / total) * 100
    
    def is_seat_available(self, row: str, col: int) -> bool:
        for seat in self.seats:
            if seat.row == row and seat.col == col:
                return seat.is_available
        return False
    

class Seat(Base):
    __tablename__ = "seats"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id"))
    row: Mapped[str] = mapped_column(String(2), nullable=False)
    col: Mapped[int] = mapped_column(Integer, nullable=False)
    seat_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")

    session: Mapped["Session"] = relationship("Session", back_populates="seats")

    @property
    def seat_number(self) -> str:
        return f"{self.row}{self.col}"
    
    @property
    def is_available(self) -> bool:
        return self.status == SeatStatus.AVAILABLE.value
    

class Booking(Base):
    __tablename__ = "bookings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    group_size: Mapped[int] = mapped_column(Integer, nullable=False)
    seat_preferences: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    seat_mix: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    allocation_notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_cancelled: Mapped[bool] = mapped_column(default=False)

    session: Mapped["Session"] = relationship("Session", back_populates="bookings")

    booked_seats: Mapped[list["BookedSeat"]] = relationship("BookedSeat", back_populates="booking", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("session_id", "name", name="unique_booking_name_per_session"),
    )


class BookedSeat(Base):
    __tablename__ = "booking_seats"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    booking_id: Mapped[int] = mapped_column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    seat_id: Mapped[int] = mapped_column(Integer, ForeignKey("seats.id", ondelete="CASCADE"), nullable=False)

    booking: Mapped["Booking"] = relationship("Booking", back_populates="booked_seats")
    seat: Mapped["Seat"] = relationship("Seat")

    @property
    def seat_number(self) -> str:
        return self.seat.seat_number

    __table_args__ = (
        UniqueConstraint("session_id", "seat_id", name="unique_seat_booking"),
    )