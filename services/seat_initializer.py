import random
from models import Seat, SeatType, SeatStatus


ROWS = list("ABCDEFGHIJKLMNO")
COLS = list(range(1, 29)) 

VIP_ROWS = set("EFGHI")
VIP_COLS = {12, 13, 14, 15}

def generate_disability_seats() -> list[tuple[str, int]]:
    candidate_pairs = [
        [("N", 1), ("N", 2)],
        [("N", 27), ("N", 28)],
        [("O", 1), ("O", 2)],
        [("O", 27), ("O", 28)],
    ]
    chosen_pairs = random.sample(candidate_pairs, 3)
    seats: list[tuple[str, int]] = []
    for pair in chosen_pairs:
        seats.extend(pair)
    return seats


def apply_broken_seats(seats: list[Seat]):
    broken_seats_count = random.randint(6, 10)

    eligible_seats = [seat for seat in seats if seat.seat_type != SeatType.DISABILITY.value and seat.seat_type != SeatType.VIP.value]
    broken_seats = random.sample(eligible_seats, broken_seats_count)
    for seat in broken_seats:
        seat.status = SeatStatus.BROKEN.value

    return seats

def build_seat_template(session_id: int = 0) -> list[Seat]:
    disability_seats = set(generate_disability_seats())
    seats = []
    for row in ROWS:
        for col in COLS:
            key = (row, col)
            if key in disability_seats:
                seat_type = SeatType.DISABILITY.value
            elif row in VIP_ROWS and col in VIP_COLS:
                seat_type = SeatType.VIP.value
            else:
                seat_type = SeatType.REGULAR.value
            
            seat = Seat(session_id=session_id, row=row, col=col, seat_type=seat_type, status=SeatStatus.AVAILABLE.value)
            seats.append(seat)

    apply_broken_seats(seats)

    return seats