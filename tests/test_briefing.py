from __future__ import annotations

import json
import tempfile
import unittest
import wave
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.briefing import (
    CandidateStore,
    FeedConfig,
    apply_retention_decision,
    audio_status,
    build_edition,
    build_narrative_prompt,
    detect_narrative_violations,
    evaluate_candidates,
    generate_narrative,
    generate_audio,
    group_related_items,
    load_feed_config,
    normalize_title,
    normalize_url,
    parse_evaluation,
    poll_configured_feeds,
    prepare_speech_script,
    validate_narrative,
    write_speech_script,
)
from scripts.feed_poller import FeedEntry, parse_feed


RSS = b"""<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel><title>Lab Feed</title><item>
<title>Agent Runtime Advances</title><link>https://example.com/agents?utm_source=rss</link>
<guid isPermaLink="false">story-123</guid><pubDate>Sat, 08 Aug 2026 12:30:00 GMT</pubDate>
<author>author@example.com</author><category>agents</category><category>AI</category>
<description>&lt;p&gt;A practical agent runtime update.&lt;/p&gt;</description>
<content:encoded>&lt;p&gt;Full technical content.&lt;/p&gt;</content:encoded>
</item></channel></rss>"""

ATOM = b"""<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom Lab</title><entry>
<id>tag:example.com,2026:abc</id><title>Local AI Platform</title>
<link rel="alternate" href="https://example.com/local-ai"/>
<published>2026-08-08T09:00:00-05:00</published><updated>2026-08-08T15:00:00Z</updated>
<author><name>Jane Engineer</name></author><category term="local-ai"/>
<summary type="html">&lt;p&gt;Local inference improvements.&lt;/p&gt;</summary>
</entry></feed>"""


def feed(feed_id: str = "lab", *, name: str = "Lab", priority: int = 0) -> FeedConfig:
    return FeedConfig(feed_id, name, f"https://feeds.example.com/{feed_id}.xml", priority=priority, tags=["ai"])


def entry(title: str = "Agent Runtime Advances", url: str = "https://example.com/story", guid: str = "") -> FeedEntry:
    return FeedEntry(
        title=title, url=url, content="Technical source content", summary="A useful summary",
        guid=guid, published_at="2026-08-08T12:00:00+00:00", categories=["agents"],
    )


VALID_EVALUATION = json.dumps({
    "relevance": 90,
    "technical_significance": 80,
    "novelty": 70,
    "usefulness": 85,
    "interest_connection": 95,
    "marketing_noise": 10,
    "why_it_matters": "It directly improves practical agent application reliability.",
})


class TempCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "metadata" / "briefing" / "candidates.db"

    def tearDown(self) -> None:
        self.tmp.cleanup()


class FeedConfigurationTests(TempCase):
    def write(self, payload: object) -> Path:
        path = self.root / "feeds.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_valid_configuration(self) -> None:
        result = load_feed_config(self.write({"feeds": [{
            "id": "openai", "name": "OpenAI", "url": "https://example.com/feed.xml",
            "enabled": True, "domain": "ai", "priority": 5, "tags": ["agents"],
        }]}))
        self.assertEqual(result.errors, [])
        self.assertEqual(result.feeds[0].id, "openai")
        self.assertEqual(result.feeds[0].priority, 5)

    def test_missing_configuration(self) -> None:
        result = load_feed_config(self.root / "missing.json")
        self.assertEqual(result.feeds, [])
        self.assertEqual(result.errors, [])

    def test_empty_configuration(self) -> None:
        self.assertEqual(load_feed_config(self.write({"feeds": []})).feeds, [])

    def test_disabled_feed_is_valid_but_not_polled(self) -> None:
        config = self.write({"feeds": [{"id": "off", "name": "Off", "url": "https://x.test/rss", "enabled": False}]})
        summary = poll_configured_feeds(config, self.db, root=self.root, fetcher=lambda _: RSS)
        self.assertEqual(summary.feeds_checked, 0)
        self.assertFalse(self.db.exists())

    def test_duplicate_feed_id_rejected_without_losing_valid_feed(self) -> None:
        result = load_feed_config(self.write({"feeds": [
            {"id": "same", "name": "One", "url": "https://one.test/rss"},
            {"id": "same", "name": "Two", "url": "https://two.test/rss"},
        ]}))
        self.assertEqual(len(result.feeds), 1)
        self.assertIn("duplicate feed id", result.errors[0])

    def test_malformed_entries_reported_independently(self) -> None:
        result = load_feed_config(self.write({"feeds": [
            {"id": "bad", "name": "Bad", "url": "not-a-url"},
            {"id": "good", "name": "Good", "url": "https://good.test/rss"},
            {"name": "Missing fields"},
        ]}))
        self.assertEqual([item.id for item in result.feeds], ["good"])
        self.assertEqual(len(result.errors), 2)


class ProvenanceParsingTests(unittest.TestCase):
    def test_rss_metadata(self) -> None:
        item = parse_feed(RSS, "Lab Feed")[0]
        self.assertEqual(item.guid, "story-123")
        self.assertEqual(item.published_at, "2026-08-08T12:30:00+00:00")
        self.assertEqual(item.author, "author@example.com")
        self.assertEqual(item.categories, ["agents", "AI"])
        self.assertIn("practical agent", item.summary)
        self.assertIn("Full technical", item.content)

    def test_atom_metadata(self) -> None:
        item = parse_feed(ATOM, "Atom Lab")[0]
        self.assertEqual(item.guid, "tag:example.com,2026:abc")
        self.assertEqual(item.published_at, "2026-08-08T14:00:00+00:00")
        self.assertEqual(item.updated_at, "2026-08-08T15:00:00+00:00")
        self.assertEqual(item.author, "Jane Engineer")
        self.assertEqual(item.categories, ["local-ai"])

    def test_missing_optional_metadata_remains_empty(self) -> None:
        item = parse_feed(b"<rss><channel><item><title>T</title><link>https://x.test/a</link></item></channel></rss>")[0]
        self.assertEqual(item.guid, "")
        self.assertEqual(item.published_at, "")
        self.assertEqual(item.categories, [])


class IdentityAndStoreTests(TempCase):
    def test_normalization(self) -> None:
        self.assertEqual(normalize_url("HTTPS://Example.COM/a/?utm_source=x&x=1#part"), "https://example.com/a?x=1")
        self.assertEqual(normalize_title("AI:  Agent Runtime!"), "ai agent runtime")

    def test_insert_and_restart_persistence(self) -> None:
        store = CandidateStore(self.db)
        candidate_id, state = store.add_entry(feed(), entry(guid="guid-1"))
        self.assertEqual(state, "new")
        reopened = CandidateStore(self.db)
        self.assertEqual(reopened.get(candidate_id)["guid"], "guid-1")

    def test_same_guid_repeated_poll_is_exact_duplicate(self) -> None:
        store = CandidateStore(self.db)
        first, _ = store.add_entry(feed(), entry(url="https://x.test/one", guid="stable"))
        second, outcome = store.add_entry(feed(), entry(url="https://x.test/changed", guid="stable"))
        self.assertEqual(first, second)
        self.assertEqual(outcome, "exact_duplicate")
        self.assertEqual(len(store.list_candidates()), 1)

    def test_same_canonical_url_across_feeds_is_duplicate_candidate(self) -> None:
        store = CandidateStore(self.db)
        first, _ = store.add_entry(feed("one"), entry(url="https://x.test/story?utm_source=a"))
        second, state = store.add_entry(feed("two"), entry(url="https://x.test/story"))
        self.assertEqual(state, "duplicate")
        self.assertEqual(store.get(second)["duplicate_of"], first)
        self.assertEqual(store.get(second)["dedupe_reason"], "same_canonical_url")

    def test_fallback_identity_is_deterministic(self) -> None:
        store = CandidateStore(self.db)
        item = entry(url="", guid="")
        first, _ = store.add_entry(feed(), item)
        second, outcome = store.add_entry(feed(), item)
        self.assertEqual(first, second)
        self.assertEqual(outcome, "exact_duplicate")
        self.assertEqual(store.get(first)["identity_kind"], "content_hash")

    def test_nearly_identical_title_marked_duplicate(self) -> None:
        store = CandidateStore(self.db)
        first, _ = store.add_entry(feed("one"), entry(title="OpenAI releases a major agent runtime", url="https://one.test/a"))
        second, state = store.add_entry(feed("two"), entry(title="OpenAI releases major agent runtime", url="https://two.test/b"))
        self.assertEqual(state, "duplicate")
        self.assertEqual(store.get(second)["duplicate_of"], first)

    def test_state_transition_and_uniqueness(self) -> None:
        store = CandidateStore(self.db)
        candidate_id, _ = store.add_entry(feed(), entry(guid="state"))
        store.transition(candidate_id, "evaluated", editorial_score=88, editorial_reasoning="Useful")
        self.assertEqual(store.get(candidate_id)["editorial_score"], 88)
        with self.assertRaises(ValueError):
            store.transition(candidate_id, "promoted")

    def test_concurrent_inserts_are_safe(self) -> None:
        CandidateStore(self.db)
        subjects = ["agents", "terraform", "linux", "azure", "aws", "ollama", "security", "storage", "networking", "python", "databases", "observability"]
        def insert(i: int) -> str:
            store = CandidateStore(self.db)
            return store.add_entry(feed(), entry(title=f"{subjects[i]} engineering report", url=f"https://x.test/{i}", guid=f"g-{i}"))[1]
        with ThreadPoolExecutor(max_workers=4) as pool:
            outcomes = list(pool.map(insert, range(12)))
        self.assertEqual(outcomes, ["new"] * 12)
        self.assertEqual(len(CandidateStore(self.db).list_candidates()), 12)


