"""Request and response schemas for repository API operations."""

from pydantic import BaseModel, ConfigDict, Field


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
