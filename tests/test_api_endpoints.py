from fastapi.testclient import TestClient

from backend.api import app

from backend.db.repository import ResearchRepository
from unittest.mock import AsyncMock, patch
import pytest

@pytest.fixture
def mock_repo_class():
    with patch("backend.api.ResearchRepository") as MockRepo:
        mock_instance = AsyncMock()
        mock_instance.save_session.return_value = None
        mock_instance.list_sessions.return_value = []
        mock_instance.get_session.return_value = None
        MockRepo.return_value = mock_instance
        yield MockRepo

@pytest.fixture
def client(_mock_repo_class):
    # Depending on implementation, we might need to patch AsyncSessionLocal too if it tries to connect
    # But usually creating the session object is cheap/sync if not entered.
    # However, 'async with AsyncSessionLocal() as session' will enter context.
    # So we should patch AsyncSessionLocal to return a mock session.
    with patch("backend.api.AsyncSessionLocal") as MockSession:
        MockSession.return_value.__aenter__.return_value = AsyncMock()
        # Mock init_db to prevent real database initialization
        with patch("backend.api.init_db", new_callable=AsyncMock):
            with TestClient(app) as test_client:
                 yield test_client


def test_read_history(client):
    response = client.get("/research/history")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_start_research_no_topic(client):
    response = client.post("/research/start", json={})
    assert response.status_code == 422  # Validation error for missing field


def test_start_research_empty_topic(client):
    response = client.post("/research/start", json={"topic": ""})
    assert response.status_code == 400  # Our custom validation


def test_get_nonexistent_session(client):
    response = client.get("/research/fake-session-id")
    # It might be 404 or empty depending on impl, currently 404
    assert response.status_code == 404
