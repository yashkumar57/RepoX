"""Deterministic traceback triage and source-constrained debugging."""

from dataclasses import dataclass, replace
from pathlib import PurePosixPath

from repox.chunking.semantic_chunker import chunk_repository
from repox.debugging.traceback import (
    TracebackAnalysis,
    extract_exception,
    parse_traceback,
)
from repox.models.answer import RepositoryAnswer
from repox.models.retrieval import RetrievalResponse, RetrievedChunk
from repox.query.qa import RepositoryQAService
from repox.query.retrieval import RepositoryRetrievalService


@dataclass(frozen=True)
class DebuggingResult:
    """Traceback facts and the cited repository analysis."""

    description: str
    traceback: TracebackAnalysis
    answer: RepositoryAnswer


class DebuggingService:
    """Investigate bugs without confusing generic symptoms with repo evidence."""

    def __init__(self, qa_service: RepositoryQAService) -> None:
        self.qa_service = qa_service

    def analyze(
        self,
        *,
        description: str = "",
        traceback_text: str = "",
        top_k: int = 8,
        context_limit: int = 12,
        token_budget: int = 8_000,
        max_output_tokens: int = 1_200,
    ) -> DebuggingResult:
        description = description.strip()
        traceback_text = traceback_text.strip()
        if not description and not traceback_text:
            raise ValueError("Provide a bug description, a traceback, or both.")

        parsed = parse_traceback(traceback_text)
        if not parsed.exception_type and description:
            exception_type, exception_message = extract_exception(description)
            if exception_type:
                parsed = TracebackAnalysis(
                    frames=parsed.frames,
                    exception_type=exception_type,
                    exception_message=exception_message,
                    raw_last_line=parsed.raw_last_line,
                )
        query = self._build_query(description, parsed)

        # A traceback path may belong to an application that is not the active
        # checkout (as with externally supplied bug reports). Exact frame mapping
        # is strongest evidence, but description-based semantic retrieval is
        # still useful for finding candidate implementations to inspect. Keep
        # those candidates explicitly distinct from an exact traceback match.
        if not isinstance(
            getattr(self.qa_service, "retrieval", None),
            RepositoryRetrievalService,
        ):
            if not parsed.frames:
                answer = self._diagnose_without_repository_evidence(
                    query,
                    token_budget=token_budget,
                    max_output_tokens=max_output_tokens,
                )
                return DebuggingResult(description, parsed, answer)
            # Preserve compatibility with lightweight QA adapters and tests.
            answer = self.qa_service.ask(
                query,
                top_k=top_k,
                context_limit=context_limit,
                token_budget=token_budget,
                max_output_tokens=max_output_tokens,
            )
            return DebuggingResult(description, parsed, answer)

        if parsed.frames:
            retrieval = self._retrieve_traceback_evidence(
                query, parsed, context_limit=context_limit
            )
        else:
            retrieval = RetrievalResponse(query, (), 0, 0)
        exact_frame_match = bool(retrieval.results)
        if not exact_frame_match:
            # Use the bug description and parsed exception to find relevant
            # repository candidates even when traceback paths are external or
            # absent. These are investigation leads, never proof of the failing
            # line; the prompt and UI state this distinction explicitly.
            retrieval_parts = (
                description,
                parsed.exception_type or "",
                parsed.exception_message or "",
                " ".join(frame.function for frame in parsed.frames),
            )
            retrieval_query = " ".join(part for part in retrieval_parts if part)
            retrieval_query = retrieval_query or query
            retrieval = self.qa_service.retrieval.retrieve(
                retrieval_query, top_k=max(top_k, 10), context_limit=context_limit
            )

        if not retrieval.results:
            answer = self._diagnose_without_repository_evidence(
                query,
                token_budget=token_budget,
                max_output_tokens=max_output_tokens,
                evidence_status=(
                    "no matching source frame; no related repository candidates"
                    if parsed.frames
                    else "no related repository candidates"
                ),
            )
            return DebuggingResult(description, parsed, answer)

        if not exact_frame_match:
            retrieval_note = (
                "No supplied traceback frame matched an indexed source location. "
                "Treat retrieved chunks only as semantically related candidates; "
                "do not claim they contain the failing line or prove the root cause."
                if parsed.frames
                else "No traceback was supplied. Treat retrieved chunks as related "
                "implementation candidates, not proof of the failing execution path."
            )
            retrieval = replace(
                retrieval,
                query=f"{query}\n\nRepository evidence constraint: {retrieval_note}",
            )

        answer = self.qa_service.ask(
            query,
            top_k=top_k,
            context_limit=context_limit,
            token_budget=token_budget,
            max_output_tokens=max_output_tokens,
            retrieval_override=retrieval,
        )
        if not exact_frame_match:
            status = (
                "No traceback frame matched an indexed source location. "
                "The following are semantically related repository candidates, "
                "not verified locations of the failure."
                if parsed.frames
                else "No traceback was supplied. The following source is retrieved "
                "from the bug description and should be treated as related evidence, "
                "not proof of the failing execution path."
            )
            answer = RepositoryAnswer(
                query=answer.query,
                answer=f"**Repository evidence status:** {status}\n\n{answer.answer}",
                model=answer.model,
                citations=answer.citations,
                invalid_citations=answer.invalid_citations,
                context=answer.context,
                citation_retry_used=answer.citation_retry_used,
                citation_fallback_used=answer.citation_fallback_used,
                uncited_draft=answer.uncited_draft,
            )
        return DebuggingResult(description, parsed, answer)

    @staticmethod
    def _build_query(description: str, parsed: TracebackAnalysis) -> str:
        facts = []
        if parsed.exception_type:
            facts.append(
                f"Exception: {parsed.exception_type}: {parsed.exception_message}"
            )
        if parsed.frames:
            facts.append("Python traceback frames (outermost to innermost):")
            facts.extend(
                f"- {frame.path}:{frame.line} in {frame.function}"
                for frame in parsed.frames
            )
        if parsed.raw_last_line and not parsed.exception_type:
            facts.append(f"Traceback terminal line: {parsed.raw_last_line}")
        return (
            "Investigate this Python bug using the supplied report and any "
            "repository evidence explicitly provided. Separate directly "
            "observed facts from hypotheses. "
            "Explain the failing operation, execution path, evidence-ranked causes, "
            "and smallest safe fix. A traceback frame identifies where an exception "
            "was raised; it does not by itself prove a helper's return contract. "
            "When source evidence is available, inspect the exact expression at the "
            "innermost frame before proposing a fix. For example, if the failing "
            "source line is `return user.profile` and the exception says a NoneType "
            "has no attribute `profile`, the observed failing receiver is `user`; "
            "do not claim that the current function returned None. Recommend a "
            "guard at the actual dereference site unless source proves another fix. "
            "Do not invent files, symbols, or line numbers.\n\n"
            f"Bug description:\n{description or '(not provided)'}\n\n"
            "Deterministically parsed traceback facts:\n"
            + ("\n".join(facts) if facts else "No standard Python frames were parsed.")
        )

    def _retrieve_traceback_evidence(
        self, query: str, parsed: TracebackAnalysis, *, context_limit: int
    ) -> RetrievalResponse:
        """Map traceback frames to the narrowest unambiguous source chunks.

        A basename/suffix match is accepted only when it identifies one file in
        the indexed repository. This prevents same-named files in different
        packages from being treated as interchangeable evidence.
        """
        analysis = self.qa_service.retrieval.analysis
        chunks = chunk_repository(analysis)
        chunks_by_path: dict[str, list] = {}
        for chunk in chunks:
            chunks_by_path.setdefault(self._normalize_path(chunk.file_path), []).append(
                chunk
            )

        selected: dict[str, RetrievedChunk] = {}
        for frame in parsed.frames:
            frame_path = self._normalize_path(frame.path)
            exact_candidates = [path for path in chunks_by_path if path == frame_path]
            if exact_candidates:
                path_candidates = exact_candidates
            else:
                path_candidates = [
                    path
                    for path in chunks_by_path
                    if path.endswith("/" + frame_path)
                    or frame_path.endswith("/" + path)
                ]
            # A path suffix is useful for tracebacks captured from a different
            # checkout root, but only if it resolves to one unique repo file.
            if len(path_candidates) != 1:
                continue

            candidates = [
                chunk
                for chunk in chunks_by_path[path_candidates[0]]
                if chunk.start_line <= frame.line <= chunk.end_line
            ]
            if not candidates:
                continue

            # Prefer the smallest enclosing chunk (usually the exact function)
            # instead of sending overlapping module/class/function chunks.
            chunk = min(
                candidates,
                key=lambda item: (
                    item.end_line - item.start_line,
                    item.kind != "function",
                    item.start_line,
                    item.id,
                ),
            )
            selected[chunk.id] = RetrievedChunk(
                chunk=chunk,
                semantic_score=None,
                relationships=("traceback_frame",),
                evidence=(
                    f"Exact traceback location mapped to {chunk.file_path}:"
                    f"{frame.line}",
                ),
            )

        results = tuple(
            sorted(
                selected.values(),
                key=lambda item: (
                    item.chunk.file_path,
                    item.chunk.start_line,
                    item.chunk.id,
                ),
            )[: max(context_limit, 1)]
        )
        return RetrievalResponse(
            query=query,
            results=results,
            semantic_match_count=0,
            structural_context_count=len(results),
        )

    @staticmethod
    def _normalize_path(path: str) -> str:
        normalized = str(PurePosixPath(path.replace("\\", "/")))
        while normalized.startswith("./"):
            normalized = normalized[2:]
        return normalized.lstrip("/")

    def _diagnose_without_repository_evidence(
        self,
        query: str,
        *,
        token_budget: int,
        max_output_tokens: int,
        evidence_status: str = "unavailable",
    ) -> RepositoryAnswer:
        """Generate a symptom-level diagnosis without repository citations."""
        context = self.qa_service.context_builder.build(
            RetrievalResponse(query, (), 0, 0), token_budget=token_budget
        )
        system_prompt = (
            "You are RepoX, a Python debugging assistant. Diagnose only from the "
            "bug description and deterministically parsed exception facts. "
            "No repository source code has been verified for this request. "
            "Treat exception type, exception message, and parsed traceback frames "
            "as observed facts. Treat explanations about return values, call "
            "contracts, and control flow as hypotheses unless the supplied "
            "traceback directly proves them. Never state that a function returns "
            "None unless that return is directly visible in supplied source or "
            "traceback text. Do not invent helper functions, filenames, symbols, "
            "or line numbers. Give a concise diagnosis, label hypotheses, and "
            "suggest the smallest safe check. Do not describe a function as "
            "returning None merely because a NoneType attribute error occurred: "
            "the traceback proves only that the receiver of the failing attribute "
            "access was None. If the failing source expression is unavailable, "
            "do not name a specific function as the source of that None value. "
            "Any code must be a generic illustrative pattern, not a patch to the "
            "user's repository. Do not suggest a default identity or username as "
            "an authentication fallback. Do not emit repository citations."
        )
        user_prompt = (
            f"Bug report and parsed facts:\n{query}\n\n"
            f"Repository evidence status: {evidence_status}. Provide a "
            "symptom-level diagnosis only. Explicitly separate observed facts "
            "from hypotheses and avoid presenting an inferred call path as proven."
        )
        model = self.qa_service.model
        answer_text = model.generate(
            system_prompt,
            user_prompt,
            max_output_tokens=max_output_tokens,
        )
        return RepositoryAnswer(
            query=query,
            answer=(
                f"**Repository evidence status: {evidence_status}.** The diagnosis "
                "uses only the supplied report, exception, and parsed traceback; "
                "it is not verified against indexed source code.\n\n" + answer_text
            ),
            model=model.model_name,
            citations=(),
            invalid_citations=(),
            context=context,
        )

    def _no_matching_source_answer(
        self,
        query: str,
        parsed: TracebackAnalysis,
        token_budget: int,
        max_output_tokens: int = 1_200,
    ) -> RepositoryAnswer:
        frame_list = "\n".join(
            f"- `{frame.path}:{frame.line}` in `{frame.function}`"
            for frame in parsed.frames
        )
        query_with_frames = (
            query
            + "\n\nTraceback locations that could not be mapped to indexed source:\n"
            + frame_list
        )
        return self._diagnose_without_repository_evidence(
            query_with_frames,
            token_budget=token_budget,
            max_output_tokens=max_output_tokens,
            evidence_status="no matching source frame",
        )
