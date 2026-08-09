"""Single-host runtime safety helpers for the Mac mini knowledge-base writer."""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class LockUnavailable(RuntimeError):
    """Raised when a non-blocking runtime lock is already held."""


def lock_path(root: Path, name: str) -> Path:
    safe_name = "".join(c if c.isalnum() or c in "._-" else "-" for c in name)
    return root / "tmp" / "locks" / f"{safe_name}.lock"


@contextmanager
def file_lock(
    root: Path,
    name: str,
    *,
    blocking: bool = True,
) -> Iterator[Path]:
    """Hold an advisory flock; the OS releases it on exit, crash, or reboot."""
    path = lock_path(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    flags = fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB)
    try:
        try:
            fcntl.flock(handle.fileno(), flags)
        except BlockingIOError as exc:
            raise LockUnavailable(f"Lock already held: {name}") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()}\n")
        handle.flush()
        yield path
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Flush and atomically replace a text file on the same filesystem."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_lock = path.parent / f".{path.name}.write.lock"
    with write_lock.open("a+") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        temp_path = Path(temporary)
        try:
            with os.fdopen(fd, "w", encoding=encoding) as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise


def atomic_write_json(path: Path, payload: object) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2) + "\n")
