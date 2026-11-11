from pathlib import Path

import pytest

from repox.languages import LanguageRegistry, PythonLanguageAdapter
from repox.scanner import scan_repository


class FakeAdapter:
    language = "sample"
    extensions = frozenset({".sample"})

    def parse(self, source: str, *, path: str):
        from repox.models.repository import FileInfo

        return FileInfo(path=path, language=self.language)

    def resolve_imports(self, repository_root: Path, files):
        return []

    def resolve_symbols(self, files):
        return []


def test_default_registry_exposes_python_reference_adapter():
    registry = LanguageRegistry([PythonLanguageAdapter()])

    assert registry.languages == ("python",)
    assert registry.for_path("src/example.py") is not None
    assert registry.for_path("src/example.sample") is None


def test_registry_rejects_duplicate_extensions():
    registry = LanguageRegistry([FakeAdapter()])

    class ConflictingAdapter(FakeAdapter):
        language = "other"

    with pytest.raises(ValueError, match="already registered"):
        registry.register(ConflictingAdapter())


def test_scanner_dispatches_through_registered_adapter(tmp_path):
    (tmp_path / "module.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (tmp_path / "module.sample").write_text("sample source", encoding="utf-8")
    registry = LanguageRegistry([PythonLanguageAdapter(), FakeAdapter()])

    result = scan_repository(tmp_path, registry)

    assert set(result.files) == {"module.py", "module.sample"}
    assert result.files["module.py"].language == "python"
    assert result.files["module.sample"].language == "sample"


def test_scanner_ignores_unregistered_extensions(tmp_path):
    (tmp_path / "main.rs").write_text("fn main() {}", encoding="utf-8")

    result = scan_repository(tmp_path)

    assert result.files == {}
    assert result.errors == []


def test_analyzer_runs_registered_adapter_and_shared_graph_pipeline(tmp_path):
    from repox.analyzers.repository_analyzer import analyze_repository

    (tmp_path / "module.sample").write_text("sample source", encoding="utf-8")
    registry = LanguageRegistry([FakeAdapter()])

    analysis = analyze_repository(tmp_path, registry)

    assert list(analysis.files) == ["module.sample"]
    assert analysis.files["module.sample"].language == "sample"
    assert "file:module.sample" in analysis.graph.nodes
    assert analysis.graph.validate() == []
