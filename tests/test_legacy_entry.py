from fastapi.testclient import TestClient

from app import main


def test_legacy_entry_serves_legacy_frontend_with_isolated_assets():
    client = TestClient(main.app)

    response = client.get("/legacy")

    assert response.status_code == 200
    assert "圈影 MomentWeaver" in response.text
    assert "/legacy-static/styles.css" in response.text
    assert "/legacy-static/app.js" in response.text
    assert 'href="/"' in response.text


def test_legacy_static_assets_are_available():
    client = TestClient(main.app)

    response = client.get("/legacy-static/app.js")

    assert response.status_code == 200
    assert "loadSettings" in response.text