class PollBoundaryTests(TempCase):
    def config(self) -> Path:
        path = self.root / "metadata" / "feeds.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"feeds": [{"id": "lab", "name": "Lab", "url": "https://x.test/rss"}]}))
        return path

    def test_poll_stores_candidate_and_never_writes_kb_inbox(self) -> None:
        summary = poll_configured_feeds(self.config(), self.db, root=self.root, fetcher=lambda _: RSS)
        self.assertEqual(summary.new_candidates, 1)
        self.assertTrue(self.db.exists())
        self.assertFalse((self.root / "raw").exists())

    def test_repeated_poll_reports_duplicate(self) -> None:
        config = self.config()
        poll_configured_feeds(config, self.db, root=self.root, fetcher=lambda _: RSS)
        second = poll_configured_feeds(config, self.db, root=self.root, fetcher=lambda _: RSS)
        self.assertEqual(second.new_candidates, 0)
        self.assertEqual(second.duplicates, 1)

    def test_invalid_feed_does_not_block_valid_feed(self) -> None:
        config = self.config()
        payload = json.loads(config.read_text())
        payload["feeds"].insert(0, {"id": "bad", "name": "Bad", "url": "invalid"})
        config.write_text(json.dumps(payload))
        summary = poll_configured_feeds(config, self.db, root=self.root, fetcher=lambda _: RSS)
        self.assertEqual(summary.new_candidates, 1)
        self.assertEqual(len(summary.errors), 1)


class EditorialEvaluationTests(TempCase):
    def setUp(self) -> None:
        super().setUp()
        self.store = CandidateStore(self.db)
        self.candidate_id, _ = self.store.add_entry(feed(), entry(guid="eval"))
        self.profile = {"prompt_version": "test", "prioritize": ["agents"], "deemphasize": ["marketing"]}

    def test_valid_structured_result_persists_score_and_reason(self) -> None:
        evaluated, errors = evaluate_candidates(self.store, self.profile, evaluator=lambda p, m: VALID_EVALUATION)
        candidate = self.store.get(self.candidate_id)
        self.assertEqual((evaluated, errors), (1, 0))
        self.assertEqual(candidate["state"], "evaluated")
        self.assertEqual(candidate["editorial_score"], 83)
        self.assertIn("agent application", candidate["editorial_reasoning"])
        self.assertEqual(candidate["evaluation_model"], "phi4:latest")

    def test_malformed_model_output_preserves_candidate_for_retry(self) -> None:
        evaluated, errors = evaluate_candidates(self.store, self.profile, evaluator=lambda p, m: "not json")
        self.assertEqual((evaluated, errors), (0, 1))
        self.assertEqual(self.store.get(self.candidate_id)["state"], "error")
        evaluated, errors = evaluate_candidates(self.store, self.profile, evaluator=lambda p, m: VALID_EVALUATION)
        self.assertEqual((evaluated, errors), (1, 0))
        self.assertEqual(self.store.get(self.candidate_id)["state"], "evaluated")

    def test_ollama_unavailable_is_retryable_error(self) -> None:
        def unavailable(prompt: str, model: str) -> str:
            raise ConnectionError("Ollama unavailable")
        evaluate_candidates(self.store, self.profile, evaluator=unavailable)
        candidate = self.store.get(self.candidate_id)
        self.assertEqual(candidate["state"], "error")
        self.assertIn("Ollama unavailable", candidate["last_error"])

    def test_score_validation_rejects_out_of_range(self) -> None:
        payload = json.loads(VALID_EVALUATION)
        payload["novelty"] = 101
        with self.assertRaises(ValueError):
            parse_evaluation(json.dumps(payload))

    def test_evaluation_batch_is_recent_and_feed_diverse(self) -> None:
        store = CandidateStore(self.root / "diverse.db")
        for feed_id in ("alpha", "beta", "gamma"):
            for day in (1, 2):
                topic = "legacy database history" if day == 1 else "current quantum platform"
                source = entry(title=f"{feed_id} {topic}", url=f"https://{feed_id}.test/{day}", guid=f"{feed_id}-{day}")
                source.published_at = f"2026-08-0{day}T12:00:00+00:00"
                store.add_entry(feed(feed_id), source)
        batch = store.evaluation_candidates(3)
        self.assertEqual({item["feed_id"] for item in batch}, {"alpha", "beta", "gamma"})
        self.assertTrue(all(item["published_at"].startswith("2026-08-02") for item in batch))


class EditionSelectionTests(TempCase):
    def setUp(self) -> None:
        super().setUp()
        self.store = CandidateStore(self.db)

    def add_evaluated(self, title: str, score: int, feed_id: str, url: str, priority: int = 0) -> str:
        candidate_id, _ = self.store.add_entry(feed(feed_id, priority=priority), entry(title=title, url=url, guid=f"{feed_id}-{title}"))
        self.store.transition(candidate_id, "evaluated", editorial_score=score, editorial_reasoning=f"Why {title}")
        return candidate_id

    def test_selects_configured_number_prioritizing_score(self) -> None:
        titles = ["Agent runtime security", "AWS migration tooling", "Local model inference", "Linux container update", "Terraform provider design"]
        for i, score in enumerate([99, 95, 90, 80, 70]):
            self.add_evaluated(titles[i], score, f"feed-{i}", f"https://x.test/{i}")
        edition = build_edition(self.store, "2026-08-09", self.root / "editions", target=3)
        self.assertEqual(len(edition["items"]), 3)
        self.assertEqual([item["editorial_score"] for item in edition["items"]], [99, 95, 90])

    def test_avoids_same_feed_dominating_when_alternatives_exist(self) -> None:
        vendor_titles = ["Agent runtime release", "Cloud migration toolkit", "Container platform security"]
        for i, score in enumerate([99, 98, 97]):
            self.add_evaluated(vendor_titles[i], score, "vendor", f"https://v.test/{i}")
        self.add_evaluated("Independent platform story", 90, "independent", "https://i.test/1")
        edition = build_edition(self.store, "2026-08-09", self.root / "editions", target=3)
        self.assertEqual([item["feed_id"] for item in edition["items"]].count("vendor"), 2)
        self.assertIn("independent", [item["feed_id"] for item in edition["items"]])

    def test_duplicate_candidates_are_excluded(self) -> None:
        self.add_evaluated("Primary story", 90, "one", "https://x.test/shared")
        _, state = self.store.add_entry(feed("two"), entry(title="Syndicated story", url="https://x.test/shared"))
        self.assertEqual(state, "duplicate")
        edition = build_edition(self.store, "2026-08-09", self.root / "editions", target=5)
        self.assertEqual(len(edition["items"]), 1)

    def test_recent_story_is_not_reselected(self) -> None:
        old = self.add_evaluated("Agent release", 95, "one", "https://x.test/old")
        first = build_edition(self.store, "2026-08-08", self.root / "editions", target=1)
        self.assertEqual(first["items"][0]["candidate_id"], old)
        new = self.add_evaluated("Agent release update", 99, "two", "https://x.test/new")
        second = build_edition(self.store, "2026-08-09", self.root / "editions", target=1)
        self.assertEqual(second["items"], [])
        self.assertEqual(self.store.get(new)["state"], "not_selected")

    def test_edition_generation_is_idempotent(self) -> None:
        self.add_evaluated("One", 90, "one", "https://x.test/1")
        first = build_edition(self.store, "2026-08-09", self.root / "editions", target=1)
        self.add_evaluated("Two", 99, "two", "https://x.test/2")
        second = build_edition(self.store, "2026-08-09", self.root / "editions", target=2)
        self.assertEqual(first["edition_id"], second["edition_id"])
        self.assertEqual(len(second["items"]), 1)
        self.assertTrue(Path(second["artifact_path"]).exists())

    def test_prune_preserves_selected_and_removes_old_low_value(self) -> None:
        old_time = (datetime.now(timezone.utc) - timedelta(days=60)).replace(microsecond=0).isoformat()
        selected = self.add_evaluated("Keep", 90, "one", "https://x.test/keep")
        build_edition(self.store, "2026-08-09", self.root / "editions", target=1)
        duplicate, _ = self.store.add_entry(feed("two"), entry(title="Old duplicate", url="https://x.test/keep"), discovered_at=old_time)
        removed = self.store.prune(30)
        self.assertEqual(removed, 1)
        self.assertIsNotNone(self.store.get(selected))
        self.assertIsNone(self.store.get(duplicate))

    def test_selection_excludes_stale_backfill_items(self) -> None:
        stale = self.add_evaluated("Old high score", 99, "old", "https://x.test/old")
        with self.store.connect() as conn:
            conn.execute("UPDATE candidates SET published_at='2026-01-01T00:00:00+00:00' WHERE candidate_id=?", (stale,))
        fresh = self.add_evaluated("Current lower score", 80, "fresh", "https://x.test/fresh")
        edition = build_edition(self.store, "2026-08-09", self.root / "editions", target=2, max_age_days=14)
        self.assertEqual([item["candidate_id"] for item in edition["items"]], [fresh])

    def test_selection_does_not_fill_slots_below_minimum_score(self) -> None:
        keep = self.add_evaluated("Useful current story", 70, "keep", "https://x.test/keep")
        low = self.add_evaluated("Irrelevant current filler", 20, "low", "https://x.test/low")
        edition = build_edition(self.store, "2026-08-09", self.root / "editions", target=5, min_score=50)
        self.assertEqual([item["candidate_id"] for item in edition["items"]], [keep])
        self.assertNotEqual(self.store.get(low)["state"], "selected")


