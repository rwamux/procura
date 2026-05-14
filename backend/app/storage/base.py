from abc import ABC, abstractmethod
from pathlib import Path


class FileStorage(ABC):
    @abstractmethod
    async def save(self, content: bytes, filename: str, prefix: str = "") -> str:
        """Save file and return the storage path."""

    @abstractmethod
    async def read(self, path: str) -> bytes:
        """Read file by storage path."""

    @abstractmethod
    async def delete(self, path: str) -> None:
        """Delete file by storage path."""

    @abstractmethod
    def public_url(self, path: str) -> str:
        """Return a URL or path suitable for serving the file."""
