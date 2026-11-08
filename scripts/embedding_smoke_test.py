"""Run a local semantic-embedding smoke test against a repository."""

import argparse
from math import sqrt
from pathlib import Path

from repox.analyzers.repository_analyzer import analyze_repository
from repox.chunking import chunk_repository
from repox.embeddings import CodeRankEmbedder, embed_chunks


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding dimensions do not match")
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        raise ValueError("Cannot compare a zero-length embedding")
    dot_product = sum(a * b for a, b in zip(left, right, strict=True))
    return dot_product / (left_norm * right_norm)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Embed repository chunks and rank them for a natural-language query."
        )
    )
    parser.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument(
        "--query",
        default="Where does RepoX resolve calls to imported functions?",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--device", choices=("cpu", "cuda"), default=None)
    args = parser.parse_args()

    if args.top_k < 1:
        parser.error("--top-k must be at least 1")

    analysis = analyze_repository(args.root)
    chunks = chunk_repository(analysis)
    if not chunks:
        raise SystemExit("No semantic chunks were produced for this repository.")

    embedder = CodeRankEmbedder(
        device=args.device,
        batch_size=args.batch_size,
    )
    embedded_chunks = embed_chunks(chunks, embedder)
    query_vector = embedder.embed_query(args.query)

    ranked = sorted(
        (
            (
                _cosine_similarity(query_vector, item.vector),
                item.chunk,
            )
            for item in embedded_chunks
        ),
        key=lambda result: result[0],
        reverse=True,
    )

    print(f"Repository: {analysis.root}")
    print(f"Embedding model: {embedder.model_name}")
    print(f"Embedding dimensions: {embedder.dimension}")
    print(f"Chunks embedded: {len(embedded_chunks)}")
    print(f"Query: {args.query}")
    print("\nTop matches:")

    for score, chunk in ranked[: args.top_k]:
        print(
            f"{score:.4f}  {chunk.file_path}:{chunk.start_line}-"
            f"{chunk.end_line}  [{chunk.kind}] {chunk.symbol_name}"
        )


if __name__ == "__main__":
    main()
