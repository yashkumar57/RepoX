"""Tests for the RepoX HTTP application and repository acquisition route."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from repox.api.app import create_app
from repox.indexing.indexer import IndexingReport
from repox.indexing.service import RepositoryIndexResult
from repox.ingestion import (
    InvalidRepositoryURLError,
    RepositoryCheckout,
    RepositoryCloneError,
)


def _checkout() -> RepositoryCheckout:
    return RepositoryCheckout(
        repository_id="a" * 32,
        owner="pallets",
        name="itsdangerous",
        url="https://github.com/pallets/itsdangerous.git",
        branch="main",
        path=Path("/managed/repositories") / ("a" * 32),
    )


def test_health_endpoint_reports_service_liveness() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "repox-api"}


def test_openapi_schema_is_available_and_documents_repository_route() -> None:
    client = TestClient(create_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "/health" in schema["paths"]
    assert "/repositories" in schema["paths"]
    assert "post" in schema["paths"]["/repositories"]
    assert "/repositories/{repository_id}/index" in schema["paths"]
    assert "post" in schema["paths"]["/repositories/{repository_id}/index"]


def test_create_repository_returns_checkout_metadata() -> None:
    service = Mock()
    service.clone.return_value = _checkout()
    client = TestClient(create_app(repository_service=service))

    response = client.post(
        "/repositories",
        json={
            "repository_url": "https://github.com/pallets/itsdangerous",
            "branch": "main",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "repository_id": "a" * 32,
        "owner": "pallets",
        "name": "itsdangerous",
        "url": "https://github.com/pallets/itsdangerous.git",
        "branch": "main",
        "status": "cloned",
    }
    service.clone.assert_called_once_with(
        "https://github.com/pallets/itsdangerous", branch="main"
    )


def test_create_repository_omits_branch_when_not_requested() -> None:
    service = Mock()
    service.clone.return_value = _checkout()
    client = TestClient(create_app(repository_service=service))

    response = client.post(
        "/repositories",
        json={"repository_url": "https://github.com/pallets/itsdangerous"},
    )

    assert response.status_code == 201
    service.clone.assert_called_once_with(
        "https://github.com/pallets/itsdangerous", branch=None
    )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"repository_url": ""},
        {"repository_url": "https://github.com/pallets/itsdangerous", "extra": 1},
    ],
)
def test_create_repository_rejects_invalid_request_schema(payload: dict) -> None:
    client = TestClient(create_app(repository_service=Mock()))

    response = client.post("/repositories", json=payload)

    assert response.status_code == 422


def test_create_repository_maps_invalid_github_url_to_422() -> None:
    service = Mock()
    service.clone.side_effect = InvalidRepositoryURLError("Only GitHub HTTPS URLs")
    client = TestClient(create_app(repository_service=service))

    response = client.post(
        "/repositories", json={"repository_url": "https://gitlab.com/a/b"}
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Only GitHub HTTPS URLs"


def test_create_repository_maps_invalid_branch_to_422() -> None:
    service = Mock()
    service.clone.side_effect = ValueError("Invalid branch name")
    client = TestClient(create_app(repository_service=service))

    response = client.post(
        "/repositories",
        json={
            "repository_url": "https://github.com/pallets/itsdangerous",
            "branch": "bad",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Invalid branch name"


def test_create_repository_maps_clone_failure_to_502() -> None:
    service = Mock()
    service.clone.side_effect = RepositoryCloneError("repository not found")
    client = TestClient(create_app(repository_service=service))

    response = client.post(
        "/repositories", json={"repository_url": "https://github.com/a/b"}
    )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "Repository acquisition failed: repository not found"
    )


def test_index_repository_returns_analysis_and_incremental_index_report() -> None:
    repository_service = Mock()
    repository_service.get_checkout.return_value = _checkout()
    indexing_service = Mock()
    indexing_service.index.return_value = RepositoryIndexResult(
        report=IndexingReport(
            total_chunks=12, embedded_chunks=10, reused_chunks=2, deleted_chunks=1
        ),
        analyzed_files=7,
        relationships=9,
    )
    factory = Mock(return_value=indexing_service)
    client = TestClient(
        create_app(
            repository_service=repository_service,
            indexing_service_factory=factory,
        )
    )

    response = client.post(f"/repositories/{'a' * 32}/index")

    assert response.status_code == 200
    assert response.json() == {
        "repository_id": "a" * 32,
        "status": "indexed",
        "analyzed_files": 7,
        "relationships": 9,
        "total_chunks": 12,
        "embedded_chunks": 10,
        "reused_chunks": 2,
        "deleted_chunks": 1,
    }
    repository_service.get_checkout.assert_called_once_with("a" * 32)
    factory.assert_called_once_with(_checkout().path)
    indexing_service.index.assert_called_once_with(_checkout().path)


def test_index_repository_reuses_indexing_service_between_requests() -> None:
    repository_service = Mock()
    repository_service.get_checkout.return_value = _checkout()
    indexing_service = Mock()
    indexing_service.index.return_value = RepositoryIndexResult(
        report=IndexingReport(0, 0, 0, 0), analyzed_files=0, relationships=0
    )
    factory = Mock(return_value=indexing_service)
    client = TestClient(
        create_app(
            repository_service=repository_service,
            indexing_service_factory=factory,
        )
    )

    first = client.post(f"/repositories/{'a' * 32}/index")
    second = client.post(f"/repositories/{'a' * 32}/index")

    assert first.status_code == second.status_code == 200
    factory.assert_called_once_with(_checkout().path)
    assert indexing_service.index.call_count == 2


def test_index_repository_returns_404_for_unknown_repository() -> None:
    from repox.ingestion import RepositoryNotFoundError

    repository_service = Mock()
    repository_service.get_checkout.side_effect = RepositoryNotFoundError(
        "Repository not found"
    )
    client = TestClient(create_app(repository_service=repository_service))

    response = client.post(f"/repositories/{'a' * 32}/index")

    assert response.status_code == 404
    assert response.json()["detail"] == "Repository not found"


def test_index_repository_maps_scan_or_index_validation_error_to_422() -> None:
    repository_service = Mock()
    repository_service.get_checkout.return_value = _checkout()
    indexing_service = Mock()
    indexing_service.index.side_effect = ValueError("scan failed")
    client = TestClient(
        create_app(
            repository_service=repository_service,
            indexing_service_factory=Mock(return_value=indexing_service),
        )
    )

    response = client.post(f"/repositories/{'a' * 32}/index")

    assert response.status_code == 422
    assert response.json()["detail"] == "scan failed"
