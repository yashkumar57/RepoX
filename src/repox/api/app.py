"""FastAPI application factory for RepoX."""

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from repox.api.schemas import (
    RepositoryCreateRequest,
    RepositoryCreateResponse,
    RepositoryIndexResponse,
)
from repox.ingestion import (
    GitHubRepositoryService,
    InvalidRepositoryURLError,
    RepositoryCloneError,
    RepositoryNotFoundError,
)


class HealthResponse(BaseModel):
    """Liveness response for the HTTP service."""

    status: str
    service: str


def create_app(
    repository_service: GitHubRepositoryService | None = None,
    indexing_service_factory: Callable[[Path], object] | None = None,
) -> FastAPI:
    """Create the API application without loading models or opening indexes.

    A repository service can be injected by tests or embedding applications.
    """
    app = FastAPI(
        title="RepoX API",
        description="HTTP interface for repository intelligence services.",
        version="0.1.0",
    )
    app.state.repository_service = repository_service or GitHubRepositoryService()
    app.state.indexing_service_factory = indexing_service_factory
    app.state.indexing_services = {}
    app.state.embedding_provider = None

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        """Report that the API process is alive."""
        return HealthResponse(status="ok", service="repox-api")

    @app.post(
        "/repositories",
        response_model=RepositoryCreateResponse,
        status_code=status.HTTP_201_CREATED,
        tags=["repositories"],
        summary="Acquire a public GitHub repository",
    )
    def create_repository(
        request: RepositoryCreateRequest,
    ) -> RepositoryCreateResponse:
        """Clone a public GitHub repository into the managed workspace."""
        try:
            checkout = app.state.repository_service.clone(
                request.repository_url,
                branch=request.branch,
            )
        except (InvalidRepositoryURLError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc
        except RepositoryCloneError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Repository acquisition failed: {exc}",
            ) from exc

        return RepositoryCreateResponse(
            repository_id=checkout.repository_id,
            owner=checkout.owner,
            name=checkout.name,
            url=checkout.url,
            branch=checkout.branch,
        )

    @app.post(
        "/repositories/{repository_id}/index",
        response_model=RepositoryIndexResponse,
        status_code=status.HTTP_200_OK,
        tags=["repositories"],
        summary="Analyze and semantically index an acquired repository",
    )
    def index_repository(repository_id: str) -> RepositoryIndexResponse:
        """Run deterministic analysis and synchronize the repository vector index."""
        try:
            checkout = app.state.repository_service.get_checkout(repository_id)
        except RepositoryNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc

        service = app.state.indexing_services.get(repository_id)
        if service is None:
            factory = app.state.indexing_service_factory
            if factory is None:
                from repox.embeddings.code_rank import CodeRankEmbedder
                from repox.indexing.service import RepositoryIndexingService
                from repox.vector_store.chroma import ChromaVectorStore

                if app.state.embedding_provider is None:
                    app.state.embedding_provider = CodeRankEmbedder()

                def factory(root: Path) -> object:
                    store = ChromaVectorStore.for_repository(root)
                    return RepositoryIndexingService(
                        store, app.state.embedding_provider
                    )

            try:
                service = factory(checkout.path)
            except ImportError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=str(exc),
                ) from exc
            app.state.indexing_services[repository_id] = service

        try:
            result = service.index(checkout.path)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc

        report = result.report
        return RepositoryIndexResponse(
            repository_id=repository_id,
            analyzed_files=result.analyzed_files,
            relationships=result.relationships,
            total_chunks=report.total_chunks,
            embedded_chunks=report.embedded_chunks,
            reused_chunks=report.reused_chunks,
            deleted_chunks=report.deleted_chunks,
        )

    return app


app = create_app()
