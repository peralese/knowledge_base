from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.briefing import (
    CandidateStore,
    FeedConfig,
    apply_retention_decision,
    build_edition,
    evaluate_candidates,
    generate_narrative,
    group_related_items,
    load_feed_config,
    normalize_title,
    normalize_url,
    parse_evaluation,
    poll_configured_feeds,
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
        third = dict(edition["items"][0], candidate_id="other", title="Linux kernel filesystem performance", categories_json="[]")
        groups = group_related_items(edition["items"] + [third])
        self.assertEqual(sorted(len(group["item_ids"]) for group in groups), [1, 2])

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


if __name__ == "__main__":
    unittest.main()
