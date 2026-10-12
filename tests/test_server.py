import json
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

import indexer
import notes
import search
import server
import usage
from store import EMBED_DIM, connect


@pytest.fixture
def lib(tmp_path: Path, monkeypatch):
    root = tmp_path / "library"
    (root / "7 - Developer & Systems Reference").mkdir(parents=True)
    (root / "1 - Enterprise & Software").mkdir()
    monkeypatch.setattr(indexer, "embed_documents",
                        lambda texts: [[0.1] * EMBED_DIM for _ in texts])
    monkeypatch.setattr(search, "embed_query", lambda q: [0.1] * EMBED_DIM)
    return root, connect(tmp_path / "test.db"), tmp_path / ".lock"


# ------------------------------------------------------------------ notes

def test_note_creates_topic_file_then_appends(lib):
    root, _, _ = lib
    p, created = notes.append_note(7, "Git Tips", "Undo the last commit",
                                   "`git reset --soft HEAD~1`", "man git-reset, verified",
                                   root=root, today=date(2026, 10, 12))
    assert created and p.name == "Git Tips.md"
    notes.append_note(7, "git tips", "Show a file at a commit", "`git show <rev>:<path>`",
                      "verified", root=root)          # same file, case-insensitive
    text = p.read_text()
    assert text.startswith("---\ntitle: Git Tips\n---\n")
    assert text.count("\n## ") == 2
    assert "Source: man git-reset, verified\nSaved: 2026-10-12\n" in text


def test_note_rejects_bad_category_and_empty_body(lib):
    root, _, _ = lib
    with pytest.raises(ValueError):
        notes.append_note(9, "X", "h", "b", "s", root=root)
    with pytest.raises(ValueError):
        notes.append_note(7, "X", "h", "  ", "s", root=root)


def test_saved_note_is_searchable_immediately(lib):
    root, db, lock = lib
    p, _ = notes.append_note(7, "Shell Tips", "Find big files",
                             "`du -ah . | sort -rh | head` lists the largest files.",
                             "verified", root=root)
    outcome, title = indexer.index_path(p, root=root, db=db, log=lambda _: None,
                                        lock_path=lock)
    assert (outcome, title) == ("added", "Shell Tips")
    hits = search.search(db, '"largest files"')
    assert hits and hits[0]["title"] == "Shell Tips"


def test_index_path_waits_for_a_running_index(lib):
    root, db, lock = lib
    p, _ = notes.append_note(7, "T", "h", "body text", "s", root=root)
    held = indexer.lock(lock)
    threading.Timer(1.0, held.close).start()
    t0 = time.monotonic()
    outcome, _ = indexer.index_path(p, root=root, db=db, log=lambda _: None,
                                    wait=5, lock_path=lock)
    assert outcome == "added" and time.monotonic() - t0 >= 0.9


def test_index_path_gives_up_after_wait(lib):
    root, db, lock = lib
    p, _ = notes.append_note(7, "T", "h", "body text", "s", root=root)
    held = indexer.lock(lock)
    with pytest.raises(indexer.Locked):
        indexer.index_path(p, root=root, db=db, wait=0.6, lock_path=lock)
    held.close()


# ---------------------------------------------------------------- outline

def test_outline_lists_chapters_then_sections(lib):
    root, db, lock = lib
    md = root / "1 - Enterprise & Software" / "Patterns.md"
    md.write_text("---\ntitle: Patterns\n---\n\n## Saga\n\nCompensating steps.\n\n"
                  "## Outbox\n\nWrite events with the data.\n")
    indexer.index_path(md, root=root, db=db, log=lambda _: None, lock_path=lock)
    top = server.outline_text(db, "patterns")
    assert "Patterns — chapters" in top
    detail = server.outline_text(db, "Patterns", chapter="Patterns")
    assert detail.index("Saga") < detail.index("Outbox") and "section_id=" in detail
    assert "No book" in server.outline_text(db, "nonexistent")


# ------------------------------------------------------------------ usage

def test_usage_log_and_summary(tmp_path):
    path = tmp_path / "usage.db"
    usage.log_call("search", "saga", ["Building Microservices", "X"], project="~/work/a", path=path)
    usage.log_call("search", "outbox", ["Building Microservices"], project="~/work/b", path=path)
    usage.log_call("read_section", "12", ["Y"], project="~/work/a", path=path)
    lines = usage.summary(path=path)
    assert lines[0] == "Usage, last 7 days: 2 search, 1 read_section from 2 project(s)"
    assert any("~/work/a" in l for l in lines)
    assert "Building Microservices (2)" in lines[-1]


def test_usage_log_never_raises(tmp_path):
    bad = tmp_path / "file"
    bad.write_text("x")
    usage.log_call("search", "q", path=bad / "usage.db")  # parent is a file


def test_project_name_shortens_home():
    assert usage.project_name(str(Path.home() / "work" / "x")) == "~/work/x"


# ----------------------------------------------------------------- health

def test_health_silent_when_fine_and_speaks_on_problems(lib):
    _, db, _ = lib
    assert "no indexer run" in indexer.health(db)
    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    db.execute("INSERT INTO runs (started_at, finished_at, stats) VALUES (?, ?, ?)",
               (now, now, json.dumps({})))
    db.commit()
    assert indexer.health(db) is None
    db.execute("INSERT INTO failures (rel_path, size, mtime, error) VALUES ('a.epub', 1, 1, 'E')")
    db.commit()
    assert "1 file(s) failed" in indexer.health(db)
    db.execute("DELETE FROM failures")
    old = (datetime.now() - timedelta(hours=5)).isoformat(sep=" ", timespec="seconds")
    db.execute("INSERT INTO runs (started_at, finished_at, stats) VALUES (?, ?, ?)",
               (old, old, json.dumps({})))
    db.commit()
    assert "no index run since" in indexer.health(db)
