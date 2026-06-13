"""
traversal.py
------------
Recursive directory / single-file walker for WhereTF.

Yields FileEntry dicts that carry the raw metadata needed to populate
the `File` SQLAlchemy model.  No DB sessions are opened here.
"""

from __future__ import annotations

import hashlib
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Generator

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

#: Every extension the processing pipeline can handle.
#: Keep in sync with the dispatch table in extractors.py.
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {
        # ── Documents ─────────────────────────────────────────────────────
        ".pdf", ".docx", ".pptx", ".xlsx", ".xls",
        # ── Images (standalone OCR) ───────────────────────────────────────
        ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif",
        # ── Plain text & markup ───────────────────────────────────────────
        ".txt", ".md", ".rst", ".tex",
        # ── Data formats ─────────────────────────────────────────────────
        ".json", ".csv", ".tsv", ".xml", ".yaml", ".yml", ".toml",
        # ── Python ───────────────────────────────────────────────────────
        ".py", ".pyi", ".ipynb",
        # ── JavaScript / TypeScript ───────────────────────────────────────
        ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
        # ── Web ───────────────────────────────────────────────────────────
        ".html", ".htm", ".css", ".scss", ".sass",
        # ── Systems / compiled languages ─────────────────────────────────
        ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hxx",
        ".cs", ".java", ".kt", ".swift", ".go", ".rs", ".zig",
        # ── Scripting / shell ─────────────────────────────────────────────
        ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd",
        # ── Ruby / PHP / others ───────────────────────────────────────────
        ".rb", ".php", ".lua", ".pl", ".r", ".scala",
        ".ex", ".exs", ".erl", ".hs", ".ml", ".clj",
        # ── Config / infra ────────────────────────────────────────────────
        ".ini", ".cfg", ".conf", ".env",
        ".dockerfile", ".tf", ".hcl", ".sql", ".graphql", ".proto",
    }
)

#: Extensionless filenames that should still be processed as plain text.
SUPPORTED_NAMES: frozenset[str] = frozenset(
    {
        "makefile", "dockerfile", "jenkinsfile", "vagrantfile",
        "gemfile", "rakefile", "procfile", "brewfile",
        ".gitignore", ".gitattributes", ".editorconfig",
        "requirements", "pipfile", "cargo.lock", "go.sum",
    }
)


class FileEntry(dict):
    """
    A plain dict subclass that remains fully JSON-serialisable.

    Keys match the ``File`` SQLAlchemy model fields:
        file_path     : str       – absolute, POSIX-style path
        file_hash     : str       – SHA-256 hex digest
        mime_type     : str       – best-guess MIME type
        last_modified : datetime
        tags          : list[str] – starts empty; callers may populate later
    """


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    """Stream-hash a file in 1 MiB chunks — never loads the whole file."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            buf = fh.read(chunk_size)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def _mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def _is_supported(path: Path) -> bool:
    """Return True if this path should be processed."""
    return (
        path.suffix.lower() in SUPPORTED_EXTENSIONS
        or path.name.lower() in SUPPORTED_NAMES
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def iter_files(root: str | Path) -> Generator[FileEntry, None, None]:
    """
    Yield one :class:`FileEntry` for every supported file found under
    *root*.  If *root* is a single file, yield just that file (provided
    its extension or name is supported).

    Parameters
    ----------
    root:
        A directory path or a single file path.

    Yields
    ------
    FileEntry
        Populated with ``file_path``, ``file_hash``, ``mime_type``,
        ``last_modified``, and an empty ``tags`` list.
    """
    root = Path(root).resolve()

    if root.is_file():
        paths: list[Path] | Generator = [root]
    elif root.is_dir():
        paths = (p for p in root.rglob("*") if p.is_file())
    else:
        raise FileNotFoundError(f"Path does not exist or is not accessible: {root}")

    for path in paths:
        if not _is_supported(path):
            continue
        try:
            stat = path.stat()
            yield FileEntry(
                file_path=path.as_posix(),
                file_hash=_sha256(path),
                mime_type=_mime(path),
                last_modified=datetime.fromtimestamp(stat.st_mtime),
                tags=[],
            )
        except (OSError, PermissionError) as exc:
            print(f"[traversal] Skipping {path}: {exc}")