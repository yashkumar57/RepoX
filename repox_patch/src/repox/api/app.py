"""FastAPI application factory for RepoX."""

from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from repox.api.schemas import (
    AnswerCitationResponse,
    RepositoryAskRequest,
    RepositoryAskResponse,
    RepositoryCreateRequest,
    RepositoryCreateResponse,
    RepositoryIndexResponse,
    RepositorySearchRequest,
    RepositorySearchResponse,
    RepositorySearchResult,
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
    query_service_factory: Callable[[Path], tuple[object, object]] | None = None,
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
    app.state.query_service_factory = query_service_factory
    app.state.query_services = {}
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

    def get_query_services(repository_id: str, repository_path: Path):
        """Build and cache repository retrieval and QA services on demand."""
        services = app.state.query_services.get(repository_id)
        if services is not None:
            return services

        factory = app.state.query_service_factory
        if factory is None:
            from repox.analyzers.repository_analyzer import analyze_repository
            from repox.embeddings.code_rank import CodeRankEmbedder
            from repox.indexing.search import SemanticSearchService
            from repox.llm.ollama import OllamaChatModel
            from repox.query.qa import RepositoryQAService
            from repox.query.retrieval import RepositoryRetrievalService
            from repox.vector_store.chroma import ChromaVectorStore

            def factory(root: Path):
                analysis = analyze_repository(root)
                store = ChromaVectorStore.for_repository(root)
                if app.state.embedding_provider is None:
                    app.state.embedding_provider = CodeRankEmbedder()
                semantic_search = SemanticSearchService(
                    store, app.state.embedding_provider
                )
                retrieval = RepositoryRetrievalService(analysis, semantic_search)
                qa = RepositoryQAService(retrieval, OllamaChatModel())
                return retrieval, qa

        try:
            services = factory(repository_path)
        except ImportError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc
        app.state.query_services[repository_id] = services
        return services

    def resolve_repository(repository_id: str) -> Path:
        try:
            return app.state.repository_service.get_checkout(repository_id).path
        except RepositoryNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
            ) from exc

    @app.post(
        "/repositories/{repository_id}/search",
        response_model=RepositorySearchResponse,
        tags=["repositories"],
        summary="Search indexed repository code",
    )
    def search_repository(
        repository_id: str, request: RepositorySearchRequest
    ) -> RepositorySearchResponse:
        """Return semantic matches with exact source locations and content."""
        repository_path = resolve_repository(repository_id)
        retrieval, _ = get_query_services(repository_id, repository_path)
        try:
            matches = retrieval.semantic_search.search(
                request.query, top_k=request.top_k
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc

        results = [
            RepositorySearchResult(
                file_path=item.chunk.file_path,
                language=item.chunk.language,
                kind=item.chunk.kind,
                symbol_id=item.chunk.symbol_id,
                symbol_name=item.chunk.symbol_name,
                start_line=item.chunk.start_line,
                end_line=item.chunk.end_line,
                content=item.chunk.content,
                score=item.score,
                distance=item.distance,
            )
            for item in matches
        ]
        return RepositorySearchResponse(
            repository_id=repository_id,
            query=request.query,
            result_count=len(results),
            results=results,
        )

    @app.post(
        "/repositories/{repository_id}/ask",
        response_model=RepositoryAskResponse,
        tags=["repositories"],
        summary="Ask a question about an indexed repository",
    )
    def ask_repository(
        repository_id: str, request: RepositoryAskRequest
    ) -> RepositoryAskResponse:
        """Answer using retrieved repository evidence and validated citations."""
        repository_path = resolve_repository(repository_id)
        _, qa = get_query_services(repository_id, repository_path)
        try:
            result = qa.ask(
                request.query,
                top_k=request.top_k,
                context_limit=request.context_limit,
                token_budget=request.token_budget,
                max_output_tokens=request.max_output_tokens,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
            ) from exc

        return RepositoryAskResponse(
            repository_id=repository_id,
            query=result.query,
            answer=result.answer,
            model=result.model,
            citations=[
                AnswerCitationResponse(
                    source_id=citation.source_id,
                    file_path=citation.file_path,
                    start_line=citation.start_line,
                    end_line=citation.end_line,
                )
                for citation in result.citations
            ],
            invalid_citations=list(result.invalid_citations),
            citation_retry_used=result.citation_retry_used,
            citation_fallback_used=result.citation_fallback_used,
            uncited_draft=result.uncited_draft,
        )

    return app


app = create_app()
