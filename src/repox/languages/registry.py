"""Registry for selecting language adapters by source-file extension."""

from collections.abc import Iterable
from pathlib import Path

from repox.languages.base import LanguageAdapter


class LanguageRegistry:
    """Deterministic extension-to-adapter registry."""

    def __init__(self, adapters: Iterable[LanguageAdapter] = ()) -> None:
        self._by_extension: dict[str, LanguageAdapter] = {}
        self._by_language: dict[str, LanguageAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: LanguageAdapter) -> None:
        """Register an adapter, rejecting ambiguous language/extension ownership."""
        language = adapter.language.strip().lower()
        if not language:
            raise ValueError("Adapter language must not be empty")
        if language in self._by_language:
            raise ValueError(f"Language adapter already registered: {language}")
        extensions = {extension.lower() for extension in adapter.extensions}
        if not extensions or any(not item.startswith(".") for item in extensions):
            raise ValueError("Adapters must declare extensions such as '.py'")
        conflicts = sorted(item for item in extensions if item in self._by_extension)
        if conflicts:
            details = ", ".join(conflicts)
            raise ValueError(f"File extensions already registered: {details}")
        self._by_language[language] = adapter
        for extension in extensions:
            self._by_extension[extension] = adapter

    def for_path(self, path: str | Path) -> LanguageAdapter | None:
        """Return the adapter registered for a file suffix, if any."""
        return self._by_extension.get(Path(path).suffix.lower())

    def get(self, language: str) -> LanguageAdapter:
        """Return an adapter by normalized language name."""
        try:
            return self._by_language[language.strip().lower()]
        except KeyError as exc:
            raise KeyError(f"No language adapter registered for: {language}") from exc

    @property
    def extensions(self) -> frozenset[str]:
        """All supported extensions."""
        return frozenset(self._by_extension)

    @property
    def languages(self) -> tuple[str, ...]:
        """Registered language names in deterministic order."""
        return tuple(sorted(self._by_language))


def default_language_registry() -> LanguageRegistry:
    """Create RepoX's default registry (Python is the first reference adapter)."""
    from repox.languages.python import PythonLanguageAdapter

    return LanguageRegistry([PythonLanguageAdapter()])
