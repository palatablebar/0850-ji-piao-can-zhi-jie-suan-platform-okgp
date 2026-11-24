def test_home_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert '票结'.encode() in response.data


def test_health_and_catalog(client):
    assert client.get("/healthz").status_code == 200
    catalog = client.get("/api/catalog").get_json()
    assert len(catalog["stages"]) == 7
