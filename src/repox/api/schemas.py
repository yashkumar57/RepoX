"""Request and response schemas for repository API operations."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RepositoryCreateRequest(BaseModel):
    """Request to acquire a public GitHub repository."""

    model_config = ConfigDict(extra="forbid")

    repository_url: str = Field(
        min_length=1,
        max_length=2048,
        description="HTTPS URL of a public GitHub repository.",
        examples=["https://github.com/pallets/itsdangerous"],
    )
    branch: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description=(
            "Optional branch to clone. Defaults to the repository's default branch."
        ),
    )


class RepositoryCreateResponse(BaseModel):
    """Metadata for a successfully acquired repository."""

    repository_id: str
    owner: str
    name: str
    url: str
    branch: str | None
    status: str = "cloned"


class RepositoryIndexResponse(BaseModel):
    """Summary of repository analysis and vector-index synchronization."""

    repository_id: str
    status: str = "indexed"
    analyzed_files: int
    relationships: int
    total_chunks: int
    embedded_chunks: int
    reused_chunks: int
    deleted_chunks: int


class RepositoryRecordResponse(BaseModel):
    """Persisted repository metadata and its latest indexing summary."""

    repository_id: str
    owner: str
    name: str
    url: str
    branch: str | None
    status: str
    index_result: RepositoryIndexResponse | None = None
    created_at: str
    updated_at: str


class RepositorySearchRequest(BaseModel):
    """A semantic repository search request."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=50)


class RepositorySearchResult(BaseModel):
    """One source-grounded semantic search result."""

    file_path: str
    language: str
    kind: str
    symbol_id: str
    symbol_name: str
    start_line: int
    end_line: int
    content: str
    score: float
    distance: float


class RepositorySearchResponse(BaseModel):
    """Semantic search results for a repository."""

    repository_id: str
    query: str
    result_count: int
    results: list[RepositorySearchResult]


class RepositoryAskRequest(BaseModel):
    """A repository-grounded question answering request."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)
    context_limit: int = Field(default=10, ge=0, le=50)
    token_budget: int = Field(default=6000, ge=256, le=30000)
    max_output_tokens: int = Field(default=1000, ge=1, le=4000)


class AnswerCitationResponse(BaseModel):
    """A citation validated against evidence supplied to the model."""

    source_id: str
    file_path: str
    start_line: int
    end_line: int


class RepositoryAskResponse(BaseModel):
    """Repository answer and citation-validation metadata."""

    repository_id: str
    query: str
    answer: str
    model: str
    citations: list[AnswerCitationResponse]
    invalid_citations: list[str]
    citation_retry_used: bool
    citation_fallback_used: bool
    uncited_draft: str | None = None


class RepositoryGraphNodeResponse(BaseModel):
    """One source-located node in the repository visualization graph."""

    id: str
    name: str
    kind: str
    path: str
    language: str
    start_line: int | None = None
    end_line: int | None = None


class RepositoryGraphEdgeResponse(BaseModel):
    """A directed, evidence-bearing repository relationship."""

    source: str
    target: str
    kind: str
    evidence: str | None = None


class RepositoryGraphSummaryResponse(BaseModel):
    """Aggregate values suitable for repository overview visualizations."""

    files: int
    symbols: int
    classes: int
    functions: int
    relationships: int
    parse_errors: int
    scan_errors: int
    languages: dict[str, int]
    relationship_kinds: dict[str, int]


class RepositoryGraphResponse(BaseModel):
    """Language-neutral graph projection for interactive clients."""

    repository_id: str
    summary: RepositoryGraphSummaryResponse
    nodes: list[RepositoryGraphNodeResponse]
    edges: list[RepositoryGraphEdgeResponse]


class RepositoryDebugRequest(BaseModel):
    """A Python bug report, optionally accompanied by a traceback."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(default="", max_length=8000)
    traceback: str = Field(default="", max_length=30000)
    top_k: int = Field(default=8, ge=1, le=30)
    context_limit: int = Field(default=12, ge=0, le=50)
    token_budget: int = Field(default=8000, ge=256, le=30000)
    max_output_tokens: int = Field(default=1200, ge=1, le=4000)

    @model_validator(mode="after")
    def require_bug_input(self):
        if not self.description.strip() and not self.traceback.strip():
            raise ValueError("Provide a bug description, a traceback, or both.")
        return self


class DebugTracebackFrameResponse(BaseModel):
    path: str
    line: int
    function: str


class RepositoryDebugResponse(BaseModel):
    """Structured traceback facts plus a cited repository investigation."""

    repository_id: str
    description: str
    exception_type: str | None
    exception_message: str | None
    frames: list[DebugTracebackFrameResponse]
    innermost_frame: DebugTracebackFrameResponse | None
    answer: str
    model: str
    citations: list[AnswerCitationResponse]
    citation_fallback_used: bool
