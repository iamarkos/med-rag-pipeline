"""Where the original documents live.

The pipeline works on a redacted copy; the doctor needs the real document. A
store keeps that original and hands it back by its source_ref, so a search hit
can lead to the real file.

In a hospital the original would stay in the hospital's own system, and a store
would be a small adapter to it. Here, LocalFolderStore keeps files in a folder
and stands in for that system. A vault or cloud storage could replace it later
without changing the rest of the code: only the three methods below matter.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.config import get_originals_dir

# The file types we accept, and the extension each is saved with. The extension
# is how the type is remembered, so no extra bookkeeping is needed.
_EXTENSIONS = {
    "text/plain": ".txt",
    "text/csv": ".csv",
    "application/pdf": ".pdf",
}

# A source_ref becomes part of a file name, so only harmless characters are
# allowed. This stops a value such as "../../etc/passwd" from escaping the folder.
_SAFE_REF = re.compile(r"[A-Za-z0-9_-]+")


@dataclass(frozen=True)
class StoredOriginal:
    content: bytes
    content_type: str


class OriginalStore(Protocol):
    """What the rest of the code relies on. Any storage that offers these works."""

    def save(self, source_ref: str, content: bytes, content_type: str) -> None: ...

    def load(self, source_ref: str) -> StoredOriginal | None: ...

    def delete(self, source_ref: str) -> None: ...


class LocalFolderStore:
    """Keeps originals as files in one folder, named by their source_ref."""

    def __init__(self, folder: Path) -> None:
        self._folder = folder
        folder.mkdir(parents=True, exist_ok=True)

    def _path(self, source_ref: str, extension: str) -> Path:
        if not _SAFE_REF.fullmatch(source_ref):
            raise ValueError("Invalid source reference.")
        return self._folder / f"{source_ref}{extension}"

    def save(self, source_ref: str, content: bytes, content_type: str) -> None:
        extension = _EXTENSIONS.get(content_type)
        if extension is None:
            raise ValueError("Unsupported content type.")
        final_path = self._path(source_ref, extension)
        # Write to a temporary name and rename, so a reader never sees a file
        # that is only half written.
        temporary_path = final_path.with_name(final_path.name + ".tmp")
        temporary_path.write_bytes(content)
        temporary_path.replace(final_path)

    def load(self, source_ref: str) -> StoredOriginal | None:
        for content_type, extension in _EXTENSIONS.items():
            path = self._path(source_ref, extension)
            if path.is_file():
                return StoredOriginal(path.read_bytes(), content_type)
        return None

    def delete(self, source_ref: str) -> None:
        for extension in _EXTENSIONS.values():
            self._path(source_ref, extension).unlink(missing_ok=True)


@lru_cache(maxsize=1)
def get_original_store() -> OriginalStore:
    """The store the API uses, created once."""
    return LocalFolderStore(Path(get_originals_dir()))
