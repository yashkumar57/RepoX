from pathlib import Path

from repox.analyzers.repository_analyzer import analyze_repository
from repox.visualization import build_repository_visualization

FIXTURE_ROOT = Path(__file__).parent.parent / "fixtures" / "sample_repo"


def test_visualization_projection_contains_source_located_graph_data():
    analysis = analyze_repository(FIXTURE_ROOT)

    projection = build_repository_visualization(analysis)

    assert projection["summary"]["files"] == 3
    assert projection["summary"]["languages"] == {"python": 3}
    assert projection["summary"]["symbols"] > 0
    assert projection["nodes"]
    assert projection["edges"]
    function = next(node for node in projection["nodes"] if node["kind"] == "function")
    assert function["path"]
    assert function["start_line"] is not None
