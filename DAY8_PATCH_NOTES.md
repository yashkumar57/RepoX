# RepoX Day 8 patch

This patch adds persistent local vector indexing and semantic retrieval.

## Files added

- `src/repox/vector_store/base.py`: storage protocol and vector match model.
- `src/repox/vector_store/chroma.py`: persistent ChromaDB adapter.
- `src/repox/indexing/indexer.py`: incremental repository synchronization.
- `src/repox/indexing/search.py`: natural-language semantic retrieval.
- `src/repox/models/search.py`: typed search result.
- `tests/unit/test_indexing.py`: incremental indexing and search tests.
- `tests/unit/test_chroma_store.py`: ChromaDB persistence and adapter tests.
- `docs/decisions/ADR-003-persistent-vector-index.md`: architecture decision.

## Files updated

- `pyproject.toml`: adds the optional `vector-store` dependency group.
- `DAY8_GITIGNORE_ADDITION.txt`: contains the one ignore rule to append to the existing `.gitignore`. This avoids overwriting any project-specific ignore rules.
- `README.md`: documents installation, indexing and search.

## Apply

Extract this ZIP into the RepoX project root and allow the files to merge/replace.
Append the single line from `DAY8_GITIGNORE_ADDITION.txt` to your existing `.gitignore`
(the existing ZIP ignore rule is preserved). Then run:

```powershell
python -m pip install -e ".[dev,embeddings,vector-store]"
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
```

The default persistent index is created under `.repox/index/` inside the
repository. It is local, rebuildable data and must not be committed.

## API example

```python
from pathlib import Path

from repox.analyzers.repository_analyzer import analyze_repository
from repox.embeddings.code_rank import CodeRankEmbedder
from repox.indexing.indexer import RepositoryIndexer
from repox.indexing.search import SemanticSearchService
from repox.vector_store.chroma import ChromaVectorStore

root = Path(".").resolve()
analysis = analyze_repository(root)
provider = CodeRankEmbedder()
store = ChromaVectorStore.for_repository(root)

report = RepositoryIndexer(store, provider).index(analysis)
print(report)

results = SemanticSearchService(store, provider).search(
    "Where are imported function calls resolved?", top_k=5
)
for result in results:
    chunk = result.chunk
    print(result.score, chunk.file_path, chunk.start_line, chunk.end_line)
    print(chunk.content)
```

## Validation performed while preparing this patch

- `python -m pytest -q`: 101 passed, 1 skipped.
- `python -m compileall -q src tests`: passed.
- ChromaDB integration tests are included but were skipped in the isolated
  build environment because ChromaDB was not installed there. They should run
  in the user's project environment, where ChromaDB 1.5.9 is installed.
- Ruff could not be run in the isolated build environment because it had no
  network access to install Ruff. Run the two Ruff commands above locally.


### ChromaDB 1.5.x compatibility correction

`ChromaVectorStore.configure()` excludes the immutable `hnsw:space` setting from `Collection.modify()` metadata updates. ChromaDB accepts `hnsw:space` when a collection is created but rejects it in later metadata modifications, even when unchanged.
