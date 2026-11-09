from pathlib import Path

from repox.analyzers.repository_analyzer import analyze_repository

FIXTURE_ROOT = Path(__file__).parent.parent / "fixtures" / "sample_repo"


def test_analyze_repository_runs_complete_pipeline():
    analysis = analyze_repository(FIXTURE_ROOT)

    assert len(analysis.files) == 3
    assert len(analysis.import_relationships) == 2
    assert analysis.symbol_relationships
    assert analysis.graph.nodes
    assert analysis.graph.edges
    assert analysis.validation_errors == []
    assert analysis.graph_is_valid is True


def test_analysis_separates_import_and_symbol_relationships():
    analysis = analyze_repository(FIXTURE_ROOT)

    assert all(edge.kind == "imports" for edge in analysis.import_relationships)
    assert all(
        edge.kind in {"calls", "inherits"} for edge in analysis.symbol_relationships
    )
    assert len(analysis.relationships) == (
        len(analysis.import_relationships) + len(analysis.symbol_relationships)
    )


def test_analyze_repository_rejects_non_directory(tmp_path):
    file_path = tmp_path / "not-a-directory.txt"
    file_path.write_text("not a directory", encoding="utf-8")

    try:
        analyze_repository(file_path)
    except NotADirectoryError:
        pass
    else:
        raise AssertionError("Expected NotADirectoryError")
