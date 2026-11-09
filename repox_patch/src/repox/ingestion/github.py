"""Acquire public GitHub repositories into a RepoX-managed workspace."""

from __future__ import annotations

import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

_COMPONENT_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


class InvalidRepositoryURLError(ValueError):
    """Raised when a URL is not a supported public GitHub repository URL."""


class RepositoryCloneError(RuntimeError):
    """Raised when Git cannot clone a repository successfully."""


class RepositoryNotFoundError(FileNotFoundError):
    """Raised when a managed repository checkout cannot be found."""


@dataclass(frozen=True, slots=True)
class RepositoryCheckout:
    """Metadata and local path for a successfully acquired repository."""

    repository_id: str
    owner: str
    name: str
    url: str
    branch: str | None
    path: Path


def _parse_github_url(repository_url: str) -> tuple[str, str, str]:
    """Validate and normalize an HTTPS GitHub repository URL."""
    if not isinstance(repository_url, str) or not repository_url.strip():
        raise InvalidRepositoryURLError("A GitHub repository URL is required.")

    candidate = repository_url.strip()
    try:
        parsed = urlsplit(candidate)
        port = parsed.port
    except ValueError as exc:
        raise InvalidRepositoryURLError("The repository URL is malformed.") from exc

    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.query
        or parsed.fragment
    ):
        raise InvalidRepositoryURLError(
            "Only public HTTPS URLs on github.com are supported."
        )

    if "%" in parsed.path or "\\" in parsed.path:
        raise InvalidRepositoryURLError(
            "Encoded or escaped repository paths are not supported."
        )

    path = parsed.path
    if path.endswith("/"):
        path = path[:-1]
    if not path.startswith("/") or path.startswith("//"):
        raise InvalidRepositoryURLError("The repository URL path is invalid.")
    parts = path[1:].split("/")
    if len(parts) != 2 or any(not part for part in parts):
        raise InvalidRepositoryURLError(
            "Use a repository URL in the form https://github.com/owner/repository."
        )

    owner, name = parts
    if name.endswith(".git"):
        name = name[:-4]

    if (
        not _COMPONENT_PATTERN.fullmatch(owner)
        or not _COMPONENT_PATTERN.fullmatch(name)
        or owner in {".", ".."}
        or name in {".", ".."}
    ):
        raise InvalidRepositoryURLError("The owner or repository name is invalid.")

    normalized_url = f"https://github.com/{owner}/{name}.git"
    return owner, name, normalized_url


def _validate_branch(branch: str | None) -> str | None:
    if branch is None:
        return None
    if (
        not isinstance(branch, str)
        or not branch
        or branch.startswith("-")
        or branch.startswith("/")
        or branch.endswith(("/", "."))
        or ".." in branch
        or "@{" in branch
        or "//" in branch
        or any(character.isspace() or ord(character) < 32 for character in branch)
        or any(character in branch for character in "~^:?*[\\")
    ):
        raise ValueError("The branch name is not a valid Git branch reference.")

    invalid_component = any(
        component.startswith(".") or component.endswith(".lock")
        for component in branch.split("/")
    )
    if invalid_component:
        raise ValueError("The branch name is not a valid Git branch reference.")

    return branch


class GitHubRepositoryService:
    """Clone public GitHub repositories into isolated RepoX workspaces."""

    def __init__(
        self,
        workspace: str | Path | None = None,
        *,
        git_executable: str = "git",
        timeout_seconds: int = 300,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero.")
        self.workspace = Path(workspace or Path.home() / ".repox" / "repositories")
        self.git_executable = git_executable
        self.timeout_seconds = timeout_seconds

    def get_checkout(self, repository_id: str) -> RepositoryCheckout:
        """Resolve a previously cloned repository from its managed identifier."""
        if not re.fullmatch(r"[a-f0-9]{32}", repository_id):
            raise RepositoryNotFoundError("The repository ID is invalid or unknown.")

        workspace = self.workspace.expanduser().resolve()
        path = (workspace / repository_id).resolve()
        if (
            path.parent != workspace
            or not path.is_dir()
            or not (path / ".git").exists()
        ):
            raise RepositoryNotFoundError(
                f"Repository {repository_id} was not found in the managed workspace."
            )

        try:
            remote = subprocess.run(
                [self.git_executable, "-C", str(path), "remote", "get-url", "origin"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            ).stdout.strip()
            owner, name, normalized_url = _parse_github_url(remote.removesuffix(".git"))
            branch_result = subprocess.run(
                [self.git_executable, "-C", str(path), "branch", "--show-current"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError, InvalidRepositoryURLError) as exc:
            raise RepositoryNotFoundError(
                f"Repository {repository_id} metadata could not be read."
            ) from exc

        branch = branch_result.stdout.strip() or None
        return RepositoryCheckout(
            repository_id=repository_id,
            owner=owner,
            name=name,
            url=normalized_url,
            branch=branch,
            path=path,
        )

    def clone(
        self,
        repository_url: str,
        *,
        branch: str | None = None,
    ) -> RepositoryCheckout:
        """Clone a public GitHub repository and return its checkout metadata."""
        owner, name, normalized_url = _parse_github_url(repository_url)
        branch = _validate_branch(branch)

        self.workspace.mkdir(parents=True, exist_ok=True)
        workspace = self.workspace.resolve()
        repository_id = uuid.uuid4().hex
        destination = workspace / repository_id

        command = [
            self.git_executable,
            "clone",
            "--depth",
            "1",
            "--single-branch",
        ]
        if branch is not None:
            command.extend(["--branch", branch])
        command.extend(["--", normalized_url, str(destination)])

        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise RepositoryCloneError(
                "Git was not found. Install Git and ensure it is available on PATH."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            shutil.rmtree(destination, ignore_errors=True)
            raise RepositoryCloneError(
                f"Repository clone exceeded the {self.timeout_seconds}-second timeout."
            ) from exc
        except OSError as exc:
            shutil.rmtree(destination, ignore_errors=True)
            raise RepositoryCloneError(f"Unable to start Git: {exc}") from exc

        if result.returncode != 0:
            shutil.rmtree(destination, ignore_errors=True)
            detail = result.stderr.strip() or (
                "Git clone failed without an error message."
            )
            raise RepositoryCloneError(detail)

        if not destination.is_dir():
            raise RepositoryCloneError(
                "Git reported success but did not create the repository directory."
            )

        return RepositoryCheckout(
            repository_id=repository_id,
            owner=owner,
            name=name,
            url=normalized_url,
            branch=branch,
            path=destination,
        )
