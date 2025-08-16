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
    assert b"Bokning" in response.data


def test_login_route(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Login" in response.data
