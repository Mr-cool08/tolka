import pytest
import website


@pytest.fixture
def client():
    website.app.config.update({"TESTING": True})
    with website.app.test_client() as client:
        yield client


def test_index_route(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"V\xc3\xa4lkommen" in response.data


def test_login_route(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Login" in response.data


def test_health_route(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert b"OK" in response.data


def test_404_route(client):
    response = client.get("/not-found")
    assert response.status_code == 404
    assert b"Detta var inte vad du letade efter." in response.data
