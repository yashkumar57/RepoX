"""Tests for safe acquisition of public GitHub repositories."""

from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import patch

import pytest

from repox.ingestion.github import (
    GitHubRepositoryService,
    InvalidRepositoryURLError,
    RepositoryCloneError,
    RepositoryNotFoundError,
)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "not-a-url",
        "http://github.com/openai/whisper",
        "https://gitlab.com/openai/whisper",
        "https://user:password@github.com/openai/whisper",
        "https://github.com:8443/openai/whisper",
        "https://github.com/openai/whisper?tab=readme",
        "https://github.com/openai/whisper/tree/main",
        "https://github.com/openai/%2e%2e",
        "https://github.com/openai/../other",
        "https://github.com//openai/whisper",
    ],
)
def test_rejects_unsupported_repository_urls(url: str, tmp_path: Path) -> None:
    service = GitHubRepositoryService(tmp_path)

    with pytest.raises(InvalidRepositoryURLError):
        service.clone(url)


@patch("repox.ingestion.github.subprocess.run")
def test_clones_repository_into_managed_workspace(run_mock, tmp_path: Path) -> None:
    def successful_clone(command, **kwargs):
        Path(command[-1]).mkdir(parents=True)
        return CompletedProcess(command, 0, stdout="", stderr="")

    run_mock.side_effect = successful_clone
    service = GitHubRepositoryService(tmp_path / "workspace")

    checkout = service.clone("https://github.com/openai/whisper")

    assert checkout.owner == "openai"
    assert checkout.name == "whisper"
    assert checkout.url == "https://github.com/openai/whisper.git"
    assert checkout.branch is None
    assert checkout.path.is_dir()
    assert checkout.path.parent == (tmp_path / "workspace").resolve()
    assert len(checkout.repository_id) == 32
    command = run_mock.call_args.args[0]
    assert command[:5] == ["git", "clone", "--depth", "1", "--single-branch"]
    assert command[-2] == "https://github.com/openai/whisper.git"
    assert run_mock.call_args.kwargs["timeout"] == 300


@patch("repox.ingestion.github.subprocess.run")
def test_supports_git_suffix_and_requested_branch(run_mock, tmp_path: Path) -> None:
    def successful_clone(command, **kwargs):
        Path(command[-1]).mkdir(parents=True)
        return CompletedProcess(command, 0, stdout="", stderr="")

    run_mock.side_effect = successful_clone
    checkout = GitHubRepositoryService(tmp_path).clone(
        "https://github.com/openai/whisper.git/", branch="release/2.0"
    )

    command = run_mock.call_args.args[0]
    assert checkout.name == "whisper"
    assert checkout.branch == "release/2.0"
    assert command[5:7] == ["--branch", "release/2.0"]


@pytest.mark.parametrize(
    "branch",
    ["", "-upload-pack=evil", "main..bad", "main//bad", "bad branch", "../escape"],
)
def test_rejects_invalid_branch_names(branch: str, tmp_path: Path) -> None:
    service = GitHubRepositoryService(tmp_path)

    with pytest.raises(ValueError):
        service.clone("https://github.com/openai/whisper", branch=branch)


@patch("repox.ingestion.github.subprocess.run")
def test_failed_clone_cleans_partial_checkout(run_mock, tmp_path: Path) -> None:
    def failed_clone(command, **kwargs):
        Path(command[-1]).mkdir(parents=True)
        return CompletedProcess(command, 128, stdout="", stderr="repository not found")

    run_mock.side_effect = failed_clone
    service = GitHubRepositoryService(tmp_path)

    with pytest.raises(RepositoryCloneError, match="repository not found"):
        service.clone("https://github.com/openai/missing")

    assert list(tmp_path.iterdir()) == []


@patch("repox.ingestion.github.subprocess.run")
def test_clone_timeout_cleans_partial_checkout(run_mock, tmp_path: Path) -> None:
    def timed_out(command, **kwargs):
        Path(command[-1]).mkdir(parents=True)
        raise TimeoutExpired(command, timeout=kwargs["timeout"])

    run_mock.side_effect = timed_out
    service = GitHubRepositoryService(tmp_path, timeout_seconds=5)

    with pytest.raises(RepositoryCloneError, match="5-second timeout"):
        service.clone("https://github.com/openai/whisper")

    assert list(tmp_path.iterdir()) == []


@patch("repox.ingestion.github.subprocess.run", side_effect=FileNotFoundError)
def test_reports_missing_git_executable(_run_mock, tmp_path: Path) -> None:
    service = GitHubRepositoryService(tmp_path)

    with pytest.raises(RepositoryCloneError, match="Git was not found"):
        service.clone("https://github.com/openai/whisper")


def test_resolves_existing_checkout_metadata_from_managed_workspace(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "repositories"
    repository_id = "a" * 32
    checkout_path = workspace / repository_id
    (checkout_path / ".git").mkdir(parents=True)
    service = GitHubRepositoryService(workspace)

    def git_metadata(command, **kwargs):
        if command[-3:] == ["remote", "get-url", "origin"]:
            return CompletedProcess(
                command,
                0,
                stdout="https://github.com/pallets/itsdangerous.git\n",
                stderr="",
            )
        return CompletedProcess(command, 0, stdout="main\n", stderr="")

    with patch("repox.ingestion.github.subprocess.run", side_effect=git_metadata):
        checkout = service.get_checkout(repository_id)

    assert checkout.repository_id == repository_id
    assert checkout.owner == "pallets"
    assert checkout.name == "itsdangerous"
    assert checkout.branch == "main"
    assert checkout.path == checkout_path.resolve()


def test_rejects_unknown_or_malformed_checkout_id(tmp_path: Path) -> None:
    service = GitHubRepositoryService(tmp_path)

    with pytest.raises(RepositoryNotFoundError):
        service.get_checkout("../../outside")


def test_reuses_existing_checkout_for_same_repository(tmp_path: Path) -> None:
    from repox.ingestion.github import RepositoryCheckout

    service = GitHubRepositoryService(tmp_path / "workspace")
    existing = RepositoryCheckout(
        repository_id="a" * 32,
        owner="pallets",
        name="itsdangerous",
        url="https://github.com/pallets/itsdangerous.git",
        branch="main",
        path=tmp_path / "workspace" / ("a" * 32),
    )
    with patch.object(service, "list_checkouts", return_value=[existing]):
        checkout = service.clone("https://github.com/pallets/itsdangerous")

    assert checkout is existing
