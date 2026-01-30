import pytest
from fastapi.testclient import TestClient
from backend.api import app

client = TestClient(app)

def test_read_history():
    response = client.get("/research/history")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_start_research_no_topic():
    response = client.post("/research/start", json={})
    assert response.status_code == 422 # Validation error for missing field

def test_start_research_empty_topic():
    response = client.post("/research/start", json={"topic": ""})
    assert response.status_code == 400 # Our custom validation

def test_get_nonexistent_session():
    response = client.get("/research/fake-session-id")
    # It might be 404 or empty depending on impl, currently 404
    assert response.status_code == 404
