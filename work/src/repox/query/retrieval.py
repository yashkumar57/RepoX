"""Hybrid retrieval combining semantic matches with deterministic graph context."""

from collections import defaultdict
from dataclasses import dataclass, field

from repox.chunking.semantic_chunker import chunk_repository
from repox.indexing.search import SemanticSearchService
from repox.models.analysis import RepositoryAnalysis
from repox.models.chunk import CodeChunk
from repox.models.retrieval import RetrievalResponse, RetrievedChunk


@dataclass
class _CollectedChunk:
    """Mutable accumulator used to merge duplicate retrieval paths."""

    chunk: CodeChunk
    semantic_score: float | None = None
    context_rank: float = float("-inf")
    relationships: set[str] = field(default_factory=set)
    related_to: set[str] = field(default_factory=set)
    evidence: set[str] = field(default_factory=set)


class RepositoryRetrievalService:
    """Retrieve semantically relevant code and its one-hop graph context.

    Semantic search determines the primary matches. The repository graph then
    contributes deterministic callers, callees, parents, children, imports,
    dependents, base classes, and subclasses. Structural context is kept
    distinct from semantic relevance and never receives a fabricated score.
    """

    _OUTGOING_LABELS = {
        "contains": "child",
        "calls": "callee",
        "inherits": "base_class",
        "imports": "import",
    }
    _INCOMING_LABELS = {
        "contains": "parent",
        "calls": "caller",
        "inherits": "subclass",
        "imports": "dependent",
    }

    def __init__(
        self,
        analysis: RepositoryAnalysis,
        semantic_search: SemanticSearchService,
    ) -> None:
        self.analysis = analysis
        self.semantic_search = semantic_search

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        context_limit: int = 10,
    ) -> RetrievalResponse:
        """Return ranked semantic matches followed by deduplicated graph context.

        ``top_k`` controls primary vector matches. ``context_limit`` controls
        additional unique structural chunks. A chunk found through both paths
        appears once and retains its semantic score plus structural links.
        """
        if context_limit < 0:
            raise ValueError("context_limit must be at least 0")

        semantic_matches = self.semantic_search.search(query, top_k=top_k)
        if not semantic_matches:
            return RetrievalResponse(
                query=query,
                results=(),
                semantic_match_count=0,
                structural_context_count=0,
            )

        chunks_by_symbol: dict[str, list[CodeChunk]] = defaultdict(list)
        for chunk in chunk_repository(self.analysis):
            chunks_by_symbol[chunk.symbol_id].append(chunk)

        collected: dict[str, _CollectedChunk] = {}

        # Preserve the vector store's semantic ranking for primary matches.
        for match in semantic_matches:
            item = collected.setdefault(
                match.chunk.id, _CollectedChunk(chunk=match.chunk)
            )
            item.semantic_score = match.score

        # Expand each primary hit by one deterministic graph hop.
        for match in semantic_matches:
            seed_id = match.chunk.symbol_id
            if seed_id not in self.analysis.graph.nodes:
                continue

            neighbors: list[tuple[str, str, str | None]] = []
            for edge in self.analysis.graph.edges:
                if edge.source == seed_id:
                    label = self._OUTGOING_LABELS.get(edge.kind)
                    if label:
                        neighbors.append((edge.target, label, edge.evidence))
                if edge.target == seed_id:
                    label = self._INCOMING_LABELS.get(edge.kind)
                    if label:
                        neighbors.append((edge.source, label, edge.evidence))

            neighbors.sort(key=lambda value: (value[1], value[0], value[2] or ""))

            for neighbor_id, relationship, evidence in neighbors:
                for chunk in chunks_by_symbol.get(neighbor_id, []):
                    item = collected.setdefault(chunk.id, _CollectedChunk(chunk=chunk))
                    item.context_rank = max(item.context_rank, match.score)
                    item.relationships.add(relationship)
                    item.related_to.add(seed_id)
                    if evidence:
                        item.evidence.add(evidence)

        primary = [
            item for item in collected.values() if item.semantic_score is not None
        ]
        structural = [
            item for item in collected.values() if item.semantic_score is None
        ]
        structural.sort(
            key=lambda item: (
                -item.context_rank,
                item.chunk.file_path,
                item.chunk.start_line,
                item.chunk.end_line,
                item.chunk.id,
            )
        )
        selected_structural = structural[:context_limit]

        ordered = primary + selected_structural
        results = tuple(
            RetrievedChunk(
                chunk=item.chunk,
                semantic_score=item.semantic_score,
                relationships=tuple(sorted(item.relationships)),
                related_to=tuple(sorted(item.related_to)),
                evidence=tuple(sorted(item.evidence)),
            )
            for item in ordered
        )

        return RetrievalResponse(
            query=query,
            results=results,
            semantic_match_count=len(primary),
            structural_context_count=len(selected_structural),
        )
