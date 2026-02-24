import base64
import importlib
import os

from prometheus_client import CONTENT_TYPE_LATEST
from starlette.testclient import TestClient


def _load_main():
    os.environ.setdefault("ADMIN_USERNAME", "test_user")
    os.environ.setdefault("ADMIN_PASSWORD", "test_password")
    os.environ.setdefault("METRICS_ENABLED", "false")

    import api.auth_utils as auth_utils
    import mcp_service.core as core
    import mcp_service.main as main

    importlib.reload(auth_utils)
    importlib.reload(core)
    return importlib.reload(main)


def _basic_auth_header(username: str, password: str) -> dict:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {token}"}


def test_metrics_app_exposes_prometheus_metrics():
    main = _load_main()
    metrics_app = main._build_metrics_app()

    with TestClient(metrics_app) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(CONTENT_TYPE_LATEST)
    assert "# HELP" in response.text


def test_main_app_does_not_expose_metrics():
    main = _load_main()
    headers = _basic_auth_header(os.environ["ADMIN_USERNAME"], os.environ["ADMIN_PASSWORD"])

    with TestClient(main.app) as client:
        response = client.get("/metrics", headers=headers)

    assert response.status_code == 404
