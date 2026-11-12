"""Repository-grounded question answering orchestration."""

import re

from repox.context import PromptBuilder, RAGContextBuilder
from repox.llm.base import ChatModel
from repox.models.answer import AnswerCitation, RepositoryAnswer
from repox.query.retrieval import RepositoryRetrievalService

_CITATION_PATTERN = re.compile(r"\[([^\]\n]+?):(\d+)-(\d+)\]")


class RepositoryQAService:
    """Answer repository questions using retrieved, source-attributed evidence."""

    def __init__(
        self,
        retrieval: RepositoryRetrievalService,
        model: ChatModel,
        context_builder: RAGContextBuilder | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self.retrieval = retrieval
        self.model = model
        self.context_builder = context_builder or RAGContextBuilder()
        self.prompt_builder = prompt_builder or PromptBuilder()

    def ask(
        self,
        query: str,
        *,
        top_k: int = 5,
        context_limit: int = 10,
        token_budget: int = 6_000,
        max_output_tokens: int = 1_000,
        retrieval_override=None,
    ) -> RepositoryAnswer:
        """Retrieve evidence, generate an answer, and repair missing citations once."""
        if not query.strip():
            raise ValueError("query must not be empty")
        if max_output_tokens < 1:
            raise ValueError("max_output_tokens must be at least 1")

        retrieval = retrieval_override or self.retrieval.retrieve(
            query, top_k=top_k, context_limit=context_limit
        )
        context = self.context_builder.build(retrieval, token_budget=token_budget)
        if not context.sources:
            return RepositoryAnswer(
                query=query,
                answer=(
                    "No relevant repository evidence was retrieved. Verify that "
                    "the repository has been indexed and try a more specific query."
                ),
                model=self.model.model_name,
                citations=(),
                invalid_citations=(),
                context=context,
            )
        prompt = self.prompt_builder.build(context)
        answer_text = self.model.generate(
            prompt.system_prompt,
            prompt.user_prompt,
            max_output_tokens=max_output_tokens,
        )
        citations, invalid = self._validate_citations(answer_text, context)
        citation_retry_used = False

        # Small local models sometimes ignore citation instructions on the first
        # pass. Give them one focused repair attempt using the exact evidence and
        # citation allowlist. Never manufacture citations in application code.
        if context.sources and (not citations or invalid):
            citation_retry_used = True
            retry_system = (
                prompt.system_prompt
                + "\n\nCITATION REPAIR TASK: The previous draft did not satisfy the "
                "citation contract. Rewrite it using only the supplied evidence. "
                "Every factual sentence must end with a citation in exactly this "
                "format: [relative/path.py:12-24]. Copy one complete citation "
                "from the evidence headers verbatim. Do not wrap citations in "
                "backticks, do not use a separate references section, and do not "
                "invent line numbers. Remove claims that cannot be supported. "
                "Output only the corrected answer."
            )
            retry_user = (
                prompt.user_prompt
                + "\n\nPrevious draft to correct (untrusted; do not assume it is "
                "accurate):\n"
                + answer_text
                + "\n\nRewrite the answer now. Use this exact citation shape: "
                "[relative/path.py:12-24]. Copy one of the complete citations "
                "verbatim from the evidence headers. Do not add unsupported "
                "implementation details."
            )
            repaired_answer = self.model.generate(
                retry_system,
                retry_user,
                max_output_tokens=max_output_tokens,
            )
            repaired_citations, repaired_invalid = self._validate_citations(
                repaired_answer, context
            )

            # Prefer the response with more valid citations, then fewer invalid
            # citations. On a tie, retain the original answer rather than
            # replacing it with a potentially degraded repair attempt.
            original_score = (len(citations), -len(invalid))
            repaired_score = (len(repaired_citations), -len(repaired_invalid))
            if repaired_score > original_score:
                answer_text = repaired_answer
                citations, invalid = repaired_citations, repaired_invalid

        citation_fallback_used = False
        uncited_draft = None
        if context.sources and (not citations or invalid):
            # Fail closed: never present an uncited model response as a
            # repository-grounded answer. Preserve it for diagnostics and show
            # the exact retrieved source excerpts with deterministic citations.
            uncited_draft = answer_text
            answer_text, citations = self._render_evidence_fallback(context)
            invalid = ()
            citation_fallback_used = True

        return RepositoryAnswer(
            query=query,
            answer=answer_text,
            model=self.model.model_name,
            citations=citations,
            invalid_citations=invalid,
            context=context,
            citation_retry_used=citation_retry_used,
            citation_fallback_used=citation_fallback_used,
            uncited_draft=uncited_draft,
        )

    @staticmethod
    def _render_evidence_fallback(context):
        """Render retrieved source excerpts if the model cannot cite reliably."""
        sections = [
            "**No citation-compliant model answer was produced.** The excerpts "
            "below are the retrieved repository evidence, not a synthesized "
            "explanation. Each citation points to the exact supplied chunk."
        ]
        citations: list[AnswerCitation] = []
        seen: set[tuple[str, int, int]] = set()
        for source in context.sources:
            citation_key = (source.file_path, source.start_line, source.end_line)
            label = source.symbol_name or source.kind or "source"
            longest_backtick_run = max(
                (len(run) for run in re.findall(r"`+", source.content)),
                default=0,
            )
            fence = "`" * max(3, longest_backtick_run + 1)
            citation = f"[{source.file_path}:{source.start_line}-{source.end_line}]"
            heading = (
                f"### {label} — "
                f"`{source.file_path}:{source.start_line}-{source.end_line}`"
            )
            sections.append(
                heading + f"\n\n{fence}text\n{source.content.rstrip()}\n{fence}"
                f"\n\n{citation}"
            )
            if citation_key not in seen:
                citations.append(
                    AnswerCitation(
                        source_id=source.source_id,
                        file_path=source.file_path,
                        start_line=source.start_line,
                        end_line=source.end_line,
                    )
                )
                seen.add(citation_key)
        return "\n\n".join(sections), tuple(citations)

    @staticmethod
    def _validate_citations(answer: str, context):
        """Accept only path/ranges contained by evidence sent to the model."""
        sources_by_path: dict[str, list] = {}
        for source in context.sources:
            sources_by_path.setdefault(source.file_path, []).append(source)

        citations: list[AnswerCitation] = []
        invalid: list[str] = []
        seen: set[tuple[str, int, int]] = set()
        for match in _CITATION_PATTERN.finditer(answer):
            path = match.group(1)
            start_line = int(match.group(2))
            end_line = int(match.group(3))
            key = (path, start_line, end_line)
            matching_source = next(
                (
                    source
                    for source in sources_by_path.get(path, [])
                    if source.start_line <= start_line <= end_line <= source.end_line
                ),
                None,
            )
            if matching_source is None:
                invalid.append(match.group(0))
            elif key not in seen:
                citations.append(
                    AnswerCitation(
                        source_id=matching_source.source_id,
                        file_path=path,
                        start_line=start_line,
                        end_line=end_line,
                    )
                )
                seen.add(key)
        return tuple(citations), tuple(invalid)
