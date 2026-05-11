"""Regression: confirm DocumentInstance is fully gone."""


def test_instance_manager_removed():
    import importlib
    try:
        importlib.import_module("officeplane.management.instance_manager")
        assert False, "instance_manager should have been deleted"
    except ModuleNotFoundError:
        pass


def test_ecm_instances_routes_removed():
    import importlib
    try:
        importlib.import_module("officeplane.api.ecm.instances")
        assert False, "ecm.instances should have been deleted"
    except ModuleNotFoundError:
        pass


def test_prisma_has_no_documentinstance():
    """Schema should not declare DocumentInstance any more."""
    schema = open(
        "/app/prisma/schema.prisma" if __import__("os").path.exists("/app/prisma/schema.prisma")
        else __import__("pathlib").Path(__file__).parents[2] / "prisma/schema.prisma"
    ).read()
    assert "DocumentInstance" not in schema
    assert "InstanceState" not in schema


def test_instances_endpoint_returns_404():
    from fastapi.testclient import TestClient
    from officeplane.api.main import app
    c = TestClient(app)
    assert c.get("/api/instances").status_code == 404
    assert c.get("/api/ecm/instances").status_code == 404
