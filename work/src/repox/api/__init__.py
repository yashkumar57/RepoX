"""HTTP API for RepoX. Install the optional ``api`` dependencies to use it."""

from repox.api.app import create_app

__all__ = ["create_app"]