class NarrativeGenerationTests(TempCase):
    def setUp(self) -> None:
        super().setUp()
        self.store = CandidateStore(self.db)
        self.out = self.root / "narratives"

    def add_selected(self, title: str, feed_id: str, url: str, categories: list[str] | None = None) -> str:
        source = entry(title=title, url=url, guid=f"{feed_id}-{title}")
        source.categories = categories or []
        candidate_id, _ = self.store.add_entry(feed(feed_id, name=feed_id.title()), source)
        self.store.transition(candidate_id, "evaluated", editorial_score=90, editorial_reasoning=f"Why {title}")
        return candidate_id

    @staticmethod
    def response(edition: dict, sections: list[dict] | None = None) -> str:
        ids = [item["candidate_id"] for item in edition["items"]]
        return json.dumps({
            "edition_date": edition["briefing_date"],
            "headline": "Infrastructure and AI systems converge",
            "opening": "Today's developments center on practical system design.",
            "sections": sections or [{
                "section_title": "The main shift",
                "narrative_text": "The sources report a concrete change. Analysis: this may alter architecture choices.",
                "supporting_item_ids": ids,
                "key_takeaway": "Evaluate the operational tradeoffs.",
            }],
            "what_to_watch": ["Implementation details and independent measurements."],
        })

    def build(self, count: int = 2) -> dict:
        self.add_selected("Acme agent runtime security architecture", "vendor", "https://vendor.test/runtime", ["agents"])
        if count > 1:
            self.add_selected("Acme agent runtime security analysis", "analysis", "https://analysis.test/runtime", ["agents"])
        return build_edition(self.store, "2026-08-09", self.root / "editions", target=count)

    def test_grouping_related_and_unrelated_items(self) -> None:
        edition = self.build(2)
        groups = group_related_items(edition["items"])
        self.assertEqual(len(groups), 1)
        third = dict(edition["items"][0], candidate_id="other", title="Linux kernel filesystem performance",
                     summary="Filesystem benchmark results", editorial_reasoning="Kernel performance analysis",
                     categories_json="[]")
        groups = group_related_items(edition["items"] + [third])
        self.assertEqual(sorted(len(group["item_ids"]) for group in groups), [1, 2])

    def test_architectural_grouping_is_vendor_independent_and_not_forced(self) -> None:
        def item(item_id: str, title: str, summary: str, feed_id: str) -> dict:
            return {
                "candidate_id": item_id, "title": title, "summary": summary,
                "editorial_reasoning": "", "categories_json": "[]", "feed_id": feed_id,
            }
        vector = item("vector", "DynamoDB real-time vector search", "Native semantic similarity search for AI applications", "aws")
        runtime = item("runtime", "AgentCore persistent runtime", "Managed runtime for persistent multi-agent workloads", "aws")
        compute = item("compute", "EC2 R8i instances", "Intel processors and higher memory bandwidth", "aws")
        network = item("network", "Azure ExpressRoute resiliency guard", "Hybrid network gateway resilience", "azure")
        groups = group_related_items([vector, runtime, compute, network])
        self.assertEqual([group["item_ids"] for group in groups], [["vector", "runtime"], ["compute"], ["network"]])
        self.assertIn("AI application infrastructure", groups[0]["relationship"])
        self.assertEqual(groups[0]["relationship_type"], "thematic")
        self.assertFalse(groups[0]["direct_product_integration"])
        self.assertFalse(groups[0]["causal_relationship"])
        self.assertEqual(groups[1]["relationship_type"], "standalone")
        self.assertIn("compute/platform foundation", groups[1]["architectural_themes"])
        self.assertIn("hybrid network resilience", groups[2]["architectural_themes"])

    def test_prompt_requires_evidence_bounded_wording(self) -> None:
        edition = self.build(2)
        prompt = build_narrative_prompt(edition, group_related_items(edition["items"]))
        self.assertIn("parallel architectural developments", prompt)
        self.assertIn('"AWS says"', prompt)
        self.assertIn("may influence", prompt)
        self.assertIn("It will be worth seeing whether", prompt)
        self.assertIn("not evidence of direct integration", prompt)
        self.assertIn("When direct_product_integration is false", prompt)
        self.assertIn('"One concerns', prompt)
        self.assertIn('the data layer, while the other concerns runtime infrastructure"', prompt)

    def test_thematic_group_rejects_unsupported_product_relationship_language(self) -> None:
        edition = self.build(2)
        groups = group_related_items(edition["items"])
        self.assertEqual(groups[0]["relationship_type"], "thematic")
        for wording in (
            "The products are integrating seamlessly for operators.",
            "This integration combines the two product capabilities.",
            "The services provide an interlinked architecture.",
            "The announcements describe interconnected products.",
        ):
            payload = json.loads(self.response(edition))
            payload["sections"][0]["narrative_text"] = wording
            with self.subTest(wording=wording), self.assertRaisesRegex(
                    ValueError, "unsupported_integration"):
                validate_narrative(json.dumps(payload), edition, groups)

    def test_thematic_architectural_synthesis_without_integration_validates(self) -> None:
        edition = self.build(2)
        groups = group_related_items(edition["items"])
        payload = json.loads(self.response(edition))
        payload["sections"][0]["narrative_text"] = (
            "Both announcements are relevant to AI application infrastructure. "
            "One concerns the data layer, while the other concerns runtime infrastructure."
        )
        self.assertEqual(validate_narrative(json.dumps(payload), edition, groups)["topic_groups"], groups)

    def test_global_prose_cannot_imply_integration_for_thematic_group(self) -> None:
        edition = self.build(2)
        groups = group_related_items(edition["items"])
        payload = json.loads(self.response(edition))
        payload["what_to_watch"] = ["Watch how the integration of these products changes operations."]
        violations = detect_narrative_violations(payload, groups)
        self.assertEqual(violations[0]["unit_id"], "what_to_watch.0")
        self.assertIn("unsupported_integration", violations[0]["violation_types"])

    def test_supported_product_integration_language_remains_possible(self) -> None:
        edition = self.build(2)
        groups = group_related_items(edition["items"])
        groups[0]["direct_product_integration"] = True
        payload = json.loads(self.response(edition))
        payload["sections"][0]["narrative_text"] = "The documented integration connects the two services."
        self.assertEqual(validate_narrative(json.dumps(payload), edition, groups)["topic_groups"], groups)

    def test_related_cross_vendor_networking_groups_but_same_vendor_unrelated_does_not(self) -> None:
        items = [
            {"candidate_id": "aws-network", "title": "AWS hybrid network resiliency", "summary": "gateway connectivity resilience", "editorial_reasoning": "", "categories_json": "[]"},
            {"candidate_id": "azure-network", "title": "Azure ExpressRoute guard", "summary": "multicloud network resilience", "editorial_reasoning": "", "categories_json": "[]"},
            {"candidate_id": "aws-tool", "title": "AWS developer CLI update", "summary": "developer tooling commands", "editorial_reasoning": "", "categories_json": "[]"},
        ]
        groups = group_related_items(items)
        self.assertEqual([group["item_ids"] for group in groups], [["aws-network", "azure-network"], ["aws-tool"]])

    def test_valid_generation_preserves_provenance_and_path(self) -> None:
        edition = self.build()
        result = generate_narrative(self.store, "2026-08-09", self.out,
                                    generator=lambda prompt, model: self.response(edition))
        self.assertTrue(result.success)
        self.assertEqual(Path(result.generation["artifact_path"]), self.out / "2026-08-09-narrative.md")
        provenance = result.generation["narrative"]["source_provenance"]
        self.assertEqual({item["item_id"] for item in provenance}, {item["candidate_id"] for item in edition["items"]})
        self.assertEqual({item["canonical_url"] for item in provenance}, {item["canonical_url"] for item in edition["items"]})
        artifact = Path(result.generation["artifact_path"]).read_text()
        self.assertIn("## Source appendix", artifact)
        self.assertIn("https://vendor.test/runtime", artifact)

    def test_unknown_item_and_invalid_response_are_retryable_failures(self) -> None:
        edition = self.build(1)
        payload = json.loads(self.response(edition))
        payload["sections"][0]["supporting_item_ids"] = ["BFC-hallucinated"]
        unknown = generate_narrative(self.store, "2026-08-09", self.out, generator=lambda p, m: json.dumps(payload))
        self.assertFalse(unknown.success)
        self.assertIn("unknown item", unknown.error)
        invalid = generate_narrative(self.store, "2026-08-09", self.out, generator=lambda p, m: "not JSON")
        self.assertFalse(invalid.success)
        self.assertIsNone(self.store.current_narrative(edition["edition_id"]))
        self.assertTrue(Path(edition["artifact_path"]).exists())

    def test_high_risk_wording_is_rejected_without_replacing_current_generation(self) -> None:
        edition = self.build(1)
        first = generate_narrative(self.store, "2026-08-09", self.out,
                                   generator=lambda p, m: self.response(edition))
        payload = json.loads(self.response(edition))
        payload["sections"][0]["narrative_text"] = "This unprecedented feature is set to change architecture."
        rejected = generate_narrative(self.store, "2026-08-09", self.out, regenerate=True,
                                      generator=lambda p, m: json.dumps(payload))
        self.assertFalse(rejected.success)
        self.assertIn("cleanup retry limit reached", rejected.error)
        self.assertEqual(self.store.current_narrative(edition["edition_id"])["generation_id"],
                         first.generation["generation_id"])
        with self.store.connect() as conn:
            history = conn.execute(
                "SELECT status,is_current FROM narrative_generations WHERE edition_id=? ORDER BY generation_id",
                (edition["edition_id"],),
            ).fetchall()
        self.assertEqual([(row["status"], row["is_current"]) for row in history],
                         [("ready", 1), ("failed", 0)])

    def test_attributed_claims_and_cautious_prospective_language_validate(self) -> None:
        edition = self.build(1)
        payload = json.loads(self.response(edition))
        payload["sections"][0]["narrative_text"] = (
            "The vendor says the instance offers higher performance than its prior generation. "
            "Analysis: this may give architects another option for memory-intensive workloads."
        )
        payload["what_to_watch"] = ["It will be worth seeing whether operators report similar results."]
        result = generate_narrative(self.store, "2026-08-09", self.out,
                                    generator=lambda p, m: json.dumps(payload))
        self.assertTrue(result.success)

    def test_absolute_and_vague_performance_wording_is_rejected(self) -> None:
        edition = self.build(1)
        groups = group_related_items(edition["items"])
        for wording in (
            "This capability eliminates the need for another database.",
            "The instance provides superior performance for applications.",
        ):
            payload = json.loads(self.response(edition))
            payload["sections"][0]["narrative_text"] = wording
            with self.subTest(wording=wording), self.assertRaisesRegex(
                    ValueError, "unsupported_absolute|vague_performance_claim"):
                validate_narrative(json.dumps(payload), edition, groups)

    def test_eliminate_need_variants_and_cautious_alternatives(self) -> None:
        edition = self.build(1)
        groups = group_related_items(edition["items"])
        for wording in (
            "This capability can eliminate the need for another database.",
            "This capability eliminates the need for another database.",
            "This capability is eliminating the need for another database.",
        ):
            payload = json.loads(self.response(edition))
            payload["sections"][0]["narrative_text"] = wording
            with self.subTest(wording=wording), self.assertRaisesRegex(ValueError, "unsupported_absolute"):
                validate_narrative(json.dumps(payload), edition, groups)
        for wording in (
            "This capability may reduce the need for another database.",
            "This capability can reduce the need for another database.",
        ):
            payload = json.loads(self.response(edition))
            payload["sections"][0]["narrative_text"] = wording
            with self.subTest(wording=wording):
                self.assertEqual(validate_narrative(json.dumps(payload), edition, groups)["topic_groups"], groups)

    def test_promotional_technical_adjectives_are_rejected_but_precise_measurement_passes(self) -> None:
        edition = self.build(1)
        groups = group_related_items(edition["items"])
        for wording in (
            "The instance offers exceptional aSAPS ratings.",
            "The instance delivers outstanding performance.",
            "The service provides remarkable throughput.",
        ):
            payload = json.loads(self.response(edition))
            payload["sections"][0]["narrative_text"] = wording
            with self.subTest(wording=wording), self.assertRaisesRegex(ValueError, "vague_performance_claim"):
                validate_narrative(json.dumps(payload), edition, groups)
        for wording in (
            "AWS lists the instance with an aSAPS rating of 142,100.",
            "The instance uses Intel Xeon 6 processors.",
            "AWS says the instance provides 20% higher performance than R7i instances.",
        ):
            payload = json.loads(self.response(edition))
            payload["sections"][0]["narrative_text"] = wording
            with self.subTest(wording=wording):
                if wording.startswith("AWS"):
                    payload_item = edition["items"][0]
                    payload_item["feed_name"] = "AWS What's New"
                self.assertEqual(validate_narrative(json.dumps(payload), edition, groups)["topic_groups"], groups)

    def test_cleanup_replaces_promotional_core_claim_with_stored_measurement(self) -> None:
        edition = self.build(1)
        item_id = edition["items"][0]["candidate_id"]
        evidence = "R8i instances are SAP-certified and deliver 142,100 aSAPS."
        with self.store.connect() as conn:
            conn.execute("UPDATE candidates SET feed_name='AWS What''s New',summary=?,content=? WHERE candidate_id=?",
                         (evidence, evidence, item_id))
        payload = json.loads(self.response(edition))
        payload["sections"][0]["narrative_text"] = "The instances offer exceptional aSAPS ratings."
        replacement = "AWS lists the instances with an aSAPS rating of 142,100."
        cleanup = json.dumps({"action": "replace", "replacement_sentence": replacement,
                              "supporting_item_ids": [item_id]})
        result = generate_narrative(self.store, "2026-08-09", self.out,
                                    generator=lambda p, m: json.dumps(payload),
                                    cleanup_generator=lambda p, m: cleanup)
        self.assertTrue(result.success)
        self.assertEqual(result.generation["narrative"]["sections"][0]["narrative_text"], replacement)

    def test_cautious_absolute_alternative_and_product_facts_validate(self) -> None:
        edition = self.build(1)
        groups = group_related_items(edition["items"])
        payload = json.loads(self.response(edition))
        payload["sections"][0]["narrative_text"] = (
            "The capability may reduce the need for a separate database in some architectures. "
            "R8i instances use Intel Xeon 6 processors."
        )
        self.assertEqual(validate_narrative(json.dumps(payload), edition, groups)["topic_groups"], groups)

    def test_performance_and_price_performance_claims_require_vendor_attribution(self) -> None:
        edition = self.build(1)
        groups = group_related_items(edition["items"])
        for wording in (
            "The instance provides improved performance over the prior generation.",
            "The instance offers better price-performance for these workloads.",
        ):
            payload = json.loads(self.response(edition))
            payload["sections"][0]["narrative_text"] = wording
            with self.subTest(wording=wording), self.assertRaisesRegex(
                    ValueError, "unattributed_performance_claim"):
                validate_narrative(json.dumps(payload), edition, groups)

        for wording in (
            "The vendor says the instance provides improved performance over the prior generation.",
            "According to the vendor, the instance offers better price-performance for these workloads.",
        ):
            payload = json.loads(self.response(edition))
            payload["sections"][0]["narrative_text"] = wording
            with self.subTest(wording=wording):
                self.assertEqual(validate_narrative(json.dumps(payload), edition, groups)["topic_groups"], groups)

    def test_two_stage_cleanup_replaces_only_flagged_sentence_and_records_audit(self) -> None:
        edition = self.build(1)
        payload = json.loads(self.response(edition))
        payload["sections"][0]["narrative_text"] = (
            "A stable factual sentence. This capability eliminates the need for another database."
        )
        cleanup = json.dumps({"action": "replace",
                              "replacement_sentence": "This capability may reduce the need for another database.",
                              "supporting_item_ids": [edition["items"][0]["candidate_id"]]})
        result = generate_narrative(self.store, "2026-08-09", self.out,
                                    generator=lambda p, m: json.dumps(payload),
                                    cleanup_generator=lambda p, m: cleanup)
        self.assertTrue(result.success)
        text = result.generation["narrative"]["sections"][0]["narrative_text"]
        self.assertEqual(text, "A stable factual sentence. This capability may reduce the need for another database.")
        with self.store.connect() as conn:
            run = conn.execute("SELECT * FROM narrative_pipeline_runs WHERE generation_id=?",
                               (result.generation["generation_id"],)).fetchone()
            attempts = conn.execute("SELECT * FROM narrative_cleanup_attempts WHERE generation_id=?",
                                    (result.generation["generation_id"],)).fetchall()
        self.assertEqual(run["final_validation"], "passed")
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["status"], "accepted")

    def test_cleanup_can_succeed_on_second_attempt_without_resynthesis(self) -> None:
        edition = self.build(1)
        payload = json.loads(self.response(edition))
        payload["sections"][0]["narrative_text"] = "This capability eliminates the need for another database."
        calls = {"synthesis": 0, "cleanup": 0}
        def synth(prompt: str, model: str) -> str:
            calls["synthesis"] += 1
            return json.dumps(payload)
        def clean(prompt: str, model: str) -> str:
            calls["cleanup"] += 1
            replacement = ("This capability removes the need for another database." if calls["cleanup"] == 1
                           else "This capability may reduce the need for another database.")
            return json.dumps({"action": "replace", "replacement_sentence": replacement,
                               "supporting_item_ids": [edition["items"][0]["candidate_id"]]})
        result = generate_narrative(self.store, "2026-08-09", self.out, generator=synth, cleanup_generator=clean)
        self.assertTrue(result.success)
        self.assertEqual(calls, {"synthesis": 1, "cleanup": 2})

    def test_cleanup_retry_limit_and_unknown_ids_preserve_previous_current(self) -> None:
        edition = self.build(1)
        first = generate_narrative(self.store, "2026-08-09", self.out,
                                   generator=lambda p, m: self.response(edition))
        payload = json.loads(self.response(edition))
        payload["sections"][0]["narrative_text"] = "This capability eliminates the need for another database."
        bad_cleanup = json.dumps({"action": "replace", "replacement_sentence": "A weaker statement.",
                                  "supporting_item_ids": ["BFC-unknown"]})
        failed = generate_narrative(self.store, "2026-08-09", self.out, regenerate=True,
                                    generator=lambda p, m: json.dumps(payload),
                                    cleanup_generator=lambda p, m: bad_cleanup)
        self.assertFalse(failed.success)
        self.assertIn("cleanup retry limit reached", failed.error)
        self.assertEqual(self.store.current_narrative(edition["edition_id"])["generation_id"],
                         first.generation["generation_id"])
        with self.store.connect() as conn:
            attempts = conn.execute("SELECT * FROM narrative_cleanup_attempts ORDER BY cleanup_attempt_id").fetchall()
        self.assertEqual(len(attempts), 2)
        self.assertTrue(all("unknown supporting item IDs" in row["error"] for row in attempts))

    def test_nonessential_fallback_removes_only_unresolved_watch_entry(self) -> None:
        edition = self.build(2)
        payload = json.loads(self.response(edition))
        payload["what_to_watch"] = [
            "Watch how the integration of these products changes operations.",
            "Architects may want to watch adoption patterns.",
        ]
        calls = {"synthesis": 0, "cleanup": 0}
        def synth(prompt: str, model: str) -> str:
            calls["synthesis"] += 1
            return json.dumps(payload)
        def unresolved(prompt: str, model: str) -> str:
            calls["cleanup"] += 1
            return json.dumps({"action": "unchanged", "replacement_sentence": "",
                               "supporting_item_ids": []})
        result = generate_narrative(self.store, "2026-08-09", self.out,
                                    generator=synth, cleanup_generator=unresolved)
        self.assertTrue(result.success)
        self.assertEqual(calls, {"synthesis": 1, "cleanup": 2})
        self.assertEqual(result.generation["narrative"]["what_to_watch"],
                         ["Architects may want to watch adoption patterns."])
        self.assertEqual(len(result.generation["narrative"]["source_provenance"]), 2)
        with self.store.connect() as conn:
            attempts = conn.execute("SELECT * FROM narrative_cleanup_attempts WHERE generation_id=?",
                                    (result.generation["generation_id"],)).fetchall()
            fallback = conn.execute("SELECT * FROM narrative_cleanup_fallbacks WHERE generation_id=?",
                                    (result.generation["generation_id"],)).fetchone()
        self.assertEqual(len(attempts), 2)
        self.assertEqual(fallback["action"], "remove")
        self.assertEqual(fallback["criticality"], "nonessential")
        self.assertEqual(fallback["cleanup_attempts_exhausted"], 2)
        self.assertEqual(fallback["reason"], "retry limit exhausted")

    def test_nonessential_fallback_allows_empty_watch_collection(self) -> None:
        edition = self.build(2)
        payload = json.loads(self.response(edition))
        payload["what_to_watch"] = ["The products will integrate seamlessly."]
        unresolved = json.dumps({"action": "unchanged", "replacement_sentence": "",
                                 "supporting_item_ids": []})
        result = generate_narrative(self.store, "2026-08-09", self.out,
                                    generator=lambda p, m: json.dumps(payload),
                                    cleanup_generator=lambda p, m: unresolved)
        self.assertTrue(result.success)
        self.assertEqual(result.generation["narrative"]["what_to_watch"], [])
        self.assertNotIn("## What to watch", Path(result.generation["artifact_path"]).read_text())

    def test_core_cleanup_failure_is_never_removed(self) -> None:
        edition = self.build(1)
        first = generate_narrative(self.store, "2026-08-09", self.out,
                                   generator=lambda p, m: self.response(edition))
        payload = json.loads(self.response(edition))
        payload["sections"][0]["narrative_text"] = "This capability eliminates the need for another database."
        unresolved = json.dumps({"action": "unchanged", "replacement_sentence": "",
                                 "supporting_item_ids": [edition["items"][0]["candidate_id"]]})
        failed = generate_narrative(self.store, "2026-08-09", self.out, regenerate=True,
                                    generator=lambda p, m: json.dumps(payload),
                                    cleanup_generator=lambda p, m: unresolved)
        self.assertFalse(failed.success)
        self.assertIn("core unit", failed.error)
        self.assertEqual(self.store.current_narrative(edition["edition_id"])["generation_id"],
                         first.generation["generation_id"])
        with self.store.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM narrative_cleanup_fallbacks").fetchone()[0], 0)

    def test_supported_core_claim_gets_deterministic_aws_attribution(self) -> None:
        edition = self.build(1)
        item_id = edition["items"][0]["candidate_id"]
        evidence = ("R8i offers up to 15% better price-performance compared to previous generation "
                    "Intel-based instances.")
        with self.store.connect() as conn:
            conn.execute("UPDATE candidates SET feed_name='AWS What''s New',summary=?,content=? WHERE candidate_id=?",
                         (evidence, evidence, item_id))
        payload = json.loads(self.response(edition))
        claim = "R8i offers up to 15% better price-performance compared to previous generation Intel-based instances."
        payload["sections"][0]["narrative_text"] = claim
        calls = {"synthesis": 0, "cleanup": 0}
        def synth(prompt: str, model: str) -> str:
            calls["synthesis"] += 1
            return json.dumps(payload)
        def unresolved(prompt: str, model: str) -> str:
            calls["cleanup"] += 1
            return json.dumps({"action": "unchanged", "replacement_sentence": "",
                               "supporting_item_ids": [item_id], "publisher": "Microsoft"})
        result = generate_narrative(self.store, "2026-08-09", self.out,
                                    generator=synth, cleanup_generator=unresolved)
        self.assertTrue(result.success)
        self.assertEqual(calls, {"synthesis": 1, "cleanup": 2})
        normalized = result.generation["narrative"]["sections"][0]["narrative_text"]
        self.assertEqual(normalized, "According to AWS, r8i offers up to 15% better price-performance "
                                     "compared to previous generation Intel-based instances.")
        self.assertIn("15%", normalized)
        self.assertIn("previous generation Intel-based instances", normalized)
        with self.store.connect() as conn:
            audit = conn.execute("SELECT * FROM narrative_attribution_normalizations WHERE generation_id=?",
                                 (result.generation["generation_id"],)).fetchone()
            attempts = conn.execute("SELECT COUNT(*) FROM narrative_cleanup_attempts WHERE generation_id=?",
                                    (result.generation["generation_id"],)).fetchone()[0]
        self.assertEqual(attempts, 2)
        self.assertEqual(audit["canonical_publisher"], "AWS")
        self.assertEqual(audit["action"], "normalize_attribution")
        self.assertNotIn("Microsoft", audit["normalized_text"])

    def test_attribution_normalization_rejects_invented_metric(self) -> None:
        edition = self.build(1)
        item_id = edition["items"][0]["candidate_id"]
        with self.store.connect() as conn:
            conn.execute("UPDATE candidates SET feed_name='AWS What''s New',summary='15% better price-performance',"
                         "content='15% better price-performance' WHERE candidate_id=?", (item_id,))
        payload = json.loads(self.response(edition))
        payload["sections"][0]["narrative_text"] = "R8i offers 99% better price-performance."
        unresolved = json.dumps({"action": "unchanged", "replacement_sentence": "",
                                 "supporting_item_ids": [item_id]})
        result = generate_narrative(self.store, "2026-08-09", self.out,
                                    generator=lambda p, m: json.dumps(payload),
                                    cleanup_generator=lambda p, m: unresolved)
        self.assertFalse(result.success)
        with self.store.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM narrative_attribution_normalizations").fetchone()[0], 0)

    def test_wrong_publisher_and_vague_claim_are_not_rescued(self) -> None:
        edition = self.build(1)
        item_id = edition["items"][0]["candidate_id"]
        with self.store.connect() as conn:
            conn.execute("UPDATE candidates SET feed_name='AWS What''s New',summary='15% better price-performance',"
                         "content='15% better price-performance' WHERE candidate_id=?", (item_id,))
        for claim, replacement in (
            ("R8i offers 15% better price-performance.", "According to Microsoft, r8i offers 15% better price-performance."),
            ("R8i provides high performance.", "R8i provides high performance."),
        ):
            payload = json.loads(self.response(edition))
            payload["sections"][0]["narrative_text"] = claim
            cleanup = json.dumps({"action": "replace", "replacement_sentence": replacement,
                                  "supporting_item_ids": [item_id]})
            result = generate_narrative(self.store, "2026-08-09", self.out, regenerate=True,
                                        generator=lambda p, m, value=json.dumps(payload): value,
                                        cleanup_generator=lambda p, m, value=cleanup: value)
            self.assertFalse(result.success)

    def test_comparative_reconstruction_restores_immutable_source_components(self) -> None:
        edition = self.build(1)
        item_id = edition["items"][0]["candidate_id"]
        evidence = ("The R8i and R8i-flex instances offer up to 15% better price-performance "
                    "compared to previous generation Intel-based instances.")
        with self.store.connect() as conn:
            conn.execute("UPDATE candidates SET feed_name='AWS What''s New',summary=?,content=? WHERE candidate_id=?",
                         (evidence, evidence, item_id))
        payload = json.loads(self.response(edition))
        original = "R8i instances offer improved price-performance for cloud workloads."
        payload["sections"][0]["narrative_text"] = original
        cleanup_texts = iter([
            "R8i instances offer up to 20% better price-performance compared to previous generations.",
            "R8i instances offer better price-performance compared to older Intel instances.",
        ])
        calls = {"synthesis": 0, "cleanup": 0}
        def synth(prompt: str, model: str) -> str:
            calls["synthesis"] += 1
            return json.dumps(payload)
        def altered(prompt: str, model: str) -> str:
            calls["cleanup"] += 1
            return json.dumps({"action": "replace", "replacement_sentence": next(cleanup_texts),
                               "supporting_item_ids": [item_id], "publisher": "Microsoft"})
        result = generate_narrative(self.store, "2026-08-09", self.out,
                                    generator=synth, cleanup_generator=altered)
        self.assertTrue(result.success)
        self.assertEqual(calls, {"synthesis": 1, "cleanup": 2})
        expected = ("According to AWS, R8i and R8i-flex instances provide up to 15% better "
                    "price-performance compared with previous generation Intel-based instances.")
        self.assertEqual(result.generation["narrative"]["sections"][0]["narrative_text"], expected)
        with self.store.connect() as conn:
            audit = conn.execute("SELECT * FROM narrative_comparative_reconstructions WHERE generation_id=?",
                                 (result.generation["generation_id"],)).fetchone()
            attempts = conn.execute("SELECT COUNT(*) FROM narrative_cleanup_attempts WHERE generation_id=?",
                                    (result.generation["generation_id"],)).fetchone()[0]
        self.assertEqual(attempts, 2)
        self.assertEqual(audit["publisher"], "AWS")
        self.assertEqual(audit["metric"], "up to 15%")
        self.assertEqual(audit["comparison_dimension"], "price-performance")
        self.assertEqual(audit["baseline"], "previous generation Intel-based instances")
        self.assertEqual(audit["action"], "reconstruct_comparative_claim")
        self.assertNotIn("20%", audit["reconstructed_text"])
        self.assertNotIn("Microsoft", audit["reconstructed_text"])

    def test_ambiguous_source_comparison_prevents_reconstruction(self) -> None:
        edition = self.build(1)
        item_id = edition["items"][0]["candidate_id"]
        evidence = ("The R8i instances offer 15% better price-performance compared to generation A instances. "
                    "The R8i instances offer 10% better price-performance compared to generation B instances.")
        with self.store.connect() as conn:
            conn.execute("UPDATE candidates SET feed_name='AWS What''s New',summary=?,content=? WHERE candidate_id=?",
                         (evidence, evidence, item_id))
        payload = json.loads(self.response(edition))
        payload["sections"][0]["narrative_text"] = "R8i offers improved price-performance."
        unresolved = json.dumps({"action": "unchanged", "replacement_sentence": "",
                                 "supporting_item_ids": [item_id]})
        result = generate_narrative(self.store, "2026-08-09", self.out,
                                    generator=lambda p, m: json.dumps(payload),
                                    cleanup_generator=lambda p, m: unresolved)
        self.assertFalse(result.success)
        with self.store.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM narrative_comparative_reconstructions").fetchone()[0], 0)

    def test_failure_does_not_replace_valid_narrative(self) -> None:
        edition = self.build(1)
        first = generate_narrative(self.store, "2026-08-09", self.out, generator=lambda p, m: self.response(edition))
        failed = generate_narrative(self.store, "2026-08-09", self.out, regenerate=True,
                                    generator=lambda p, m: (_ for _ in ()).throw(ConnectionError("offline")))
        self.assertFalse(failed.success)
        self.assertEqual(self.store.current_narrative(edition["edition_id"])["generation_id"], first.generation["generation_id"])

    def test_idempotency_and_explicit_regeneration(self) -> None:
        edition = self.build(1)
        calls = []
        def generate(prompt: str, model: str) -> str:
            calls.append(prompt)
            return self.response(edition)
        first = generate_narrative(self.store, "2026-08-09", self.out, generator=generate)
        reused = generate_narrative(self.store, "2026-08-09", self.out, generator=generate)
        regenerated = generate_narrative(self.store, "2026-08-09", self.out, regenerate=True, generator=generate)
        self.assertTrue(reused.reused)
        self.assertEqual(len(calls), 2)
        self.assertGreater(regenerated.generation["generation_id"], first.generation["generation_id"])
        self.assertEqual(regenerated.generation["generation_kind"], "regeneration")
        with self.store.connect() as conn:
            history = conn.execute("""
                SELECT generation_id,is_current,status FROM narrative_generations
                WHERE edition_id=? ORDER BY generation_id
            """, (edition["edition_id"],)).fetchall()
        self.assertEqual([(row["generation_id"], row["is_current"], row["status"]) for row in history],
                         [(first.generation["generation_id"], 0, "ready"),
                          (regenerated.generation["generation_id"], 1, "ready")])

    def test_empty_and_single_item_editions(self) -> None:
        empty = build_edition(self.store, "2026-08-08", self.root / "editions", target=2)
        called = False
        def should_not_call(prompt: str, model: str) -> str:
            nonlocal called
            called = True
            return "{}"
        result = generate_narrative(self.store, "2026-08-08", self.out, generator=should_not_call)
        self.assertFalse(result.success)
        self.assertFalse(called)
        edition = self.build(1)
        result = generate_narrative(self.store, "2026-08-09", self.out, generator=lambda p, m: self.response(edition))
        self.assertTrue(result.success)


