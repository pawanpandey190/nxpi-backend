"""
Integration tests for Monolith backend: Auth, Onboarding, Health checks.
"""

import pytest


@pytest.mark.asyncio
async def test_health_check(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "nxpi-backend"


@pytest.mark.asyncio
async def test_register_flow(client, register_payload):
    response = await client.post("/api/v1/auth/register", json=register_payload)
    assert response.status_code == 201
    assert "verification" in response.json()["message"].lower()
    client.mock_otp_email.assert_called_once()


@pytest.mark.asyncio
async def test_duplicate_registration(client, register_payload, db_session):
    from app.models.user import User
    from app.core.security import hash_password

    user = User(
        email=register_payload["email"],
        password_hash=hash_password(register_payload["password"]),
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    response = await client.post("/api/v1/auth/register", json=register_payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_onboarding_unauthenticated(client):
    response = await client.get("/api/v1/onboarding/status")
    assert response.status_code == 401
