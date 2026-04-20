import pytest


def test_create_profile(client, auth_headers, test_user):
    """Test creating a coaching profile."""
    response = client.post(
        "/api/profiles",
        json={
            "name": "Interview Prep",
            "profile_type": "interview",
            "coaching_focus": {
                "pace": True,
                "clarity": True,
                "fillers": True
            }
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Interview Prep"
    assert data["profile_type"] == "interview"
    assert data["is_active"] is True


def test_create_profile_no_auth(client):
    """Test creating profile without authentication."""
    response = client.post(
        "/api/profiles",
        json={
            "name": "Interview Prep",
            "profile_type": "interview"
        }
    )
    assert response.status_code == 403


def test_list_profiles(client, auth_headers, test_user):
    """Test listing coaching profiles."""
    # Create profiles
    client.post(
        "/api/profiles",
        json={
            "name": "Interview Prep",
            "profile_type": "interview"
        },
        headers=auth_headers
    )
    client.post(
        "/api/profiles",
        json={
            "name": "Sales Pitch",
            "profile_type": "sales"
        },
        headers=auth_headers
    )

    response = client.get("/api/profiles", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Interview Prep"
    assert data[1]["name"] == "Sales Pitch"


def test_get_profile(client, auth_headers, test_user):
    """Test getting a specific profile."""
    # Create profile
    create_response = client.post(
        "/api/profiles",
        json={
            "name": "Interview Prep",
            "profile_type": "interview"
        },
        headers=auth_headers
    )
    profile_id = create_response.json()["id"]

    # Get profile
    response = client.get(f"/api/profiles/{profile_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == profile_id
    assert data["name"] == "Interview Prep"


def test_get_nonexistent_profile(client, auth_headers):
    """Test getting a profile that doesn't exist."""
    response = client.get("/api/profiles/nonexistent-id", headers=auth_headers)
    assert response.status_code == 404


def test_update_profile(client, auth_headers, test_user):
    """Test updating a profile."""
    # Create profile
    create_response = client.post(
        "/api/profiles",
        json={
            "name": "Interview Prep",
            "profile_type": "interview"
        },
        headers=auth_headers
    )
    profile_id = create_response.json()["id"]

    # Update profile
    response = client.put(
        f"/api/profiles/{profile_id}",
        json={
            "name": "Advanced Interview Prep",
            "is_active": False
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Advanced Interview Prep"
    assert data["is_active"] is False


def test_delete_profile(client, auth_headers, test_user):
    """Test deleting a profile."""
    # Create profile
    create_response = client.post(
        "/api/profiles",
        json={
            "name": "Interview Prep",
            "profile_type": "interview"
        },
        headers=auth_headers
    )
    profile_id = create_response.json()["id"]

    # Delete profile
    response = client.delete(f"/api/profiles/{profile_id}", headers=auth_headers)
    assert response.status_code == 200

    # Verify it's deleted
    response = client.get(f"/api/profiles/{profile_id}", headers=auth_headers)
    assert response.status_code == 404
