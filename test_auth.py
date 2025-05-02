from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_register_login_profile():
    # Register
    reg_data = {
        "email": "testuser@example.com",
        "password": "testpass123",
        "name": "Test User"
    }
    reg_resp = client.post("/register", json=reg_data)
    assert reg_resp.status_code == 200
    assert reg_resp.json()["email"] == reg_data["email"]

    # Login
    login_data = {
        "email": "testuser@example.com",
        "password": "testpass123"
    }
    login_resp = client.post("/login", json=login_data)
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    assert token

    # Profile (authenticated)
    headers = {"Authorization": f"Bearer {token}"}
    profile_resp = client.get("/profile", headers=headers)
    assert profile_resp.status_code == 200
    assert profile_resp.json()["email"] == reg_data["email"]

test_register_login_profile()
