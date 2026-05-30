import random
from models import Seat, SeatType, SeatStatus


ROWS = list("ABCDEFGHIJKLMNO")
COLS = list(range(1, 29)) 


possible_vip_rows = [
    ["E", "F", "G", "H"],
    ["F", "G", "H", "I"]
]

selected_rows = random.choice(possible_vip_rows)

VIP_LAYOUT = {
    selected_rows[0]: 12,
    selected_rows[1]: 13,
    selected_rows[2]: 14,
    selected_rows[3]: 15,
}


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

    total_cols = len(COLS)

    vip_positions = set()

    for row, vip_count in VIP_LAYOUT.items():

        start_col = (total_cols - vip_count) // 2 + 1
        end_col = start_col + vip_count - 1

        for col in range(start_col, end_col + 1):
            vip_positions.add((row, col))

    for row in ROWS:
        for col in COLS:

            key = (row, col)

            if key in disability_seats:
                seat_type = SeatType.DISABILITY.value

            elif key in vip_positions:
                seat_type = SeatType.VIP.value

            else:
                seat_type = SeatType.REGULAR.value

            seat = Seat(
                session_id=session_id,
                row=row,
                col=col,
                seat_type=seat_type,
                status=SeatStatus.AVAILABLE.value
            )

            seats.append(seat)

    apply_broken_seats(seats)

    return seats