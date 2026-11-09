from repox.cli import main


def test_cli_prints_repository_summary(capsys):
    main(["tests/fixtures/sample_repo"])
    output = capsys.readouterr().out
    assert "Python files: 3" in output
    assert "Classes: 1" in output
    assert "Local file dependencies: 2" in output
    assert "main.py -> services.py" in output
    assert "services.py -> database.py" in output


def test_cli_outputs_mermaid(capsys):
    main(["tests/fixtures/sample_repo", "--format", "mermaid"])
    output = capsys.readouterr().out
    assert output.startswith("flowchart LR")
    assert '["main.py"]' in output
    assert '["services.py"]' in output
    assert '["database.py"]' in output
    assert "-->" in output


def test_cli_rejects_invalid_format():
    try:
        main(["tests/fixtures/sample_repo", "--format", "json"])
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError("Expected invalid format to exit with code 2")
