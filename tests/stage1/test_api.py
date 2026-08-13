from fastapi.testclient import TestClient

from apps.server.app import build_api
from packages.application.product_service import ProductService
from packages.persistence.sqlite_product_repository import SQLiteProductRepository


def test_api_create_read_patch_list_search_filter(tmp_path):
    service = ProductService(SQLiteProductRepository(tmp_path / "api.sqlite"))
    client = TestClient(build_api(service))
    response = client.post("/api/v1/products", headers={"X-Actor": "api-user"}, json={
        "company": "HMS", "part_name": "Plate", "quantity": 4, "unit": "pcs", "material": "Al",
    })
    assert response.status_code == 201
    created = response.json()
    assert created["created_by"] == "api-user"
    assert client.get(f"/api/v1/products/{created['product_code']}").status_code == 200
    patched = client.patch(f"/api/v1/products/{created['internal_id']}", headers={"X-Actor": "editor"}, json={"status": "IN_PROGRESS"})
    assert patched.status_code == 200
    assert client.get("/api/v1/products", params={"search": "plate", "status": "IN_PROGRESS"}).json()["total"] == 1
    assert client.get("/api/v1/products/nope").status_code == 404
    duplicate = client.post("/api/v1/products", json={"product_code": created["product_code"], "company": "HMS", "part_name": "x", "quantity": 1, "unit": "pcs"})
    assert duplicate.status_code == 409
