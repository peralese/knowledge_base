"""Tests for purge_source.py, review.py purge command, and dashboard DELETE endpoint."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from purge_source import purge_source
import review
from dashboard import app

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _write_manifest(root: Path, sources: list[dict]) -> None:
    meta = root / "metadata"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "source-manifest.json").write_text(
        json.dumps({"manifest_version": "0.2.0", "sources": sources}),
        encoding="utf-8",
    )


def _write_queue(root: Path, entries: list[dict]) -> None:
    meta = root / "metadata"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "review-queue.json").write_text(json.dumps(entries), encoding="utf-8")


def _source(
    source_id: str = "SRC-20260101-0001",
    filename: str = "test-article.md",
    path: str = "raw/articles/test-article.md",
    title: str = "Test Article",
) -> dict:
    return {
        "source_id": source_id,
        "title": title,
        "filename": filename,
        "path": path,
        "source_type": "article",
        "origin": "web",
        "date_ingested": "2026-01-01",
    }


def _queue_entry(
    source_id: str = "SRC-20260101-0001",
    review_action: str | None = "rejected",
    confidence_score: float | None = 0.35,
) -> dict:
    return {
        "source_id": source_id,
        "title": "Test Article",
        "topic_slug": "test-topic",
        "review_status": "synthesized",
        "review_action": review_action,
        "confidence_score": confidence_score,
    }


def _make_raw(root: Path, path: str) -> Path:
    p = root / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# Content\n", encoding="utf-8")
    return p


def _make_prompt_pack(root: Path, stem: str) -> Path:
    d = root / "metadata" / "prompts"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"compile-{stem}-synthesis.md"
    p.write_text("# Prompt\n", encoding="utf-8")
    return p


def _make_synthesis(root: Path, stem: str) -> Path:
    d = root / "compiled" / "source_summaries"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{stem}-synthesis.md"
    p.write_text("# Synthesis\n", encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# purge_source unit tests
# ---------------------------------------------------------------------------

class PurgeSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _full_setup(self) -> str:
        src = _source()
        _write_manifest(self.root, [src])
        _write_queue(self.root, [_queue_entry()])
        _make_raw(self.root, src["path"])
        _make_prompt_pack(self.root, "test-article")
        _make_synthesis(self.root, "test-article")
        return "SRC-20260101-0001"

    def test_removes_all_artifacts(self) -> None:
        sid = self._full_setup()
        result = purge_source(sid, self.root)
        # Raw file deleted
        self.assertFalse((self.root / "raw" / "articles" / "test-article.md").exists())
        # Prompt pack deleted
        self.assertFalse(
            (self.root / "metadata" / "prompts" / "compile-test-article-synthesis.md").exists()
        )
        # Synthesis deleted
        self.assertFalse(
            (self.root / "compiled" / "source_summaries" / "test-article-synthesis.md").exists()
        )
        # Manifest entry removed
        manifest = json.loads(
            (self.root / "metadata" / "source-manifest.json").read_text()
        )
        self.assertEqual(manifest["sources"], [])
        # Queue entry removed
        queue = json.loads(
            (self.root / "metadata" / "review-queue.json").read_text()
        )
        self.assertEqual(queue, [])

    def test_removed_list_contains_all_items(self) -> None:
        sid = self._full_setup()
        result = purge_source(sid, self.root)
        self.assertIn("metadata/source-manifest.json entry", result["removed"])
        self.assertTrue(any("compile-test-article-synthesis.md" in r for r in result["removed"]))
        self.assertTrue(any("test-article-synthesis.md" in r for r in result["removed"]))
        self.assertIn("metadata/review-queue.json entry", result["removed"])
        self.assertIn("raw/articles/test-article.md", result["removed"])

    def test_skips_absent_prompt_pack_without_error(self) -> None:
        src = _source()
        _write_manifest(self.root, [src])
        _make_raw(self.root, src["path"])
        # No prompt pack written
        result = purge_source("SRC-20260101-0001", self.root)
        self.assertTrue(any("compile-test-article-synthesis.md" in s for s in result["skipped"]))
        self.assertEqual(result["removed"], [
            "metadata/source-manifest.json entry",
            "raw/articles/test-article.md",
        ])

    def test_skips_absent_synthesis_without_error(self) -> None:
        src = _source()
        _write_manifest(self.root, [src])
        _make_raw(self.root, src["path"])
        # No synthesis
        result = purge_source("SRC-20260101-0001", self.root)
        self.assertTrue(any("test-article-synthesis.md" in s for s in result["skipped"]))

    def test_skips_missing_raw_file_without_error(self) -> None:
        src = _source()
        _write_manifest(self.root, [src])
        # No raw file written
        result = purge_source("SRC-20260101-0001", self.root)
        self.assertTrue(any("not found" in s for s in result["skipped"]))
        # Manifest still removed
        self.assertIn("metadata/source-manifest.json entry", result["removed"])

    def test_skips_absent_queue_entry_without_error(self) -> None:
        src = _source()
        _write_manifest(self.root, [src])
        # No queue file
        result = purge_source("SRC-20260101-0001", self.root)
        self.assertTrue(any("review-queue.json" in s for s in result["skipped"]))

    def test_raises_value_error_for_unknown_source(self) -> None:
        _write_manifest(self.root, [])
        with self.assertRaises(ValueError):
            purge_source("SRC-NONEXISTENT", self.root)

    def test_dry_run_makes_no_filesystem_changes(self) -> None:
        sid = self._full_setup()
        result = purge_source(sid, self.root, dry_run=True)
        self.assertTrue(result["dry_run"])
        # All files still exist
        self.assertTrue((self.root / "raw" / "articles" / "test-article.md").exists())
        self.assertTrue(
            (self.root / "metadata" / "prompts" / "compile-test-article-synthesis.md").exists()
        )
        self.assertTrue(
            (self.root / "compiled" / "source_summaries" / "test-article-synthesis.md").exists()
        )
        manifest = json.loads(
            (self.root / "metadata" / "source-manifest.json").read_text()
        )
        self.assertEqual(len(manifest["sources"]), 1)

    def test_dry_run_still_reports_would_remove(self) -> None:
        sid = self._full_setup()
        result = purge_source(sid, self.root, dry_run=True)
        self.assertIn("metadata/source-manifest.json entry", result["removed"])
        self.assertIn("raw/articles/test-article.md", result["removed"])
        self.assertEqual(result["affected_paths"], [])

    def test_preserves_other_sources_in_manifest(self) -> None:
        src_a = _source("SRC-A", filename="a.md", path="raw/articles/a.md", title="A")
        src_b = _source("SRC-B", filename="b.md", path="raw/articles/b.md", title="B")
        _write_manifest(self.root, [src_a, src_b])
        _make_raw(self.root, src_a["path"])
        _make_raw(self.root, src_b["path"])
        purge_source("SRC-A", self.root)
        manifest = json.loads(
            (self.root / "metadata" / "source-manifest.json").read_text()
        )
        ids = [s["source_id"] for s in manifest["sources"]]
        self.assertNotIn("SRC-A", ids)
        self.assertIn("SRC-B", ids)

    def test_affected_paths_non_empty_after_real_purge(self) -> None:
        sid = self._full_setup()
        result = purge_source(sid, self.root)
        self.assertGreater(len(result["affected_paths"]), 0)


# ---------------------------------------------------------------------------
# review.py purge command tests
# ---------------------------------------------------------------------------

class ReviewPurgeCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _setup(
        self,
        *,
        review_action: str | None = "rejected",
        with_raw: bool = True,
    ) -> None:
        src = _source()
        _write_manifest(self.root, [src])
        _write_queue(self.root, [_queue_entry(review_action=review_action)])
        if with_raw:
            _make_raw(self.root, src["path"])

    def test_purge_refused_for_approved_source(self) -> None:
        self._setup(review_action="approved")
        rc = review.cmd_purge(
            "SRC-20260101-0001",
            all_rejected=False, dry_run=False, force=False,
            root=self.root, no_commit=True,
        )
        self.assertEqual(rc, 1)
        # Raw file must still exist
        self.assertTrue((self.root / "raw" / "articles" / "test-article.md").exists())

    def test_purge_refused_for_pending_source(self) -> None:
        self._setup(review_action=None)
        rc = review.cmd_purge(
            "SRC-20260101-0001",
            all_rejected=False, dry_run=False, force=False,
            root=self.root, no_commit=True,
        )
        self.assertEqual(rc, 1)
        self.assertTrue((self.root / "raw" / "articles" / "test-article.md").exists())

    def test_purge_proceeds_for_rejected_source(self) -> None:
        self._setup(review_action="rejected")
        rc = review.cmd_purge(
            "SRC-20260101-0001",
            all_rejected=False, dry_run=False, force=False,
            root=self.root, no_commit=True,
        )
        self.assertEqual(rc, 0)
        self.assertFalse((self.root / "raw" / "articles" / "test-article.md").exists())

    def test_force_overrides_state_check(self) -> None:
        self._setup(review_action="approved")
        rc = review.cmd_purge(
            "SRC-20260101-0001",
            all_rejected=False, dry_run=False, force=True,
            root=self.root, no_commit=True,
        )
        self.assertEqual(rc, 0)
        self.assertFalse((self.root / "raw" / "articles" / "test-article.md").exists())

    def test_dry_run_makes_no_changes(self) -> None:
        self._setup(review_action="rejected")
        rc = review.cmd_purge(
            "SRC-20260101-0001",
            all_rejected=False, dry_run=True, force=False,
            root=self.root, no_commit=True,
        )
        self.assertEqual(rc, 0)
        self.assertTrue((self.root / "raw" / "articles" / "test-article.md").exists())
        manifest = json.loads(
            (self.root / "metadata" / "source-manifest.json").read_text()
        )
        self.assertEqual(len(manifest["sources"]), 1)

    def test_all_rejected_purges_all_rejected_items(self) -> None:
        src_a = _source("SRC-A", filename="a.md", path="raw/articles/a.md", title="A")
        src_b = _source("SRC-B", filename="b.md", path="raw/articles/b.md", title="B")
        src_c = _source("SRC-C", filename="c.md", path="raw/articles/c.md", title="C")
        _write_manifest(self.root, [src_a, src_b, src_c])
        _write_queue(self.root, [
            _queue_entry("SRC-A", review_action="rejected"),
            _queue_entry("SRC-B", review_action="approved"),
            _queue_entry("SRC-C", review_action="rejected"),
        ])
        for src in [src_a, src_b, src_c]:
            _make_raw(self.root, src["path"])

        rc = review.cmd_purge(
            None,
            all_rejected=True, dry_run=False, force=False,
            root=self.root, no_commit=True,
        )
        self.assertEqual(rc, 0)
        self.assertFalse((self.root / "raw" / "articles" / "a.md").exists())
        self.assertTrue((self.root / "raw" / "articles" / "b.md").exists())
        self.assertFalse((self.root / "raw" / "articles" / "c.md").exists())

    def test_all_rejected_dry_run_no_changes(self) -> None:
        src = _source()
        _write_manifest(self.root, [src])
        _write_queue(self.root, [_queue_entry(review_action="rejected")])
        _make_raw(self.root, src["path"])
        rc = review.cmd_purge(
            None,
            all_rejected=True, dry_run=True, force=False,
            root=self.root, no_commit=True,
        )
        self.assertEqual(rc, 0)
        self.assertTrue((self.root / "raw" / "articles" / "test-article.md").exists())

    def test_all_rejected_returns_zero_when_none_found(self) -> None:
        src = _source()
        _write_manifest(self.root, [src])
        _write_queue(self.root, [_queue_entry(review_action="approved")])
        rc = review.cmd_purge(
            None,
            all_rejected=True, dry_run=False, force=False,
            root=self.root, no_commit=True,
        )
        self.assertEqual(rc, 0)

    def test_purge_unknown_source_returns_error(self) -> None:
        _write_manifest(self.root, [])
        _write_queue(self.root, [_queue_entry(review_action="rejected")])
        rc = review.cmd_purge(
            "SRC-20260101-0001",
            all_rejected=False, dry_run=False, force=False,
            root=self.root, no_commit=True,
        )
        self.assertEqual(rc, 1)


# ---------------------------------------------------------------------------
# Dashboard DELETE endpoint tests
# ---------------------------------------------------------------------------

class DashboardDeleteEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _setup(self, stage: str = "rejected") -> None:
        src = _source()
        _write_manifest(self.root, [src])
        if stage == "rejected":
            _write_queue(self.root, [_queue_entry(review_action="rejected")])
            _make_synthesis(self.root, "test-article")
        elif stage == "error":
            # Missing file — no raw file written
            _write_queue(self.root, [_queue_entry(review_action=None)])
        elif stage == "approved":
            _write_queue(self.root, [_queue_entry(review_action="approved")])
            _make_raw(self.root, src["path"])
            _make_synthesis(self.root, "test-article")
        elif stage == "registered":
            _make_raw(self.root, src["path"])

    def _delete(self, source_id: str, confirm: bool = False) -> object:
        with patch("dashboard.ROOT", self.root):
            url = f"/api/pipeline-status/{source_id}"
            if confirm:
                url += "?confirm=true"
            return client.request("DELETE", url)

    def test_dry_run_rejected_returns_will_delete(self) -> None:
        self._setup("rejected")
        res = self._delete("SRC-20260101-0001")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("will_delete", data)
        self.assertIn("confirm_url", data)

    def test_confirm_rejected_removes_artifacts(self) -> None:
        self._setup("rejected")
        res = self._delete("SRC-20260101-0001", confirm=True)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["deleted"], "SRC-20260101-0001")
        # Synthesis file removed
        self.assertFalse(
            (self.root / "compiled" / "source_summaries" / "test-article-synthesis.md").exists()
        )

    def test_error_stage_allowed(self) -> None:
        self._setup("error")
        res = self._delete("SRC-20260101-0001")
        self.assertEqual(res.status_code, 200)

    def test_approved_source_returns_400(self) -> None:
        self._setup("approved")
        res = self._delete("SRC-20260101-0001")
        self.assertEqual(res.status_code, 400)
        self.assertIn("approved", res.json()["detail"])

    def test_registered_source_returns_400(self) -> None:
        self._setup("registered")
        res = self._delete("SRC-20260101-0001")
        self.assertEqual(res.status_code, 400)

    def test_unknown_source_returns_404(self) -> None:
        _write_manifest(self.root, [])
        with patch("dashboard.ROOT", self.root):
            res = client.request("DELETE", "/api/pipeline-status/SRC-UNKNOWN")
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()
