def test_health_check(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "CinemaCon API is running!"}


def test_auth_register_login_and_me_flow(client):
    register_payload = {
        "email": "jane@example.com",
        "name": "Jane",
        "password": "strong-password",
        "role": "staff",
    }
    register_response = client.post("/auth/register", json=register_payload)

    assert register_response.status_code == 200
    user = register_response.json()
    assert user["email"] == register_payload["email"]
    assert user["name"] == register_payload["name"]

    duplicate_response = client.post("/auth/register", json=register_payload)
    assert duplicate_response.status_code == 400
    assert duplicate_response.json()["detail"] == "Email already registered"

    login_response = client.post(
        "/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"

    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == register_payload["email"]


def test_auth_refresh_invalid_token_returns_401(client):
    response = client.post("/auth/refresh", params={"token": "not-a-real-token"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


def test_sessions_create_get_list_and_delete(client):
    create_response = client.post("/sessions/", json={"movie_name": "Interstellar"})

    assert create_response.status_code == 200
    created = create_response.json()
    session_id = created["id"]
    assert created["movie_name"] == "Interstellar"
    assert created["total_seats_count"] == 420
    assert created["booked_seats_count"] == 0
    assert 410 <= created["available_seats_count"] <= 414

    list_response = client.get("/sessions/")
    assert list_response.status_code == 200
    all_sessions = list_response.json()
    assert len(all_sessions) == 1
    assert all_sessions[0]["id"] == session_id

    get_response = client.get(f"/sessions/{session_id}")
    assert get_response.status_code == 200
    assert get_response.json()["movie_name"] == "Interstellar"

    delete_response = client.delete(f"/sessions/{session_id}")
    assert delete_response.status_code == 204

    not_found_response = client.get(f"/sessions/{session_id}")
    assert not_found_response.status_code == 404
    assert not_found_response.json()["detail"] == "Session not found"


def test_bookings_create_list_and_cancel(client, seed_session):
    session_id = seed_session(rows="ABCDE", cols=range(1, 13), movie_name="Booking Movie")

    create_payload = {
        "name": "team-1",
        "session_id": session_id,
        "group_size": 3,
        "seat_preference": "any",
    }
    create_response = client.post("/bookings/", json=create_payload)
    assert create_response.status_code == 200
    created = create_response.json()
    booking_id = created["id"]
    assert created["name"] == "team-1"
    assert created["session_id"] == session_id
    assert len(created["booked_seats"]) == 3

    duplicate_response = client.post("/bookings/", json=create_payload)
    assert duplicate_response.status_code == 409

    list_response = client.get(f"/bookings/{session_id}")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    cancel_response = client.delete(f"/bookings/cancel/{booking_id}")
    assert cancel_response.status_code == 204

    list_after_cancel = client.get(f"/bookings/{session_id}")
    assert list_after_cancel.status_code == 200
    assert list_after_cancel.json() == []


def test_bookings_validation_errors(client, seed_session):
    session_id = seed_session(rows="AB", cols=range(1, 9), movie_name="Validation Movie")

    invalid_pref = client.post(
        "/bookings/",
        json={
            "name": "bad-pref",
            "session_id": session_id,
            "group_size": 2,
            "seat_preference": "balcony",
        },
    )
    assert invalid_pref.status_code == 400
    assert invalid_pref.json()["detail"] == "Invalid seat preference"

    mixed_mismatch = client.post(
        "/bookings/",
        json={
            "name": "mixed-mismatch",
            "session_id": session_id,
            "group_size": 4,
            "regular_count": 1,
            "vip_count": 1,
            "accessible_count": 1,
        },
    )
    assert mixed_mismatch.status_code == 400
    assert "group_size must equal" in mixed_mismatch.json()["detail"]


def test_seats_routes(client, seed_session):
    session_id = seed_session(rows="ABC", cols=range(1, 6), movie_name="Seat Movie")

    all_seats_response = client.get(f"/seats/{session_id}/seats")
    assert all_seats_response.status_code == 200
    seats = all_seats_response.json()
    assert len(seats) == 15

    seat_id = seats[0]["id"]
    one_seat_response = client.get(f"/seats/{session_id}/{seat_id}")
    assert one_seat_response.status_code == 200
    assert one_seat_response.json()["id"] == seat_id

    missing_seat_response = client.get(f"/seats/{session_id}/999999")
    assert missing_seat_response.status_code == 404
    assert missing_seat_response.json()["detail"] == "Seat not found"


def test_seat_scatter_report(client, seed_session):
    session_id = seed_session(rows="A", cols=range(1, 6), movie_name="Scatter Movie")

    first_booking = client.post(
        "/bookings/",
        json={"name": "single-left", "session_id": session_id, "group_size": 2, "pinned_seats": ["A1", "A2"], "admin_override": True},
    )
    assert first_booking.status_code == 200

    second_booking = client.post(
        "/bookings/",
        json={"name": "single-right", "session_id": session_id, "group_size": 2, "pinned_seats": ["A4", "A5"], "admin_override": True},
    )
    assert second_booking.status_code == 200

    report_response = client.get(f"/seats/{session_id}/scatter-report")
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["session_id"] == str(session_id)
    assert report["total_isolated_seats"] == 1
    assert "A" in report["rows_affected"]


def test_admin_stats_and_mark_broken(client, seed_session):
    session_id = seed_session(
        rows="ABC",
        cols=range(1, 6),
        movie_name="Admin Movie",
        vip_rows={"B"},
        vip_cols={2, 3},
        disability_positions={("C", 1), ("C", 2)},
    )

    seats_response = client.get(f"/seats/{session_id}/seats")
    assert seats_response.status_code == 200
    seat_id = seats_response.json()[0]["id"]

    mark_response = client.post(
        "/admin/mark-broken",
        json={"session_id": session_id, "seat_ids": [seat_id]},
    )
    assert mark_response.status_code == 200
    assert mark_response.json()["message"] == "Seats marked as broken successfully"

    stats_response = client.get(f"/admin/sessions/stats/{session_id}")
    assert stats_response.status_code == 200
    stats = stats_response.json()
    assert stats["session_id"] == session_id
    assert stats["movie_name"] == "Admin Movie"
    assert "breakdown" in stats
