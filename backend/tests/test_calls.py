import pytest


def test_start_call(client, auth_headers, test_user):
    """Test starting a call."""
    # Create profile first
    profile_response = client.post(
        "/api/profiles",
        json={
            "name": "Interview Prep",
            "profile_type": "interview"
        },
        headers=auth_headers
    )
    profile_id = profile_response.json()["id"]

    # Start call
    response = client.post(
        "/api/calls/start",
        json={
            "profile_id": profile_id,
            "call_type": "phone",
            "external_participant_name": "John Interviewer"
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "call_id" in data
    assert "started_at" in data


def test_start_call_no_auth(client):
    """Test starting a call without authentication."""
    response = client.post(
        "/api/calls/start",
        json={
            "profile_id": "some-id",
            "call_type": "phone"
        }
    )
    assert response.status_code == 403


def test_end_call(client, auth_headers, test_user):
    """Test ending a call."""
    # Create profile and start call
    profile_response = client.post(
        "/api/profiles",
        json={
            "name": "Interview Prep",
            "profile_type": "interview"
        },
        headers=auth_headers
    )
    profile_id = profile_response.json()["id"]

    start_response = client.post(
        "/api/calls/start",
        json={
            "profile_id": profile_id,
            "call_type": "phone"
        },
        headers=auth_headers
    )
    call_id = start_response.json()["call_id"]

    # End call
    response = client.post(f"/api/calls/{call_id}/end", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["call_id"] == call_id
    assert "duration_seconds" in data
    assert "ended_at" in data


def test_add_metrics(client, auth_headers, test_user):
    """Test adding metrics to a call."""
    # Create profile and start call
    profile_response = client.post(
        "/api/profiles",
        json={
            "name": "Interview Prep",
            "profile_type": "interview"
        },
        headers=auth_headers
    )
    profile_id = profile_response.json()["id"]

    start_response = client.post(
        "/api/calls/start",
        json={
            "profile_id": profile_id,
            "call_type": "phone"
        },
        headers=auth_headers
    )
    call_id = start_response.json()["call_id"]

    # Add metrics
    response = client.post(
        f"/api/calls/{call_id}/metrics",
        json={
            "words_per_minute": 145.5,
            "avg_pause_duration_ms": 500,
            "filler_word_count": 3,
            "confidence_score": 0.85
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "metrics recorded"


def test_add_transcript(client, auth_headers, test_user):
    """Test adding transcript to a call."""
    # Create profile and start call
    profile_response = client.post(
        "/api/profiles",
        json={
            "name": "Interview Prep",
            "profile_type": "interview"
        },
        headers=auth_headers
    )
    profile_id = profile_response.json()["id"]

    start_response = client.post(
        "/api/calls/start",
        json={
            "profile_id": profile_id,
            "call_type": "phone"
        },
        headers=auth_headers
    )
    call_id = start_response.json()["call_id"]

    # Add transcript
    transcript_text = "Hello, I'm interested in the senior engineer position..."
    response = client.post(
        f"/api/calls/{call_id}/transcript",
        json={"transcript": transcript_text},
        headers=auth_headers
    )
    assert response.status_code == 200

    # Verify transcript was saved
    call_response = client.get(f"/api/calls/{call_id}", headers=auth_headers)
    assert call_response.json()["transcript"] == transcript_text


def test_get_call(client, auth_headers, test_user):
    """Test getting call details."""
    # Create profile and start call
    profile_response = client.post(
        "/api/profiles",
        json={
            "name": "Interview Prep",
            "profile_type": "interview"
        },
        headers=auth_headers
    )
    profile_id = profile_response.json()["id"]

    start_response = client.post(
        "/api/calls/start",
        json={
            "profile_id": profile_id,
            "call_type": "phone",
            "external_participant_name": "Jane"
        },
        headers=auth_headers
    )
    call_id = start_response.json()["call_id"]

    # Get call
    response = client.get(f"/api/calls/{call_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == call_id
    assert data["call_type"] == "phone"
    assert data["external_participant_name"] == "Jane"


def test_list_calls(client, auth_headers, test_user):
    """Test listing user's calls."""
    # Create profile
    profile_response = client.post(
        "/api/profiles",
        json={
            "name": "Interview Prep",
            "profile_type": "interview"
        },
        headers=auth_headers
    )
    profile_id = profile_response.json()["id"]

    # Start multiple calls
    client.post(
        "/api/calls/start",
        json={
            "profile_id": profile_id,
            "call_type": "phone"
        },
        headers=auth_headers
    )
    client.post(
        "/api/calls/start",
        json={
            "profile_id": profile_id,
            "call_type": "simulation"
        },
        headers=auth_headers
    )

    # List calls
    response = client.get("/api/calls", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
