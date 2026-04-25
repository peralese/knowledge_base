"""Tests for GET /api/pipeline-status and DELETE /api/pipeline-status/<id>."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import dashboard
from dashboard import (
    _build_aggregation_index,
    _compute_pipeline_status,
    app,
)

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _manifest(sources: list[dict]) -> dict:
    return {"manifest_version": "0.2.0", "last_updated": "2026-04-25", "sources": sources}


def _source(
    source_id: str = "SRC-20260101-0001",
    title: str = "Test Article",
    filename: str = "test-article.md",
    path: str = "raw/articles/test-article.md",
    date_ingested: str = "2026-01-01",
) -> dict:
    return {
        "source_id": source_id,
        "title": title,
        "filename": filename,
        "path": path,
        "source_type": "article",
        "origin": "web",
        "date_ingested": date_ingested,
        "canonical_url": "https://example.com/test",
    }


def _queue_entry(
    source_id: str,
    topic_slug: str = "test-topic",
    confidence_score: float | None = None,
    review_action: str | None = None,
    review_status: str = "synthesized",
) -> dict:
    entry: dict = {
        "source_id": source_id,
        "title": "Test",
        "topic_slug": topic_slug,
        "review_status": review_status,
        "validation_status": "validated",
        "validation_issues": [],
        "review_action": review_action,
    }
    if confidence_score is not None:
        entry["confidence_score"] = confidence_score
    return entry


def _write_manifest(root: Path, sources: list[dict]) -> None:
    meta = root / "metadata"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "source-manifest.json").write_text(
        json.dumps(_manifest(sources)), encoding="utf-8"
    )


def _write_queue(root: Path, entries: list[dict]) -> None:
    meta = root / "metadata"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "review-queue.json").write_text(
        json.dumps(entries), encoding="utf-8"
    )


def _write_raw(root: Path, rel_path: str, content: str = "# Content\n") -> None:
    p = root / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _write_prompt_pack(root: Path, stem: str) -> None:
    d = root / "metadata" / "prompts"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"compile-{stem}-synthesis.md").write_text("# Prompt\n", encoding="utf-8")


def _write_synthesis(root: Path, stem: str) -> None:
    d = root / "compiled" / "source_summaries"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{stem}-synthesis.md").write_text("# Synthesis\n", encoding="utf-8")


def _write_topic(root: Path, topic_slug: str, compiled_from: list[str]) -> None:
    d = root / "compiled" / "topics"
    d.mkdir(parents=True, exist_ok=True)
    items = "\n".join(f'  - "{s}"' for s in compiled_from)
    (d / f"{topic_slug}.md").write_text(
        f'---\ntitle: "{topic_slug}"\ncompiled_from: \n{items}\n---\n\n# Body\n',
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# _build_aggregation_index
# ---------------------------------------------------------------------------

class AggregationIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_empty_when_no_topics_dir(self) -> None:
        idx = _build_aggregation_index(self.root)
        self.assertEqual(idx, {})

    def test_indexes_single_synthesis(self) -> None:
        _write_topic(self.root, "ollama", ["i-built-a-local-ai-stack-synthesis"])
        idx = _build_aggregation_index(self.root)
        self.assertIn("i-built-a-local-ai-stack-synthesis", idx)
        self.assertEqual(idx["i-built-a-local-ai-stack-synthesis"], ["ollama"])

    def test_multi_topic_per_synthesis(self) -> None:
        _write_topic(self.root, "topic-a", ["shared-synthesis"])
        _write_topic(self.root, "topic-b", ["shared-synthesis"])
        idx = _build_aggregation_index(self.root)
        self.assertIn("shared-synthesis", idx)
        self.assertEqual(sorted(idx["shared-synthesis"]), ["topic-a", "topic-b"])

    def test_multi_synthesis_per_topic(self) -> None:
        _write_topic(self.root, "big-topic", ["alpha-synthesis", "beta-synthesis"])
        idx = _build_aggregation_index(self.root)
        self.assertIn("alpha-synthesis", idx)
        self.assertIn("beta-synthesis", idx)
        self.assertEqual(idx["alpha-synthesis"], ["big-topic"])
        self.assertEqual(idx["beta-synthesis"], ["big-topic"])

    def test_ignores_file_with_no_compiled_from(self) -> None:
        d = self.root / "compiled" / "topics"
        d.mkdir(parents=True)
        (d / "bare.md").write_text('---\ntitle: "bare"\n---\n\n# Body\n', encoding="utf-8")
        idx = _build_aggregation_index(self.root)
        self.assertEqual(idx, {})


# ---------------------------------------------------------------------------
# _compute_pipeline_status — stage determination
# ---------------------------------------------------------------------------

class StageRegisteredTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_stage_registered_when_raw_exists_nothing_else(self) -> None:
        src = _source()
        _write_manifest(self.root, [src])
        _write_raw(self.root, src["path"])
        result = _compute_pipeline_status(self.root)
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row["stage"], "registered")
        self.assertEqual(row["stage_number"], 1)
        self.assertFalse(row["file_missing"])

    def test_stage_error_when_raw_missing(self) -> None:
        src = _source()
        _write_manifest(self.root, [src])
        # Do NOT write the raw file
        result = _compute_pipeline_status(self.root)
        row = result[0]
        self.assertEqual(row["stage"], "error")
        self.assertEqual(row["stage_number"], 0)
        self.assertTrue(row["file_missing"])

    def test_stage_prompt_packed(self) -> None:
        src = _source()
        _write_manifest(self.root, [src])
        _write_raw(self.root, src["path"])
        _write_prompt_pack(self.root, "test-article")
        result = _compute_pipeline_status(self.root)
        self.assertEqual(result[0]["stage"], "prompt-packed")
        self.assertEqual(result[0]["stage_number"], 2)
        self.assertTrue(result[0]["has_prompt_pack"])

    def test_stage_synthesized(self) -> None:
        src = _source()
        _write_manifest(self.root, [src])
        _write_raw(self.root, src["path"])
        _write_prompt_pack(self.root, "test-article")
        _write_synthesis(self.root, "test-article")
        result = _compute_pipeline_status(self.root)
        self.assertEqual(result[0]["stage"], "synthesized")
        self.assertEqual(result[0]["stage_number"], 3)
        self.assertTrue(result[0]["has_synthesis"])

    def test_stage_scored_when_queue_has_confidence_no_action(self) -> None:
        src = _source()
        _write_manifest(self.root, [src])
        _write_raw(self.root, src["path"])
        _write_synthesis(self.root, "test-article")
        _write_queue(self.root, [_queue_entry("SRC-20260101-0001", confidence_score=0.78)])
        result = _compute_pipeline_status(self.root)
        row = result[0]
        self.assertEqual(row["stage"], "scored")
        self.assertEqual(row["stage_number"], 4)
        self.assertTrue(row["has_score"])
        self.assertAlmostEqual(row["confidence"], 0.78)

    def test_stage_approved(self) -> None:
        src = _source()
        _write_manifest(self.root, [src])
        _write_raw(self.root, src["path"])
        _write_synthesis(self.root, "test-article")
        _write_queue(self.root, [_queue_entry(
            "SRC-20260101-0001", confidence_score=0.91, review_action="approved"
        )])
        result = _compute_pipeline_status(self.root)
        row = result[0]
        self.assertEqual(row["stage"], "approved")
        self.assertEqual(row["stage_number"], 5)
        self.assertEqual(row["disposition"], "approved")

    def test_stage_rejected(self) -> None:
        src = _source()
        _write_manifest(self.root, [src])
        _write_raw(self.root, src["path"])
        _write_synthesis(self.root, "test-article")
        _write_queue(self.root, [_queue_entry(
            "SRC-20260101-0001", confidence_score=0.35, review_action="rejected"
        )])
        result = _compute_pipeline_status(self.root)
        row = result[0]
        self.assertEqual(row["stage"], "rejected")
        self.assertEqual(row["stage_number"], 5)
        self.assertEqual(row["disposition"], "rejected")

    def test_stage_aggregated(self) -> None:
        src = _source()
        _write_manifest(self.root, [src])
        _write_raw(self.root, src["path"])
        _write_synthesis(self.root, "test-article")
        _write_queue(self.root, [_queue_entry(
            "SRC-20260101-0001", confidence_score=0.88, review_action="approved"
        )])
        _write_topic(self.root, "my-topic", ["test-article-synthesis"])
        result = _compute_pipeline_status(self.root)
        row = result[0]
        self.assertEqual(row["stage"], "aggregated")
        self.assertEqual(row["stage_number"], 6)
        self.assertEqual(row["aggregated_into"], ["my-topic"])

    def test_aggregated_into_multiple_topics(self) -> None:
        src = _source()
        _write_manifest(self.root, [src])
        _write_raw(self.root, src["path"])
        _write_synthesis(self.root, "test-article")
        _write_topic(self.root, "topic-a", ["test-article-synthesis"])
        _write_topic(self.root, "topic-b", ["test-article-synthesis"])
        result = _compute_pipeline_status(self.root)
        row = result[0]
        self.assertEqual(row["stage"], "aggregated")
        self.assertEqual(sorted(row["aggregated_into"]), ["topic-a", "topic-b"])

    def test_error_stage_wins_over_all_others(self) -> None:
        """A missing raw file is always stage=error, even if synthesis and queue entry exist."""
        src = _source()
        _write_manifest(self.root, [src])
        # No raw file written
        _write_synthesis(self.root, "test-article")
        _write_queue(self.root, [_queue_entry(
            "SRC-20260101-0001", confidence_score=0.9, review_action="approved"
        )])
        result = _compute_pipeline_status(self.root)
        self.assertEqual(result[0]["stage"], "error")


class PipelineStatusSortTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_sorted_newest_first(self) -> None:
        sources = [
            _source("SRC-A", date_ingested="2026-01-01",
                    filename="a.md", path="raw/articles/a.md"),
            _source("SRC-C", date_ingested="2026-03-01",
                    filename="c.md", path="raw/articles/c.md"),
            _source("SRC-B", date_ingested="2026-02-01",
                    filename="b.md", path="raw/articles/b.md"),
        ]
        _write_manifest(self.root, sources)
        result = _compute_pipeline_status(self.root)
        self.assertEqual([r["source_id"] for r in result], ["SRC-C", "SRC-B", "SRC-A"])

    def test_empty_manifest_returns_empty_list(self) -> None:
        _write_manifest(self.root, [])
        result = _compute_pipeline_status(self.root)
        self.assertEqual(result, [])

    def test_missing_manifest_returns_empty_list(self) -> None:
        result = _compute_pipeline_status(self.root)
        self.assertEqual(result, [])


class PipelineStatusFieldsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_all_required_fields_present(self) -> None:
        src = _source()
        _write_manifest(self.root, [src])
        _write_raw(self.root, src["path"])
        result = _compute_pipeline_status(self.root)
        row = result[0]
        for field in [
            "source_id", "title", "topic", "registered_at", "stage",
            "stage_number", "confidence", "file_missing", "raw_path",
            "has_prompt_pack", "has_synthesis", "has_score",
            "disposition", "aggregated_into",
        ]:
            self.assertIn(field, row, f"Missing field: {field}")

    def test_no_queue_entry_yields_none_for_nullable_fields(self) -> None:
        src = _source()
        _write_manifest(self.root, [src])
        _write_raw(self.root, src["path"])
        result = _compute_pipeline_status(self.root)
        row = result[0]
        self.assertIsNone(row["confidence"])
        self.assertIsNone(row["topic"])
        self.assertIsNone(row["disposition"])
        self.assertEqual(row["aggregated_into"], [])


# ---------------------------------------------------------------------------
# GET /api/pipeline-status endpoint
# ---------------------------------------------------------------------------

class PipelineStatusEndpointTests(unittest.TestCase):
    def test_returns_list(self) -> None:
        from unittest.mock import patch
        with patch("dashboard._compute_pipeline_status", return_value=[]):
            res = client.get("/api/pipeline-status")
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)

    def test_returns_sources_from_real_manifest(self) -> None:
        res = client.get("/api/pipeline-status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIsInstance(data, list)
        # Real manifest has 15 sources
        self.assertGreater(len(data), 0)
        row = data[0]
        for field in ["source_id", "title", "stage", "stage_number"]:
            self.assertIn(field, row)

    def test_sorted_newest_first_from_real_manifest(self) -> None:
        res = client.get("/api/pipeline-status")
        data = res.json()
        dates = [d["registered_at"] for d in data]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_missing_file_sources_flagged(self) -> None:
        """Any source with file_missing=True must have stage='error'."""
        fake_status = [
            {"source_id": "SRC-MISSING", "title": "Gone", "topic": None,
             "registered_at": "2026-01-01", "stage": "error", "stage_number": 0,
             "confidence": None, "file_missing": True, "raw_path": "raw/articles/gone.md",
             "has_prompt_pack": False, "has_synthesis": False, "has_score": False,
             "disposition": None, "aggregated_into": []},
        ]
        from unittest.mock import patch
        with patch("dashboard._compute_pipeline_status", return_value=fake_status):
            res = client.get("/api/pipeline-status")
        data = res.json()
        errors = [d for d in data if d["file_missing"]]
        self.assertGreater(len(errors), 0)
        for e in errors:
            self.assertEqual(e["stage"], "error")
            self.assertEqual(e["stage_number"], 0)

    def test_aggregated_sources_have_topic_list(self) -> None:
        res = client.get("/api/pipeline-status")
        data = res.json()
        aggregated = [d for d in data if d["stage"] == "aggregated"]
        for row in aggregated:
            self.assertIsInstance(row["aggregated_into"], list)
            self.assertGreater(len(row["aggregated_into"]), 0)


# ---------------------------------------------------------------------------
# DELETE /api/pipeline-status/<id>
# ---------------------------------------------------------------------------

class DeletePipelineSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _setup_source(self, *, with_prompt: bool = False, with_synthesis: bool = False) -> str:
        """Set up a rejected source so the DELETE endpoint accepts it."""
        src = _source()
        _write_manifest(self.root, [src])
        _write_raw(self.root, src["path"])
        _write_queue(self.root, [_queue_entry("SRC-20260101-0001", review_action="rejected")])
        if with_prompt:
            _write_prompt_pack(self.root, "test-article")
        if with_synthesis:
            _write_synthesis(self.root, "test-article")
        return "SRC-20260101-0001"

    def _do_delete(self, source_id: str, confirm: bool = False) -> object:
        from unittest.mock import patch
        with patch("dashboard.ROOT", self.root):
            url = f"/api/pipeline-status/{source_id}"
            if confirm:
                url += "?confirm=true"
            res = client.request("DELETE", url)
        return res

    def test_dry_run_returns_will_delete_list(self) -> None:
        sid = self._setup_source(with_prompt=True)
        res = self._do_delete(sid)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("will_delete", data)
        self.assertIn("confirm_url", data)
        self.assertIn(sid, data["source_id"])
        self.assertTrue(any("source-manifest.json" in x for x in data["will_delete"]))

    def test_dry_run_lists_prompt_pack_if_exists(self) -> None:
        sid = self._setup_source(with_prompt=True)
        res = self._do_delete(sid)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(any("compile-test-article-synthesis.md" in x for x in data["will_delete"]))

    def test_dry_run_lists_synthesis_if_exists(self) -> None:
        sid = self._setup_source(with_synthesis=True)
        res = self._do_delete(sid)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(any("test-article-synthesis.md" in x for x in data["will_delete"]))

    def test_dry_run_does_not_delete_files(self) -> None:
        sid = self._setup_source(with_prompt=True, with_synthesis=True)
        res = self._do_delete(sid)
        self.assertEqual(res.status_code, 200)
        self.assertTrue((self.root / "raw" / "articles" / "test-article.md").exists())
        prompt = self.root / "metadata" / "prompts" / "compile-test-article-synthesis.md"
        self.assertTrue(prompt.exists())

    def test_confirm_removes_manifest_entry(self) -> None:
        sid = self._setup_source()
        res = self._do_delete(sid, confirm=True)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["deleted"], sid)
        manifest = json.loads(
            (self.root / "metadata" / "source-manifest.json").read_text()
        )
        ids = [s["source_id"] for s in manifest["sources"]]
        self.assertNotIn(sid, ids)

    def test_confirm_deletes_prompt_pack(self) -> None:
        sid = self._setup_source(with_prompt=True)
        self._do_delete(sid, confirm=True)
        prompt = self.root / "metadata" / "prompts" / "compile-test-article-synthesis.md"
        self.assertFalse(prompt.exists())

    def test_confirm_deletes_synthesis(self) -> None:
        sid = self._setup_source(with_synthesis=True)
        self._do_delete(sid, confirm=True)
        synthesis = self.root / "compiled" / "source_summaries" / "test-article-synthesis.md"
        self.assertFalse(synthesis.exists())

    def test_unknown_source_id_returns_404(self) -> None:
        _write_manifest(self.root, [])
        res = self._do_delete("SRC-NONEXISTENT")
        self.assertEqual(res.status_code, 404)

    def test_registered_source_returns_400(self) -> None:
        """Endpoint must reject sources that are neither error nor rejected."""
        src = _source()
        _write_manifest(self.root, [src])
        _write_raw(self.root, src["path"])
        # No queue entry → stage is "registered"
        res = self._do_delete("SRC-20260101-0001")
        self.assertEqual(res.status_code, 400)

    def test_confirm_removes_only_target_source(self) -> None:
        src_a = _source("SRC-A", filename="a.md", path="raw/articles/a.md")
        src_b = _source("SRC-B", filename="b.md", path="raw/articles/b.md")
        _write_manifest(self.root, [src_a, src_b])
        _write_raw(self.root, src_a["path"])
        _write_raw(self.root, src_b["path"])
        _write_queue(self.root, [
            _queue_entry("SRC-A", review_action="rejected"),
            _queue_entry("SRC-B", review_action="rejected"),
        ])
        from unittest.mock import patch
        with patch("dashboard.ROOT", self.root):
            res = client.request("DELETE", "/api/pipeline-status/SRC-A?confirm=true")
        self.assertEqual(res.status_code, 200)
        manifest = json.loads(
            (self.root / "metadata" / "source-manifest.json").read_text()
        )
        ids = [s["source_id"] for s in manifest["sources"]]
        self.assertNotIn("SRC-A", ids)
        self.assertIn("SRC-B", ids)


if __name__ == "__main__":
    unittest.main()
