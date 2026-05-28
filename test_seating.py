import pytest

from models import Seat, SeatStatus, SeatType, Session
from services.seating_algorithm import (
	allocate_mixed_seats,
	allocate_seats,
	analyse_scatter,
	parse_seat_code,
)


def build_session(
	rows: str = "AB",
	cols: range = range(1, 9),
	vip_positions: set[tuple[str, int]] | None = None,
	disability_positions: set[tuple[str, int]] | None = None,
	booked_positions: set[tuple[str, int]] | None = None,
	broken_positions: set[tuple[str, int]] | None = None,
) -> Session:
	vip_positions = vip_positions or set()
	disability_positions = disability_positions or set()
	booked_positions = booked_positions or set()
	broken_positions = broken_positions or set()

	session = Session(id=1, movie_name="Test Session")
	seats: list[Seat] = []
	seat_id = 1
	for row in rows:
		for col in cols:
			position = (row, col)

			if position in disability_positions:
				seat_type = SeatType.DISABILITY.value
			elif position in vip_positions:
				seat_type = SeatType.VIP.value
			else:
				seat_type = SeatType.REGULAR.value

			if position in broken_positions:
				status = SeatStatus.BROKEN.value
			elif position in booked_positions:
				status = SeatStatus.BOOKED.value
			else:
				status = SeatStatus.AVAILABLE.value

			seats.append(
				Seat(
					id=seat_id,
					session_id=1,
					row=row,
					col=col,
					seat_type=seat_type,
					status=status,
				)
			)
			seat_id += 1

	session.seats = seats
	return session


def test_parse_seat_code_valid_and_invalid():
	assert parse_seat_code("a1") == ("A", 1)
	assert parse_seat_code("O28") == ("O", 28)

	with pytest.raises(ValueError):
		parse_seat_code("P1")

	with pytest.raises(ValueError):
		parse_seat_code("A29")

	with pytest.raises(ValueError):
		parse_seat_code("bad")


def test_allocate_seats_rejects_invalid_group_size():
	session = build_session()

	with pytest.raises(ValueError):
		allocate_seats(session=session, group_size=0, seat_preference="any")

	with pytest.raises(ValueError):
		allocate_seats(session=session, group_size=8, seat_preference="any")


def test_allocate_seats_vip_preference_uses_vip_when_available():
	session = build_session(
		rows="E",
		cols=range(10, 18),
		vip_positions={("E", 12), ("E", 13), ("E", 14), ("E", 15)},
	)

	booked = allocate_seats(session=session, group_size=2, seat_preference="vip")

	assert len(booked) == 2
	assert all(item.seat.seat_type == SeatType.VIP.value for item in booked)
	assert all(item.seat.status == SeatStatus.BOOKED.value for item in booked)


def test_allocate_seats_vip_falls_back_to_any_when_vip_full():
	session = build_session(
		rows="AE",
		cols=range(1, 9),
		vip_positions={("E", 2), ("E", 3)},
		booked_positions={("E", 2), ("E", 3)},
	)

	booked = allocate_seats(session=session, group_size=2, seat_preference="vip")

	assert len(booked) == 2
	assert all(item.seat.seat_type != SeatType.DISABILITY.value for item in booked)


def test_allocate_seats_admin_override_pins_exact_seats():
	session = build_session(rows="A", cols=range(1, 6))

	booked = allocate_seats(
		session=session,
		group_size=2,
		seat_preference="regular",
		admin_override=True,
		pinned_seats=["A2", "A4"],
	)

	assert [item.seat.seat_number for item in booked] == ["A2", "A4"]
	assert all(item.seat.status == SeatStatus.BOOKED.value for item in booked)


def test_allocate_mixed_seats_assigns_requested_types():
	session = build_session(
		rows="NE",
		cols=range(1, 7),
		vip_positions={("E", 2), ("E", 3), ("E", 4)},
		disability_positions={("N", 1), ("N", 2), ("N", 3)},
	)

	booked = allocate_mixed_seats(session=session, regular_count=2, vip_count=1, accessible_count=1)
	booked_types = [item.seat.seat_type for item in booked]

	assert len(booked) == 4
	assert booked_types.count(SeatType.REGULAR.value) == 2
	assert booked_types.count(SeatType.VIP.value) == 1
	assert booked_types.count(SeatType.DISABILITY.value) == 1


def test_allocate_mixed_seats_rolls_back_on_failure():
	session = build_session(
		rows="N",
		cols=range(1, 3),
		disability_positions={("N", 1)},
		booked_positions={("N", 2)},
	)

	with pytest.raises(ValueError):
		allocate_mixed_seats(session=session, regular_count=0, vip_count=1, accessible_count=1)

	accessible_seat = next(seat for seat in session.seats if (seat.row, seat.col) == ("N", 1))
	assert accessible_seat.status == SeatStatus.AVAILABLE.value


def test_analyse_scatter_detects_isolated_empty_seats():
	session = build_session(
		rows="A",
		cols=range(1, 6),
		booked_positions={("A", 1), ("A", 2), ("A", 4), ("A", 5)},
	)

	report = analyse_scatter(session)

	assert "A" in report
	isolated_ids = report["A"]
	assert len(isolated_ids) == 1
	isolated_seat = next(seat for seat in session.seats if seat.id == isolated_ids[0])
	assert (isolated_seat.row, isolated_seat.col) == ("A", 3)
