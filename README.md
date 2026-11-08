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