class RetentionReviewTests(TempCase):
    def setUp(self) -> None:
        super().setUp()
        self.store = CandidateStore(self.db)
        source = entry(title="Agent Runtime Retention Story", url="https://example.com/retention", guid="retention")
        source.author = "Source Author"
        self.item_id, _ = self.store.add_entry(feed("lab", name="Lab Publisher"), source)
        self.store.transition(self.item_id, "evaluated", editorial_score=91, editorial_reasoning="Operationally useful.")
        self.edition = build_edition(self.store, "2026-08-09", self.root / "editions", target=1)

    def decide(self, decision: str, **kwargs: object):
        return apply_retention_decision(
            self.store, "2026-08-09", self.item_id, decision, reviewer="erick",
            root=self.root, references_dir=self.root / "references", **kwargs,
        )

    def test_default_pending_and_valid_discard(self) -> None:
        self.assertEqual(self.store.edition("2026-08-09")["items"][0]["retention_decision"], "pending")
        result = self.decide("discard", note="Ephemeral.")
        self.assertTrue(result.success)
        self.assertEqual(result.decision["action_status"], "completed")
        self.assertFalse((self.root / "raw").exists())
        self.assertIsNotNone(self.store.get(self.item_id))

    def test_reference_preserves_provenance_without_kb_intake(self) -> None:
        result = self.decide("reference", note="Find this later.")
        text = Path(result.decision["downstream_path"]).read_text(encoding="utf-8")
        for expected in (self.item_id, "https://example.com/retention", "Lab Publisher", "2026-08-09",
                         "not promoted or approved KB knowledge"):
            self.assertIn(expected, text)
        self.assertFalse((self.root / "raw").exists())

    def test_promote_queues_deterministic_unapproved_inbox_payload(self) -> None:
        result = self.decide("promote", note="Durable architecture value.")
        path = Path(result.decision["downstream_path"])
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(path, self.root / "raw/domains/ai/inbox/feeds" / f"briefing-{self.item_id}.json")
        self.assertEqual(payload["briefing_provenance"]["candidate_id"], self.item_id)
        self.assertEqual(payload["briefing_provenance"]["edition_id"], self.edition["edition_id"])
        self.assertNotIn("approved", payload)
        self.assertNotIn("review_action", payload)

    def test_item_must_be_selected_and_inputs_are_validated(self) -> None:
        other, _ = self.store.add_entry(feed("other"), entry(title="Not selected", guid="other"))
        result = apply_retention_decision(self.store, "2026-08-09", other, "promote", reviewer="erick", root=self.root)
        self.assertFalse(result.success)
        self.assertIn("selected edition", result.error)
        self.assertIn("selected edition", apply_retention_decision(
            self.store, "2026-08-09", "missing", "discard", reviewer="erick", root=self.root).error)
        self.assertIn("invalid retention", self.decide("approve").error)
        self.assertFalse(apply_retention_decision(
            self.store, "2026-08-09", self.item_id, "discard", reviewer="", root=self.root).success)

    def test_identical_actions_are_idempotent(self) -> None:
        first = self.decide("reference")
        first_text = Path(first.decision["downstream_path"]).read_text()
        second = self.decide("reference")
        self.assertTrue(second.reused)
        self.assertEqual(len(self.store.retention_history(self.edition["edition_id"], self.item_id)), 1)
        self.assertEqual(Path(second.decision["downstream_path"]).read_text(), first_text)
        promoted = self.decide("promote")
        promoted_again = self.decide("promote")
        self.assertTrue(promoted_again.reused)
        self.assertEqual(promoted.decision["downstream_path"], promoted_again.decision["downstream_path"])

    def test_decision_changes_retain_history(self) -> None:
        self.decide("discard")
        reference = self.decide("reference")
        promote = self.decide("promote")
        history = self.store.retention_history(self.edition["edition_id"], self.item_id)
        self.assertEqual([event["decision"] for event in history], ["discard", "reference", "promote"])
        self.assertEqual([event["previous_decision"] for event in history], ["", "discard", "reference"])
        self.assertTrue(Path(reference.decision["downstream_path"]).exists())
        self.assertTrue(Path(promote.decision["downstream_path"]).exists())

    def test_discard_to_promote(self) -> None:
        self.decide("discard")
        promoted = self.decide("promote")
        self.assertTrue(promoted.success)
        self.assertEqual(promoted.decision["decision"], "promote")

    def test_promotion_already_present_uses_manifest(self) -> None:
        manifest = self.root / "metadata/domains/ai/source-manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"sources": [{
            "source_id": "SRC-existing", "path": "raw/domains/ai/articles/existing.md",
            "canonical_url": "https://example.com/retention?utm_source=old",
        }]}))
        result = self.decide("promote")
        self.assertEqual(result.decision["action_status"], "already_present")
        self.assertEqual(result.decision["downstream_id"], "SRC-existing")
        self.assertFalse((self.root / "raw").exists())

    def test_queued_promotion_reconciles_resulting_source_id(self) -> None:
        queued = self.decide("promote")
        self.assertEqual(queued.decision["action_status"], "queued")
        manifest = self.root / "metadata/domains/ai/source-manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"sources": [{
            "source_id": "SRC-result", "path": "raw/domains/ai/articles/result.md",
            "canonical_url": "https://example.com/retention",
        }]}))
        reconciled = self.decide("promote")
        self.assertEqual(reconciled.decision["action_status"], "already_present")
        self.assertEqual(reconciled.decision["downstream_id"], "SRC-result")

    def test_malformed_manifest_fails_conservatively(self) -> None:
        manifest = self.root / "metadata/source-manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text("not json")
        result = self.decide("promote")
        self.assertFalse(result.success)
        self.assertEqual(result.decision["action_status"], "failed")
        self.assertFalse((self.root / "raw").exists())

    def test_failed_write_is_recorded_and_retry_succeeds(self) -> None:
        with patch("scripts.briefing.atomic_write_json", side_effect=OSError("disk full")):
            failed = self.decide("promote")
        self.assertFalse(failed.success)
        self.assertEqual(failed.decision["action_status"], "failed")
        self.assertIn("disk full", failed.decision["action_error"])
        retried = self.decide("promote")
        self.assertTrue(retried.success)
        self.assertTrue(Path(retried.decision["downstream_path"]).exists())
        self.assertEqual(len(self.store.retention_history(self.edition["edition_id"], self.item_id)), 1)

    def test_retention_marker_is_rendered_from_sqlite(self) -> None:
        self.decide("discard")
        self.assertIn("**Retention:** Discard (completed)", Path(self.edition["artifact_path"]).read_text())


