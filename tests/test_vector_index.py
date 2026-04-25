"""Tests for scripts/vector_index.py — 2D-2."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from vector_index import (
    STALENESS_DAYS,
    _content_hash,
    _eligible_notes,
    _note_id,
    _open_db,
    _strip_frontmatter,
    cmd_stats,
    cosine_similarity,
    index_is_fresh,
    is_stub,
    vector_search,
)

DUMMY_EMBEDDING = [0.1, 0.2, 0.3, 0.4, 0.5]


# ---------------------------------------------------------------------------
# is_stub
# ---------------------------------------------------------------------------

class IsStubTests(unittest.TestCase):
    def test_empty_body_is_stub(self) -> None:
        self.assertTrue(is_stub(""))

    def test_short_body_is_stub(self) -> None:
        self.assertTrue(is_stub("Short content."))

    def test_stub_pattern_is_stub(self) -> None:
        self.assertTrue(is_stub("Description not yet written. " * 10))

    def test_substantive_body_not_stub(self) -> None:
        self.assertFalse(is_stub("A" * 200))

    def test_update_stub_is_stub(self) -> None:
        self.assertTrue(is_stub("Update this stub with content. " * 10))


# ---------------------------------------------------------------------------
# cosine_similarity
# ---------------------------------------------------------------------------

class CosineSimilarityTests(unittest.TestCase):
    def test_identical_vectors(self) -> None:
        v = [1.0, 0.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(v, v), 1.0, places=5)

    def test_orthogonal_vectors(self) -> None:
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(a, b), 0.0, places=5)

    def test_opposite_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        self.assertAlmostEqual(cosine_similarity(a, b), -1.0, places=5)

    def test_empty_vectors_return_zero(self) -> None:
        self.assertEqual(cosine_similarity([], []), 0.0)

    def test_zero_vector_returns_zero(self) -> None:
        self.assertEqual(cosine_similarity([0.0, 0.0], [1.0, 1.0]), 0.0)

    def test_mismatched_lengths_return_zero(self) -> None:
        self.assertEqual(cosine_similarity([1.0, 2.0], [1.0]), 0.0)

    def test_similar_vectors_high_score(self) -> None:
        a = [0.9, 0.1, 0.0]
        b = [0.85, 0.15, 0.0]
        self.assertGreater(cosine_similarity(a, b), 0.99)


# ---------------------------------------------------------------------------
# _content_hash
# ---------------------------------------------------------------------------

class ContentHashTests(unittest.TestCase):
    def test_same_text_same_hash(self) -> None:
        text = "Hello world"
        self.assertEqual(_content_hash(text), _content_hash(text))

    def test_different_text_different_hash(self) -> None:
        self.assertNotEqual(_content_hash("Hello"), _content_hash("World"))

    def test_hash_is_16_chars(self) -> None:
        self.assertEqual(len(_content_hash("anything")), 16)


# ---------------------------------------------------------------------------
# _eligible_notes
# ---------------------------------------------------------------------------

class EligibleNotesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write(self, rel_path: str, content: str) -> Path:
        p = self.root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def test_topic_always_eligible(self) -> None:
        self._write("compiled/topics/my-topic.md", "---\ntitle: T\n---\n\n" + "A" * 200)
        eligible = _eligible_notes(self.root)
        self.assertTrue(any(p.name == "my-topic.md" for p, _ in eligible))

    def test_stub_concept_excluded(self) -> None:
        self._write("compiled/concepts/stub-concept.md",
                    "---\ntitle: S\n---\n\nDescription not yet written. Update this stub.\n" * 5)
        eligible = _eligible_notes(self.root)
        self.assertFalse(any(p.name == "stub-concept.md" for p, _ in eligible))

    def test_substantive_concept_included(self) -> None:
        self._write("compiled/concepts/rich-concept.md",
                    "---\ntitle: R\n---\n\n" + "Detailed content about this concept. " * 10)
        eligible = _eligible_notes(self.root)
        self.assertTrue(any(p.name == "rich-concept.md" for p, _ in eligible))

    def test_unapproved_source_summary_excluded(self) -> None:
        self._write("compiled/source_summaries/draft-synthesis.md",
                    "---\ntitle: D\napproved: false\n---\n\n" + "Content. " * 50)
        eligible = _eligible_notes(self.root)
        self.assertFalse(any(p.name == "draft-synthesis.md" for p, _ in eligible))

    def test_approved_source_summary_included(self) -> None:
        self._write("compiled/source_summaries/good-synthesis.md",
                    "---\ntitle: G\napproved: true\n---\n\n" + "Content. " * 50)
        eligible = _eligible_notes(self.root)
        self.assertTrue(any(p.name == "good-synthesis.md" for p, _ in eligible))

    def test_returns_note_type(self) -> None:
        self._write("compiled/topics/t.md", "---\ntitle: T\n---\n\n" + "A" * 200)
        self._write("compiled/entities/e.md", "---\ntitle: E\n---\n\n" + "A" * 200)
        eligible = _eligible_notes(self.root)
        types = {note_type for _, note_type in eligible}
        self.assertIn("topic", types)
        self.assertIn("entity", types)


# ---------------------------------------------------------------------------
# Content hash change detection (update logic)
# ---------------------------------------------------------------------------

class ContentHashChangeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "outputs" / "vector_index.db"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_hash_mismatch_detected(self) -> None:
        text_v1 = "---\ntitle: T\n---\n\n" + "Version 1 content. " * 20
        text_v2 = "---\ntitle: T\n---\n\n" + "Version 2 content. " * 20
        h1 = _content_hash(text_v1)
        h2 = _content_hash(text_v2)
        self.assertNotEqual(h1, h2)

    def test_same_content_same_hash_no_reembed_needed(self) -> None:
        text = "---\ntitle: T\n---\n\n" + "Stable content. " * 20
        h1 = _content_hash(text)
        h2 = _content_hash(text)
        self.assertEqual(h1, h2)


# ---------------------------------------------------------------------------
# vector_search
# ---------------------------------------------------------------------------

class VectorSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "outputs" / "vector_index.db"
        self.db_path.parent.mkdir(parents=True)

        conn = _open_db(self.db_path)
        # Insert three notes with known embeddings
        from datetime import datetime  # noqa: PLC0415
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO note_embeddings VALUES (?, ?, ?, ?, ?, ?)",
            ("compiled/topics/note-a.md", "topic", "note-a.md", "hash1", now,
             json.dumps([1.0, 0.0, 0.0])),
        )
        conn.execute(
            "INSERT INTO note_embeddings VALUES (?, ?, ?, ?, ?, ?)",
            ("compiled/topics/note-b.md", "topic", "note-b.md", "hash2", now,
             json.dumps([0.0, 1.0, 0.0])),
        )
        conn.execute(
            "INSERT INTO note_embeddings VALUES (?, ?, ?, ?, ?, ?)",
            ("compiled/topics/note-c.md", "topic", "note-c.md", "hash3", now,
             json.dumps([0.9, 0.1, 0.0])),
        )
        from vector_index import _set_meta  # noqa: PLC0415
        _set_meta(conn, "last_built", now)
        _set_meta(conn, "model", "nomic-embed-text")
        conn.commit()
        conn.close()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_search_returns_sorted_by_similarity(self) -> None:
        # Query near [1, 0, 0] → should rank note-a first, then note-c
        query_embedding = [1.0, 0.0, 0.0]
        results = vector_search(query_embedding, self.db_path, top_n=3)
        self.assertTrue(len(results) >= 1)
        # note-a (exact match) and note-c (close) should both rank above note-b
        ids = [r[0] for r in results]
        self.assertIn("compiled/topics/note-a.md", ids)
        # note-a should be first
        self.assertEqual(ids[0], "compiled/topics/note-a.md")

    def test_search_returns_tuple_fields(self) -> None:
        results = vector_search([1.0, 0.0, 0.0], self.db_path, top_n=5)
        for note_id, note_type, score in results:
            self.assertIsInstance(note_id, str)
            self.assertIsInstance(note_type, str)
            self.assertIsInstance(score, float)
            self.assertGreater(score, 0)

    def test_search_top_n_limit(self) -> None:
        results = vector_search([1.0, 0.0, 0.0], self.db_path, top_n=2)
        self.assertLessEqual(len(results), 2)

    def test_search_missing_db_returns_empty(self) -> None:
        ghost = self.root / "ghost.db"
        results = vector_search([1.0, 0.0, 0.0], ghost, top_n=5)
        self.assertEqual(results, [])


# ---------------------------------------------------------------------------
# index_is_fresh
# ---------------------------------------------------------------------------

class IndexIsFreshTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / "vector_index.db"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_missing_db_not_fresh(self) -> None:
        self.assertFalse(index_is_fresh(self.db_path))

    def test_fresh_db_is_fresh(self) -> None:
        from datetime import timezone  # noqa: PLC0415
        from datetime import datetime  # noqa: PLC0415
        from vector_index import _set_meta  # noqa: PLC0415
        conn = _open_db(self.db_path)
        now = datetime.now(timezone.utc).isoformat()
        # Insert a dummy embedding so count > 0
        conn.execute(
            "INSERT INTO note_embeddings VALUES (?, ?, ?, ?, ?, ?)",
            ("id1", "topic", "p1", "h1", now, json.dumps([1.0])),
        )
        _set_meta(conn, "last_built", now)
        conn.commit()
        conn.close()
        self.assertTrue(index_is_fresh(self.db_path, max_age_days=7))

    def test_old_db_not_fresh(self) -> None:
        from datetime import timezone, timedelta  # noqa: PLC0415
        from datetime import datetime  # noqa: PLC0415
        from vector_index import _set_meta  # noqa: PLC0415
        conn = _open_db(self.db_path)
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        conn.execute(
            "INSERT INTO note_embeddings VALUES (?, ?, ?, ?, ?, ?)",
            ("id1", "topic", "p1", "h1", old, json.dumps([1.0])),
        )
        _set_meta(conn, "last_built", old)
        conn.commit()
        conn.close()
        self.assertFalse(index_is_fresh(self.db_path, max_age_days=7))

    def test_empty_db_not_fresh(self) -> None:
        conn = _open_db(self.db_path)
        from vector_index import _set_meta  # noqa: PLC0415
        from datetime import datetime, timezone  # noqa: PLC0415
        _set_meta(conn, "last_built", datetime.now(timezone.utc).isoformat())
        conn.commit()
        conn.close()
        self.assertFalse(index_is_fresh(self.db_path))


# ---------------------------------------------------------------------------
# cmd_build / cmd_update (mocked Ollama)
# ---------------------------------------------------------------------------

class CmdBuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        topics = self.root / "compiled" / "topics"
        topics.mkdir(parents=True)
        (topics / "topic-a.md").write_text(
            "---\ntitle: A\n---\n\n" + "Content about security. " * 20,
            encoding="utf-8",
        )
        # Stub concept — should be excluded
        concepts = self.root / "compiled" / "concepts"
        concepts.mkdir()
        (concepts / "stub.md").write_text(
            "---\ntitle: S\n---\n\nDescription not yet written. Update this stub.\n" * 5,
            encoding="utf-8",
        )
        self.db_path = self.root / "vector_index.db"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_build_indexes_topics_not_stubs(self) -> None:
        from vector_index import cmd_build  # noqa: PLC0415
        with patch("vector_index._check_embed_model_available"):
            with patch("vector_index.call_ollama_embeddings", return_value=DUMMY_EMBEDDING):
                result = cmd_build(self.root, "nomic-embed-text", self.db_path)
        self.assertEqual(result, 0)
        conn = sqlite3.connect(str(self.db_path))
        rows = conn.execute("SELECT id, note_type FROM note_embeddings").fetchall()
        conn.close()
        # Should have topic-a, not stub
        ids = [r[0] for r in rows]
        self.assertTrue(any("topic-a" in nid for nid in ids))
        self.assertFalse(any("stub" in nid for nid in ids))

    def test_update_only_reembeds_changed_notes(self) -> None:
        from vector_index import cmd_build, cmd_update  # noqa: PLC0415
        call_count = [0]

        def mock_embed(text, model=None):
            call_count[0] += 1
            return DUMMY_EMBEDDING

        with patch("vector_index._check_embed_model_available"):
            with patch("vector_index.call_ollama_embeddings", side_effect=mock_embed):
                cmd_build(self.root, "nomic-embed-text", self.db_path)
                initial_calls = call_count[0]

                # Update without changes — should make zero new embed calls
                call_count[0] = 0
                cmd_update(self.root, "nomic-embed-text", self.db_path)
                self.assertEqual(call_count[0], 0)

        # Now modify the topic file
        topic_path = self.root / "compiled" / "topics" / "topic-a.md"
        topic_path.write_text(
            "---\ntitle: A\n---\n\n" + "Updated content about security. " * 20,
            encoding="utf-8",
        )
        with patch("vector_index._check_embed_model_available"):
            with patch("vector_index.call_ollama_embeddings", side_effect=mock_embed):
                cmd_update(self.root, "nomic-embed-text", self.db_path)
                self.assertEqual(call_count[0], 1)


if __name__ == "__main__":
    unittest.main()
