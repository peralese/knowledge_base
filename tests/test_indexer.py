import os
from pathlib import Path

import pytest

import indexer
from store import EMBED_DIM, connect


@pytest.fixture
def lib(tmp_path: Path, monkeypatch):
    """A tiny library folder, a throwaway index, and no Ollama."""
    root = tmp_path / "library"
    (root / "7 - Dev").mkdir(parents=True)
    monkeypatch.setattr(indexer, "embed_documents",
                        lambda texts: [[0.1] * EMBED_DIM for _ in texts])
    db = connect(tmp_path / "test.db")

    def add(name: str, body: str = "Some text about git.") -> Path:
        p = root / "7 - Dev" / name
        p.write_text(f"---\ntitle: {p.stem}\n---\n\n## Heading\n\n{body}\n")
        return p

    def run(**kw):
        return indexer.run(root, log=lambda _: None, db=db, **kw)

    return root, db, add, run


def _count_calls(monkeypatch, name):
    calls = []
    real = getattr(indexer, name)
    monkeypatch.setattr(indexer, name, lambda *a, **k: calls.append(a) or real(*a, **k))
    return calls


def test_unchanged_files_are_not_rehashed(lib, monkeypatch):
    root, db, add, run = lib
    add("a.md"), add("b.md")
    assert run()["added"] == 2
    hashes = _count_calls(monkeypatch, "_sha256")
    stats = run()
    assert stats["unchanged"] == 2 and hashes == []


def test_missing_size_mtime_is_backfilled_without_reindexing(lib, monkeypatch):
    root, db, add, run = lib
    add("a.md")
    run()
    db.execute("UPDATE sources SET size = NULL, mtime = NULL")
    db.commit()
    parses = _count_calls(monkeypatch, "parse")
    assert run()["unchanged"] == 1 and parses == []
    assert db.execute("SELECT size FROM sources").fetchone()[0] is not None


def test_changed_file_is_reindexed(lib):
    root, db, add, run = lib
    p = add("a.md")
    run()
    p.write_text(p.read_text() + "\nMore text about rebase.\n")
    assert run()["updated"] == 1
    assert db.execute("SELECT count(*) FROM sources").fetchone()[0] == 1


def test_a_few_gone_files_are_removed(lib):
    root, db, add, run = lib
    a = add("a.md")
    add("b.md")
    run()
    a.unlink()
    assert run()["removed"] == 1
    assert db.execute("SELECT count(*) FROM sources").fetchone()[0] == 1


def test_mass_removal_is_held_back(lib):
    root, db, add, run = lib
    files = [add(f"f{i}.md") for i in range(indexer.MAX_REMOVALS + 2)]
    run()
    for f in files:          # looks like a half-mounted share
        f.unlink()
    stats = run()
    assert stats["removed"] == 0 and stats["held"] == len(files)
    assert stats["_note"]
    assert db.execute("SELECT count(*) FROM sources").fetchone()[0] == len(files)
    assert run(allow_removals=True)["removed"] == len(files)


def test_failed_file_is_recorded_skipped_then_retried_on_change(lib, monkeypatch):
    root, db, add, run = lib
    bad = add("bad.md")
    add("good.md")
    real_parse = indexer.parse

    def parse(path):
        if path.name == "bad.md":
            raise ValueError("broken EPUB")
        return real_parse(path)

    monkeypatch.setattr(indexer, "parse", parse)
    stats = run()
    assert stats["added"] == 1 and stats["failed"] == 1 and stats["_failed"] == ["bad.md"]
    assert db.execute("SELECT error FROM failures").fetchone()[0] == "ValueError: broken EPUB"

    stats = run()                       # same file: not retried, not re-reported
    assert stats["failed"] == 1 and stats["_failed"] == []

    monkeypatch.setattr(indexer, "parse", real_parse)
    os.utime(bad, (1, 1))               # file changed on disk -> retried
    assert run()["added"] == 1
    assert db.execute("SELECT count(*) FROM failures").fetchone()[0] == 0


def test_runs_are_recorded_for_status(lib):
    root, db, add, run = lib
    add("a.md")
    run()
    text = indexer.status(db)
    assert "1 articles" in text and "'added': 1" in text


def test_second_lock_is_refused(tmp_path):
    held = indexer.lock(tmp_path / ".lock")
    with pytest.raises(indexer.Locked):
        indexer.lock(tmp_path / ".lock")
    held.close()
    indexer.lock(tmp_path / ".lock").close()


def test_summary_only_when_something_happened():
    quiet = {"removed": 0, "held": 0, "_changed": [], "_failed": [], "_note": None}
    assert indexer.summary(quiet) is None
    busy = dict(quiet, _changed=["A", "B", "C", "D"], _failed=["x.epub"])
    assert indexer.summary(busy) == "Indexed 4: A, B, C +1 more; FAILED: x.epub"