class AudioGenerationTests(TempCase):
    def setUp(self) -> None:
        super().setUp()
        self.store = CandidateStore(self.db)
        candidate_id, _ = self.store.add_entry(feed(), entry(title="Audio Story", guid="audio-story"))
        self.store.transition(candidate_id, "evaluated", editorial_score=90, editorial_reasoning="Useful")
        self.edition = build_edition(self.store, "2026-08-09", self.root / "editions", target=1)
        self.audio_dir = self.root / "audio"
        self.narrative_payload = {
            "edition_date": "2026-08-09", "headline": "AI and AWS infrastructure",
            "opening": "A connected opening with [documentation](https://example.com/docs).",
            "sections": [{
                "section_title": "## API tooling", "narrative_text": "First fact, then **analysis**.",
                "supporting_item_ids": [candidate_id], "key_takeaway": "Test the CLI and GPU path.",
            }],
            "what_to_watch": ["LLM performance at https://example.com/bench"],
        }
        response = json.dumps(self.narrative_payload)
        result = generate_narrative(self.store, "2026-08-09", self.root / "narratives", generator=lambda p, m: response)
        self.assertTrue(result.success)

    @staticmethod
    def valid_tts(script_path: Path, output_path: Path, config: dict) -> dict:
        with wave.open(str(output_path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(8000)
            audio.writeframes(b"\x01\x00" * 800)
        return {"engine_version": "mock-1"}

    def test_speech_preparation_removes_markup_urls_and_appendix(self) -> None:
        narrative = {**self.narrative_payload, "source_provenance": [{"article_title": "Appendix only"}]}
        script = prepare_speech_script(narrative)
        self.assertNotIn("https://", script)
        self.assertNotIn("[documentation]", script)
        self.assertNotIn("**", script)
        self.assertNotIn("##", script)
        self.assertNotIn("Appendix only", script)
        self.assertIn("A I and A W S", script)
        self.assertIn("A P I tooling", script)
        self.assertIn("C L I and G P U", script)
        self.assertIn("L L M performance", script)
        self.assertLess(script.index("connected opening"), script.index("First fact"))
        self.assertLess(script.index("First fact"), script.index("what to watch"))

    def test_script_only_artifact_is_deterministic(self) -> None:
        result = write_speech_script(self.store, "2026-08-09", self.audio_dir)
        self.assertTrue(result.success)
        self.assertEqual(result.script_path, self.audio_dir / "2026-08-09-script.txt")
        self.assertIn("Perales Lab Daily Briefing", result.script_path.read_text())

    def test_successful_audio_records_metadata_and_provenance(self) -> None:
        result = generate_audio(self.store, "2026-08-09", self.audio_dir, tts=self.valid_tts)
        self.assertTrue(result.success)
        generation = result.generation
        self.assertEqual(Path(generation["audio_path"]), self.audio_dir / "2026-08-09-briefing.wav")
        self.assertEqual(Path(generation["script_path"]), self.audio_dir / "2026-08-09-script.txt")
        self.assertEqual(Path(generation["metadata_path"]), self.audio_dir / "2026-08-09-audio.json")
        self.assertEqual(generation["narrative_generation_id"], self.store.current_narrative(self.edition["edition_id"])["generation_id"])
        self.assertGreater(generation["duration_seconds"], 0)
        self.assertGreater(generation["audio_bytes"], 44)
        metadata = json.loads(Path(generation["metadata_path"]).read_text())
        self.assertEqual(metadata["tts_engine"], "macos-say")
        self.assertEqual(metadata["tts_engine_version"], "mock-1")

    def test_default_idempotency_and_explicit_regeneration(self) -> None:
        calls = []
        def tts(script: Path, output: Path, config: dict) -> dict:
            calls.append(script.read_text())
            return self.valid_tts(script, output, config)
        first = generate_audio(self.store, "2026-08-09", self.audio_dir, tts=tts)
        reused = generate_audio(self.store, "2026-08-09", self.audio_dir, tts=tts)
        regenerated = generate_audio(self.store, "2026-08-09", self.audio_dir, regenerate=True, tts=tts)
        self.assertTrue(reused.reused)
        self.assertEqual(len(calls), 2)
        self.assertGreater(regenerated.generation["audio_generation_id"], first.generation["audio_generation_id"])
        self.assertEqual(regenerated.generation["generation_kind"], "regeneration")

    def test_changed_narrative_marks_audio_stale_and_regenerates(self) -> None:
        first = generate_audio(self.store, "2026-08-09", self.audio_dir, tts=self.valid_tts)
        changed = {**self.narrative_payload, "headline": "Changed headline"}
        narrative = generate_narrative(self.store, "2026-08-09", self.root / "narratives", regenerate=True,
                                       generator=lambda p, m: json.dumps(changed))
        self.assertTrue(narrative.success)
        self.assertTrue(audio_status(self.store, "2026-08-09")["stale"])
        second = generate_audio(self.store, "2026-08-09", self.audio_dir, tts=self.valid_tts)
        self.assertGreater(second.generation["audio_generation_id"], first.generation["audio_generation_id"])
        self.assertFalse(audio_status(self.store, "2026-08-09")["stale"])

    def test_missing_or_failed_narrative_is_actionable(self) -> None:
        empty_store = CandidateStore(self.root / "other" / "briefing.db")
        self.assertIn("no selected edition", generate_audio(
            empty_store, "2026-08-09", self.audio_dir, tts=self.valid_tts).error)
        candidate_id, _ = empty_store.add_entry(feed(), entry(guid="failed-narrative"))
        empty_store.transition(candidate_id, "evaluated", editorial_score=90, editorial_reasoning="Useful")
        build_edition(empty_store, "2026-08-09", self.root / "other-editions", target=1)
        generate_narrative(empty_store, "2026-08-09", self.root / "other-narratives", generator=lambda p, m: "bad")
        self.assertIn("no successful validated narrative", generate_audio(
            empty_store, "2026-08-09", self.audio_dir, tts=self.valid_tts).error)

    def test_tts_failure_invalid_output_and_cleanup(self) -> None:
        failed = generate_audio(self.store, "2026-08-09", self.audio_dir,
                                tts=lambda s, o, c: (_ for _ in ()).throw(RuntimeError("TTS offline")))
        self.assertFalse(failed.success)
        self.assertIn("TTS offline", failed.error)
        invalid = generate_audio(self.store, "2026-08-09", self.audio_dir,
                                 tts=lambda s, o, c: o.write_bytes(b""))
        self.assertFalse(invalid.success)
        self.assertIn("empty", invalid.error)
        self.assertFalse(any(path.name.startswith("briefing-audio-") for path in self.audio_dir.iterdir()))

    def test_failed_regeneration_preserves_existing_audio(self) -> None:
        first = generate_audio(self.store, "2026-08-09", self.audio_dir, tts=self.valid_tts)
        path = Path(first.generation["audio_path"])
        original = path.read_bytes()
        failed = generate_audio(
            self.store, "2026-08-09", self.audio_dir, regenerate=True,
            tts=lambda s, o, c: (_ for _ in ()).throw(RuntimeError("regeneration failed")),
        )
        self.assertFalse(failed.success)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(self.store.current_audio(self.edition["edition_id"])["audio_generation_id"],
                         first.generation["audio_generation_id"])

    def test_empty_and_short_narratives(self) -> None:
        with self.store.connect() as conn:
            current = self.store.current_narrative(self.edition["edition_id"])
            payload = current["narrative"]
            payload["sections"] = []
            conn.execute("UPDATE narrative_generations SET narrative_json=? WHERE generation_id=?",
                         (json.dumps(payload), current["generation_id"]))
        empty = generate_audio(self.store, "2026-08-09", self.audio_dir, tts=self.valid_tts)
        self.assertFalse(empty.success)
        self.assertIn("no substantive sections", empty.error)
        short = {**self.narrative_payload, "opening": "Brief.", "sections": [{
            **self.narrative_payload["sections"][0], "narrative_text": "A short update.",
        }]}
        self.assertIn("A short update", prepare_speech_script(short))


if __name__ == "__main__":
    unittest.main()
