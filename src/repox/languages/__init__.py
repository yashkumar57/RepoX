"""Language adapter contracts and registry for RepoX."""

from repox.languages.base import LanguageAdapter
from repox.languages.python import PythonLanguageAdapter
from repox.languages.registry import LanguageRegistry, default_language_registry

__all__ = [
    "LanguageAdapter",
    "LanguageRegistry",
    "PythonLanguageAdapter",
    "default_language_registry",
]
