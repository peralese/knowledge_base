from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.runtime_safety import LockUnavailable, atomic_write_json, atomic_write_text, file_lock


class RuntimeLockTests(unittest.TestCase):
    def test_nonblocking_duplicate_owner_defers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with file_lock(root, "item-1"):
                with self.assertRaises(LockUnavailable):
                    with file_lock(root, "item-1", blocking=False):
                        pass

    def test_lock_can_be_reacquired_after_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with file_lock(root, "worker"):
                pass
            with file_lock(root, "worker", blocking=False):
                pass


class AtomicWriteTests(unittest.TestCase):
    def test_atomic_text_replaces_existing_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.txt"
            path.write_text("old", encoding="utf-8")
            atomic_write_text(path, "new")
            self.assertEqual(path.read_text(encoding="utf-8"), "new")
            self.assertEqual(list(path.parent.glob(f".{path.name}.*.tmp")), [])

    def test_atomic_json_is_complete_and_parseable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            atomic_write_json(path, {"seen": ["a", "b"]})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"seen": ["a", "b"]})

