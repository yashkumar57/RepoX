# RepoX

Repository intelligence platform for understanding unfamiliar GitHub codebases
through architecture, dependencies, execution flows, and contextual explanations.

## Installation

Create and activate a virtual environment, then install the required extras:

```powershell
python -m pip install -e ".[dev,embeddings,vector-store]"
```

The extras are separated intentionally:

- `dev`: tests and linting.
- `embeddings`: local CodeRankEmbed inference.
- `vector-store`: persistent local ChromaDB storage.

Repository parsing and deterministic analysis do not require the embedding or
vector-store extras.

## Day 8: Persistent semantic indexing

RepoX stores a local, rebuildable semantic index under `.repox/index/` inside
the repository being indexed. This directory is ignored by Git. It is created
on first use; users do not need to configure a database server or create a
hosted database account.

### Index a repository

```python
from pathlib import Path

from repox.analyzers.repository_analyzer import analyze_repository
from repox.embeddings.code_rank import CodeRankEmbedder
from repox.indexing.indexer import RepositoryIndexer
from repox.vector_store.chroma import ChromaVectorStore

root = Path(".").resolve()
analysis = analyze_repository(root)
provider = CodeRankEmbedder()  # Loads the model locally on first use.
store = ChromaVectorStore.for_repository(root)

report = RepositoryIndexer(store, provider).index(analysis)
print(report)
```

### Search indexed code

```python
from repox.indexing.search import SemanticSearchService

search = SemanticSearchService(store, provider)
for result in search.search("Where are imported function calls resolved?", top_k=5):
    chunk = result.chunk
    print(f"{result.score:.4f} {chunk.file_path}:{chunk.start_line}-{chunk.end_line}")
    print(chunk.content)
```

Scores are cosine similarity (`1 - cosine distance`); higher is more similar.
Each result includes the exact stored source content, repository-relative path,
inclusive line range, symbol identity, and structural metadata.

### Incremental indexing behavior

- Unchanged chunk ID and embedding-input hash: reuse the existing vector.
- Existing chunk ID with changed content: generate and upsert a new vector.
- Chunk no longer present: delete its stale vector after successful embedding.
- Repository scan errors: abort synchronization to avoid deleting records for
  files that could not be read.
- Different model or vector dimension: reject the operation rather than mix
  incompatible embeddings in one collection.

The index can always be rebuilt from repository source. Do not commit `.repox/`
contents or treat the vector database as the source of truth.


## Day 9: Hybrid repository retrieval

Day 9 adds a retrieval layer that combines semantic matches with deterministic
relationships from the repository graph. Semantic search chooses the primary
code matches; graph traversal adds one-hop context such as callers, callees,
containing scopes, child symbols, imports, dependents, and inheritance links.

```python
from pathlib import Path

from repox.analyzers.repository_analyzer import analyze_repository
from repox.embeddings.code_rank import CodeRankEmbedder
from repox.indexing.search import SemanticSearchService
from repox.query.retrieval import RepositoryRetrievalService
from repox.vector_store.chroma import ChromaVectorStore

root = Path(".").resolve()
analysis = analyze_repository(root)
provider = CodeRankEmbedder()
store = ChromaVectorStore.for_repository(root)

retrieval = RepositoryRetrievalService(
    analysis,
    SemanticSearchService(store, provider),
)
response = retrieval.retrieve(
    "Where is the HTTP request handled?",
    top_k=5,
    context_limit=10,
)

for item in response.results:
    chunk = item.chunk
    if item.is_semantic_match:
        print(f"SEMANTIC {item.semantic_score:.4f}", end=" ")
    else:
        print(f"CONTEXT {','.join(item.relationships)}", end=" ")
    print(f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line}")
    print(chunk.content)
```

The response keeps semantic scores separate from structural context. A graph
neighbor is not assigned an invented similarity score. Every returned item
contains exact source text, a repository-relative path, inclusive line numbers,
and (for structural context) the graph relationship and its source evidence.
Duplicate chunks reached through multiple graph paths are merged. The
`context_limit` controls the maximum number of additional unique context
chunks; it does not reduce the requested semantic `top_k`.

## Day 10: RAG context construction

Day 10 turns hybrid retrieval results into a bounded, source-attributed context
package. Retrieval and context construction remain separate: the retrieval layer
finds evidence, while the context builder selects what fits the configured
budget. Semantic matches are prioritized by score; structural context follows
with deterministic relationship priority. Chunks are included whole or omitted
so source code and line ranges are never silently truncated.

```python
from repox.context import PromptBuilder, RAGContextBuilder

retrieved = retrieval.retrieve(
    "Where is the HTTP request handled?",
    top_k=5,
    context_limit=10,
)
context = RAGContextBuilder().build(retrieved, token_budget=6_000)
prompt = PromptBuilder().build(context)

print(context.estimated_tokens, context.token_budget)
for source in context.sources:
    print(source.file_path, source.start_line, source.end_line)

# Provider adapters can pass these two strings to their chat-completion API.
messages = [
    {"role": "system", "content": prompt.system_prompt},
    {"role": "user", "content": prompt.user_prompt},
]
```

`ApproximateTokenCounter` provides a dependency-free estimate based on UTF-8
byte length. It is useful for development and conservative budgeting, but it is
not an exact model tokenizer. For strict context-window limits, inject the
selected LLM's tokenizer by implementing the small `TokenCounter.count(text)`
interface. The context budget applies to the rendered evidence package; the
final prompt's estimated token count is reported separately because system and
provider message framing also consume tokens.

The prompt explicitly treats retrieved source as untrusted evidence, requires
source-grounded claims, and asks the model to cite exact paths and inclusive line
ranges. No LLM SDK or provider is installed or invoked in this layer.
