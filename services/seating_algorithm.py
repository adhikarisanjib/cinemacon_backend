import re
from typing import Optional

from models import BookedSeat, Seat, SeatStatus, SeatType, Session


# Row order A=0 and O=14
ROW_INDEX = {row: index for index, row in enumerate("ABCDEFGHIJKLMNO")}


PREFERRED_ROW_ORDER = list("JIKHLGMFNEODCBA")
PREFERRED_CENTER_COL = 14.5


# People generally prefer center-back rows over front rows.
SINGLE_GAP_PENALTY = 140   # Heavy penalty: would create isolated single empty seats
EDGE_BONUS = -6            # Small reward when a block ends at a natural boundary


def parse_seat_code(seat_code: str) -> tuple[str, int]:
    match = re.fullmatch(r"([A-O])(\d{1,2})", seat_code.upper())

    if not match:
        raise ValueError(f"Invalid seat code: {seat_code}")

    row = match.group(1)
    col = int(match.group(2))

    if col < 1 or col > 28:
        raise ValueError(f"Invalid seat column: {seat_code}")

    return row, col


def allocate_seats(
    session: Session,
    group_size: int,
    seat_preference: str,
    admin_override: bool = False,
    pinned_seats: list[str] | None = None,
) -> list[BookedSeat]:
    if group_size < 1 or group_size > 7:
        raise ValueError("Group size must be between 1 and 7 seats")

    normalized_preference = (seat_preference or "any").lower()

    if admin_override and pinned_seats:
        return _admin_pin_seats(session, group_size, normalized_preference, pinned_seats)

    best_window, _allocation_note = _choose_best_window(session, group_size, normalized_preference)
    if not best_window:
        raise ValueError(
            f"No contiguous block of {group_size} seats available. "
            "The cinema may be fully booked or too fragmented."
        )

    return _commit_booking_seats(session, best_window)

def allocate_mixed_seats(
    session: Session,
    regular_count: int,
    vip_count: int,
    accessible_count: int,
) -> list[BookedSeat]:
    total = regular_count + vip_count + accessible_count
    if total <= 0:
        raise ValueError("At least one seat must be requested for a mixed booking.")
    if total > 7:
        raise ValueError("Mixed booking total must be between 1 and 7 seats.")

    staged: list[Seat] = []
    stages = [
        (accessible_count, "disability"),
        (vip_count, "vip"),
        (regular_count, "regular"),
    ]

    try:
        for count, preference in stages:
            if count <= 0:
                continue
            window, _allocation_note = _choose_best_window(session, count, preference)
            if not window:
                raise ValueError(
                    "Unable to satisfy mixed booking request with current availability. "
                    f"Failed while allocating {count} {preference} seat(s)."
                )

            # Stage seats to avoid reuse in the same mixed booking selection.
            for seat in window:
                seat.status = SeatStatus.RESERVED.value
            staged.extend(window)
    except ValueError:
        _rollback_staged(staged)
        raise

    return _commit_booking_seats(session, staged)


def _rollback_staged(staged: list[Seat]) -> None:
    for seat in staged:
        if seat.status == SeatStatus.RESERVED.value:
            seat.status = SeatStatus.AVAILABLE.value


def _commit_booking_seats(session: Session, booked_seats: list[Seat]) -> list[BookedSeat]:
    booked_seat_rows: list[BookedSeat] = []
    for seat in booked_seats:
        seat.status = SeatStatus.BOOKED.value
        booked_seat_rows.append(BookedSeat(session_id=session.id, seat=seat))
    return booked_seat_rows


def _eligible_rows(preference: str) -> list[str]:
    if preference == "vip":
        return list("EFGHI")
    return list("ABCDEFGHIJKLMNO")


def _choose_best_window(
    session: Session,
    group_size: int,
    preference: str,
) -> tuple[Optional[list[Seat]], Optional[str]]:
    eligible_rows = _eligible_rows(preference)
    best_seats: Optional[list[Seat]] = None
    best_score = float("inf")
    fallback_note: Optional[str] = None

    sorted_rows = sorted(
        eligible_rows,
        key=lambda row: PREFERRED_ROW_ORDER.index(row) if row in PREFERRED_ROW_ORDER else 99,
    )

    for row in sorted_rows:
        row_seats = _get_row_seats(session, row, preference)
        windows = _contiguous_windows(row_seats, group_size)

        for window in windows:
            score = _score_window(row, row_seats, window)
            if score < best_score:
                best_score = score
                best_seats = window

    if best_seats is None and preference != "any":
        best_seats, _ = _choose_best_window(session, group_size, "any")
        if best_seats:
            label = "VIP" if preference == "vip" else "accessibility" if preference == "disability" else preference
            fallback_note = f"{label.capitalize()} seats are full, so we selected the best available block instead."

    return best_seats, fallback_note


