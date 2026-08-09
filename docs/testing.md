# Testing

Use the repository virtual environment. Install development dependencies with:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
```

The canonical complete suite is:

```bash
make test
```

The focused Phase 1 safety suite is:

```bash
.venv/bin/python -m pytest \
  tests/test_feed_poller.py \
  tests/test_git_ops.py \
  tests/test_inbox_watcher.py \
  tests/test_pipeline_run.py \
  tests/test_runtime_safety.py \
  tests/test_topic_aggregator.py -q
```

All default tests are isolated unit or local integration tests. They use temporary roots and mocks; they do not require a running Ollama server, network access, launchd, or writes to a real Git repository. Tests that accept a `root` or `domain` must create domain-scoped fixtures under `raw|metadata|compiled|outputs/domains/<domain>/`. Patch explicit roots or pass root parameters instead of changing obsolete module constants. Restore any module global or environment variable in cleanup.

`conftest.py` sets `GIT_DISABLED=1` as a second line of defense. A test must never point queue, manifest, compiled-note, index, or report writes at the live repository. Runtime smoke checks are separate, read-only operational checks and are not part of `make test`.

There are currently no skipped, xfail, deprecated, or intentionally excluded tests.
