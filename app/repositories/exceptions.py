"""Domain-specific repository failures safe for translation at application boundaries."""


class RepositoryError(RuntimeError):
    """Base class for persistence-layer failures."""


class DatasetLoadError(RepositoryError):
    """Raised when a deterministic source dataset cannot be loaded safely."""


class RepositoryConnectionError(RepositoryError):
    """Raised when the configured persistence backend cannot be reached or authenticated."""


class RepositoryQueryError(RepositoryError):
    """Raised when a persistence operation fails after connectivity is established."""