def _get_row_seats(session: Session, row: str, preference: str) -> list[Seat]:
    seats: list[Seat] = []
    for seat in session.seats:
        if seat.row != row:
            continue

        # Exclude permanently broken seats from algorithmic allocations.
        if seat.status == SeatStatus.BROKEN.value:
            continue

        if preference == "disability" and seat.seat_type != SeatType.DISABILITY.value:
            continue
        if preference != "disability" and seat.seat_type == SeatType.DISABILITY.value:
            continue
        if preference == "vip" and seat.seat_type != SeatType.VIP.value:
            continue
        if preference == "regular" and seat.seat_type != SeatType.REGULAR.value:
            continue

        seats.append(seat)

    seats.sort(key=lambda s: s.col)
    return seats


def _contiguous_windows(row_seats: list[Seat], size: int) -> list[list[Seat]]:
    windows: list[list[Seat]] = []
    n = len(row_seats)
    for i in range(n - size + 1):
        window = row_seats[i : i + size]
        if all(seat.is_available for seat in window):
            cols = [seat.col for seat in window]
            if cols == list(range(cols[0], cols[0] + size)):
                windows.append(window)
    return windows


def _score_window(row: str, row_seats: list[Seat], window: list[Seat]) -> float:
    score = 0.0

    window_cols = {seat.col for seat in window}
    min_col = min(window_cols)
    max_col = max(window_cols)
    col_map = {seat.col: seat for seat in row_seats}

    left_col = min_col - 1
    left_seat = col_map.get(left_col)
    if left_seat is None:
        score += EDGE_BONUS
    elif not left_seat.is_available:
        score += EDGE_BONUS
    else:
        left_gap = _count_consecutive_available(col_map, left_col, direction=-1)
        if left_gap == 1:
            score += SINGLE_GAP_PENALTY

    right_col = max_col + 1
    right_seat = col_map.get(right_col)
    if right_seat is None:
        score += EDGE_BONUS
    elif not right_seat.is_available:
        score += EDGE_BONUS
    else:
        right_gap = _count_consecutive_available(col_map, right_col, direction=1)
        if right_gap == 1:
            score += SINGLE_GAP_PENALTY

    row_penalty = PREFERRED_ROW_ORDER.index(row) * 2
    window_center = (min_col + max_col) / 2
    center_penalty = abs(window_center - PREFERRED_CENTER_COL) * 3
    score += row_penalty + center_penalty

    return score


def _count_consecutive_available(col_map: dict[int, Seat], start_col: int, direction: int) -> int:
    count = 0
    col = start_col
    while True:
        seat = col_map.get(col)
        if seat is None or not seat.is_available:
            break
        count += 1
        col += direction
    return count


def _admin_pin_seats(
    session: Session,
    group_size: int,
    seat_preference: str,
    pinned_seats: list[str],
) -> list[BookedSeat]:
    if len(pinned_seats) != group_size:
        raise ValueError("Pinned seats must match group size when admin_override is enabled")

    desired = [parse_seat_code(code) for code in pinned_seats]
    seat_map = {(seat.row, seat.col): seat for seat in session.seats}
    pinned_models: list[Seat] = []

    for row, col in desired:
        seat = seat_map.get((row, col))
        if not seat:
            raise ValueError(f"Seat {row}{col} does not exist in this session.")
        if seat.status == SeatStatus.BOOKED.value:
            raise ValueError(f"Seat {row}{col} is already booked.")
        pinned_models.append(seat)

    # seat_preference is intentionally ignored for admin pinning by design.
    _ = seat_preference
    return _commit_booking_seats(session, pinned_models)


def analyse_scatter(session: Session) -> dict:
    """
    Returns a diagnostic report of single isolated empty seats per row.
    Useful for stress-testing the algorithm.
    """
    report = {}
    for row in "ABCDEFGHIJKLMNO":
        row_seats = sorted(
            [s for s in session.seats if s.row == row and s.seat_type != SeatType.DISABILITY.value],
            key=lambda s: s.col,
        )
        isolated = []
        for i, seat in enumerate(row_seats):
            if not seat.is_available:
                continue
            left_ok = (i == 0) or not row_seats[i - 1].is_available
            right_ok = (i == len(row_seats) - 1) or not row_seats[i + 1].is_available
            if left_ok and right_ok:
                isolated.append(seat.id)
        if isolated:
            report[row] = isolated
    return report
