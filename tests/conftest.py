"""
Pytest fixtures for Monolith backend integration tests.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from unittest.mock import AsyncMock, patch

from app.core.database import Base, get_db
from app.main import app

TEST_DB_URL = "postgresql+asyncpg://nxpi_admin:localpassword@localhost:5432/nxpi_test_db"

test_engine = create_async_engine(TEST_DB_URL, poolclass=NullPool, echo=False)
TestSessionFactory = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_db():
    from sqlalchemy import text
    async with test_engine.connect() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.commit()
    yield
    async with test_engine.connect() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.commit()
    await test_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clear_test_db():
    from sqlalchemy import text
    async with test_engine.connect() as conn:
        await conn.execute(text("TRUNCATE org_members, onboarding_events, organizations, refresh_tokens, otp_codes, users CASCADE;"))
        await conn.commit()
    yield


@pytest_asyncio.fixture
async def db_session():
    async with TestSessionFactory() as session:
        yield session
        await session.commit()


@pytest_asyncio.fixture
async def client():
    async def _override_get_db():
        async with TestSessionFactory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db

    with patch("app.services.auth_service.send_otp_email", new_callable=AsyncMock) as mock_otp, \
         patch("app.services.auth_service.send_welcome_email", new_callable=AsyncMock) as mock_welcome:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            ac.mock_otp_email = mock_otp
            ac.mock_welcome_email = mock_welcome
            yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def register_payload():
    return {
        "email": "test@example.com",
        "password": "StrongPass1!",
    }
