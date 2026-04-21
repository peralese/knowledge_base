# Knowledge Base — Installation Guide

## Overview

This is a local-first, LLM-powered research pipeline that runs entirely on your machine. Articles are captured through a web dashboard, ingested into structured markdown notes, synthesized by a local Ollama model, confidence-scored, and organized into a topic graph browseable in Obsidian. No cloud services, no external APIs — everything runs locally.

Four background services handle the automated stages; the dashboard at `http://localhost:7842` provides a web UI for ingestion and review.

---

## Prerequisites

Everything that must be installed **before** cloning the repository.

### Python 3.9+

```bash
# Fedora
sudo dnf install python3 python3-pip

# Ubuntu / Pop!_OS
sudo apt install python3 python3-pip python3-venv
```

Verify:
```bash
python3 --version   # must be 3.9 or newer
```

> **Fedora note:** Fedora 38+ ships Python 3.11+ by default. If your system has only `python3.X` and not `python3`, symlink it or install the `python3` package:
> ```bash
> sudo dnf install python3
> ```

### Git

```bash
# Fedora
sudo dnf install git

# Ubuntu / Pop!_OS
sudo apt install git
```

### Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

This installs the `ollama` binary and registers an `ollama.service` systemd system service that starts automatically. Verify:
```bash
ollama --version
systemctl is-active ollama    # should print "active"
```

If the service is not active, start it manually:
```bash
sudo systemctl start ollama
# or run in a terminal:
ollama serve
```

### Enable systemd user lingering (Fedora / any systemd distro)

Without this, user services stop when you log out and do not start on boot.

```bash
loginctl enable-linger $USER
```

Verify:
```bash
loginctl show-user $USER | grep Linger    # should print "Linger=yes"
```

---

## Installation

### 1. Clone the repository

```bash
git clone <repo-url> ~/knowledge-base
cd ~/knowledge-base
```

Replace `~/knowledge-base` with your preferred path. All following steps assume this path.

### 2. Create and activate the virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Add this to your shell profile (`~/.bashrc` or `~/.zshrc`) if you want the venv auto-activated:
```bash
# Optional: auto-activate in the project directory
# (or just run `source .venv/bin/activate` when working on it)
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

Packages installed:

| Package | Version |
|---|---|
| `fastapi` | ≥0.111 |
| `uvicorn[standard]` | ≥0.29 |
| `python-multipart` | ≥0.0.9 |
| `httpx` | ≥0.27 |
| `beautifulsoup4` | ≥4.12 |

`pydantic` is installed as a transitive dependency of FastAPI.

### 4. Create directory structure

```bash
python3 scripts/setup_project.py
```

This creates all required directories and template files in one step. Alternatively, use `make setup-dirs` if you have `make` installed.

Directories created by `setup_project.py`:

```
raw/inbox/           raw/inbox/browser/    raw/inbox/clipboard/
raw/inbox/feeds/     raw/inbox/pdf-drop/   raw/articles/
raw/notes/           raw/pdfs/
compiled/source_summaries/   compiled/topics/   compiled/concepts/
metadata/            outputs/reports/      outputs/answers/
templates/
```

> Directories marked as transient (`tmp/`, `raw/archive/`) are created on-demand by pipeline scripts and excluded from git.

### 5. Update service files for your machine

Three service files contain the original developer's absolute path. Update them to match your installation:

```bash
# Replace hardcoded path (run from the project root)
OLD_PATH="/home/peralese/Projects/Knowledge_Base"
NEW_PATH="$(pwd)"

sed -i "s|$OLD_PATH|$NEW_PATH|g" \
    systemd/kb-dashboard.service \
    systemd/kb-pipeline.service \
    systemd/kb-lint.service

# Replace system python3 with venv python in the same three files
sed -i "s|/usr/bin/python3|$NEW_PATH/.venv/bin/python|g" \
    systemd/kb-dashboard.service \
    systemd/kb-pipeline.service \
    systemd/kb-lint.service
```

The other two services (`kb-inbox-watcher.service`, `kb-feed-poller.service`) already use the `%h` systemd specifier and the venv python — no edits needed.

Verify the result:
```bash
grep ExecStart systemd/*.service
```

All `ExecStart` lines should reference your actual path or the `%h` specifier, and all should use `.venv/bin/python`.

---

## Ollama Setup

### Pull the required model

The pipeline uses `qwen2.5:14b` by default across all synthesis, scoring, and query steps.

```bash
ollama pull qwen2.5:14b
```

> **Download size:** approximately 9 GB. On a fast connection this takes 5–15 minutes. Storage required after download: ~9 GB.

Verify the pull succeeded:
```bash
ollama list
# Should show:   qwen2.5:14b    <size>    <date>
```

### Test the model

```bash
ollama run qwen2.5:14b "Say hello in one sentence."
```

Expected: a short response within 10–30 seconds (first run may be slower as the model is loaded into memory).

### Using a different model

All pipeline scripts accept `--model <name>`. To use a smaller model for testing:

```bash
ollama pull qwen2.5:7b
python3 scripts/synthesize.py --all --model qwen2.5:7b
```

---

## Systemd Services

Four services run the pipeline in the background. Install them as user services (no root required).

### Install and enable

```bash
# Create user service directory if it doesn't exist
mkdir -p ~/.config/systemd/user

# Copy all unit files
cp systemd/kb-inbox-watcher.service ~/.config/systemd/user/
cp systemd/kb-pipeline.service ~/.config/systemd/user/
cp systemd/kb-dashboard.service ~/.config/systemd/user/
cp systemd/kb-feed-poller.service ~/.config/systemd/user/
cp systemd/kb-lint.service ~/.config/systemd/user/
cp systemd/kb-lint.timer ~/.config/systemd/user/

# Reload systemd user daemon
systemctl --user daemon-reload

# Enable services to start on login/boot
systemctl --user enable kb-inbox-watcher.service
systemctl --user enable kb-pipeline.service
systemctl --user enable kb-dashboard.service
systemctl --user enable kb-feed-poller.service
systemctl --user enable kb-lint.timer

# Start services now
systemctl --user start kb-inbox-watcher.service
systemctl --user start kb-pipeline.service
systemctl --user start kb-dashboard.service
systemctl --user start kb-feed-poller.service
```

### Verify each service

```bash
systemctl --user status kb-inbox-watcher.service
systemctl --user status kb-pipeline.service
systemctl --user status kb-dashboard.service
systemctl --user status kb-feed-poller.service
```

Each should show `Active: active (running)`. If a service is `failed` or `inactive`, check the logs:

```bash
journalctl --user -u kb-inbox-watcher.service -n 50
journalctl --user -u kb-pipeline.service -n 50
journalctl --user -u kb-dashboard.service -n 50
journalctl --user -u kb-feed-poller.service -n 50
```

### Service descriptions

| Service | Role | Restart behavior |
|---|---|---|
| `kb-inbox-watcher` | Watches `raw/inbox/` and runs ingest → validate → queue | Always, 10s |
| `kb-pipeline` | Runs `pipeline_run.py --watch` — synthesize → score → aggregate → index | Always, 10s |
| `kb-dashboard` | FastAPI web UI on `127.0.0.1:7842` | Always, 5s |
| `kb-feed-poller` | Polls RSS/Atom feeds from `metadata/feeds.json` hourly | Always, 30s |
| `kb-lint.timer` | Runs `lint.py --llm --report` weekly | Timer |

---

## First Run Verification

Work through this checklist top to bottom after completing the installation steps above.

```
[ ] 1. Dashboard responds
        curl -s http://localhost:7842 | head -5
        (or open http://localhost:7842 in a browser)

[ ] 2. Topic registry loaded
        python3 scripts/topic_aggregator.py --list
        (should list 8 pre-loaded topics — no error)

[ ] 3. Ingest a test article via dashboard
        Open http://localhost:7842 → paste any article URL → click Ingest
        Confirm "Queued" response appears

[ ] 4. Inbox file appeared
        ls raw/inbox/browser/
        (a .md or .json file should appear within 30 seconds)

[ ] 5. Article moved to raw/articles/
        ls raw/articles/
        (the inbox watcher should pick it up; allow 30-60 seconds)

[ ] 6. Item in review queue
        python3 scripts/review.py list
        (the article should appear with status "pending_review")

[ ] 7. Wait for synthesis (or trigger manually)
        python3 scripts/synthesize.py --all
        (or wait for kb-pipeline.service to process it — up to 2 minutes)

[ ] 8. Compiled note created
        ls compiled/source_summaries/
        (a *-synthesis.md file should exist)

[ ] 9. Query the knowledge base
        python3 scripts/query.py --question "what did I just add?"
        (response should stream to terminal within 30 seconds)

[ ] 10. Open in Obsidian
         Point Obsidian vault at the compiled/ directory
         Confirm compiled/index.md is visible

[ ] 11. Run lint
         python3 scripts/lint.py
         (should complete without crash; may report issues on first run)
```

---

## Daily Use

```
Dashboard:        http://localhost:7842
Add article:      Dashboard → Ingest tab → paste URL or upload file
Review queue:     Dashboard → Review Queue tab
                  (or: python3 scripts/review.py list)
Approve items:    python3 scripts/review.py approve SRC-xxxx
                  python3 scripts/review.py approve --all-high-confidence
Query:            python3 scripts/query.py --question "your question"
Search:           python3 scripts/search.py "keyword"
Pipeline log:     python3 scripts/log.py
                  python3 scripts/log.py --type synth --since "2026-04-01"
Lint:             python3 scripts/lint.py   (runs automatically weekly)
Git history:      git log --oneline
```

---

## Troubleshooting

### Service fails to start — wrong path in unit file

**Symptom:** `journalctl --user -u kb-pipeline.service` shows `No such file or directory`

**Fix:** Re-run the sed commands from the Installation section. Verify with:
```bash
grep -E "ExecStart|WorkingDirectory" systemd/kb-pipeline.service
```
Both lines must reference your actual project path.

After editing:
```bash
cp systemd/kb-pipeline.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user restart kb-pipeline.service
```

### Service fails — `ModuleNotFoundError`

**Symptom:** Service starts but immediately exits; log shows `ModuleNotFoundError: No module named 'fastapi'`

**Cause:** Service is using system python3 instead of the venv.

**Fix:** Verify the `ExecStart` line uses `.venv/bin/python`, not `/usr/bin/python3`:
```bash
grep ExecStart ~/.config/systemd/user/kb-dashboard.service
# Should show: .../knowledge-base/.venv/bin/python .../dashboard.py
```
If not, re-run the sed commands and re-copy the service files.

### Ollama not found / connection refused

**Symptom:** Synthesis produces scaffold fallback; error: `ConnectionError: [Errno 111] Connection refused`

**Check:**
```bash
curl http://localhost:11434/api/tags
systemctl is-active ollama
```

**Fix:**
```bash
sudo systemctl start ollama
# or in a terminal:
ollama serve
```

### Model not found

**Symptom:** `ValueError: model 'qwen2.5:14b' is not available`

**Check:**
```bash
ollama list
```

**Fix:**
```bash
ollama pull qwen2.5:14b
```

### Synthesis falls back to scaffold output

**Cause:** Ollama is running but the model is not loaded in memory (takes a few seconds on first use).

**Check:**
```bash
ollama ps    # shows currently loaded models
```

**Fix:** Run a test prompt to pre-load:
```bash
ollama run qwen2.5:14b "hello"
```
Then retry synthesis.

### Dashboard 500 error on startup

**Likely causes:**
1. Missing `compiled/` directory — run `python3 scripts/setup_project.py`
2. Wrong `WorkingDirectory` — service must run from the project root
3. Missing Python package — activate venv and `pip install -r requirements.txt`

**Debug:**
```bash
journalctl --user -u kb-dashboard.service -n 30
cd ~/knowledge-base
source .venv/bin/activate
python3 dashboard.py    # run manually to see the full traceback
```

### Inbox watcher not picking up files

**Check:**
```bash
systemctl --user status kb-inbox-watcher.service
ls raw/inbox/browser/
journalctl --user -u kb-inbox-watcher.service -n 20
```

**Common fix:** Service not running. Restart it:
```bash
systemctl --user restart kb-inbox-watcher.service
```

### Port 7842 already in use

**Symptom:** Dashboard fails with `address already in use`

**Option 1:** Kill the existing process:
```bash
lsof -ti:7842 | xargs kill -9
```

**Option 2:** Run on a different port:
```bash
# Edit the service file:
nano ~/.config/systemd/user/kb-dashboard.service
# Change:  ExecStart=... dashboard.py
# To:      ExecStart=... dashboard.py --port 7843

systemctl --user daemon-reload
systemctl --user restart kb-dashboard.service
```

### User services not starting after reboot (Fedora)

**Cause:** User lingering not enabled — systemd destroys the user session on logout.

**Fix:**
```bash
loginctl enable-linger $USER
```

Verify: `loginctl show-user $USER | grep Linger` should print `Linger=yes`.

### SELinux blocking file writes (Fedora)

If the project is installed in a standard home directory path (`~/knowledge-base`), SELinux should allow all writes without any policy changes.

If you install to a non-standard path (e.g., `/opt/knowledge-base`) and see `Permission denied` errors despite correct POSIX permissions, check SELinux:
```bash
ausearch -m avc -ts recent | grep knowledge-base
```

Quick workaround (development only):
```bash
sudo setenforce 0
```

Permanent fix for a custom path:
```bash
sudo semanage fcontext -a -t user_home_t "/opt/knowledge-base(/.*)?"
sudo restorecon -Rv /opt/knowledge-base
```

### Firewall blocking dashboard (Fedora)

The dashboard binds to `127.0.0.1` (localhost) by default, so `firewalld` does **not** block it for local access. If you change the host to `0.0.0.0` (network-accessible):

```bash
# Allow port through firewall
sudo firewall-cmd --add-port=7842/tcp --permanent
sudo firewall-cmd --reload
```

---

## Uninstall

```bash
# Stop and disable services
systemctl --user stop kb-inbox-watcher kb-pipeline kb-dashboard kb-feed-poller
systemctl --user disable kb-inbox-watcher kb-pipeline kb-dashboard kb-feed-poller kb-lint.timer

# Remove service files
rm -f ~/.config/systemd/user/kb-*.service
rm -f ~/.config/systemd/user/kb-lint.timer
systemctl --user daemon-reload

# Remove the project directory (includes all notes and compiled wiki)
rm -rf ~/knowledge-base

# Optionally remove the Ollama model (~9 GB)
ollama rm qwen2.5:14b

# Optionally disable user lingering (if you enabled it only for this project)
loginctl disable-linger $USER
```

---

## Appendix: Manual Pipeline Commands

These commands work without the background services — useful for testing or one-off runs:

```bash
source .venv/bin/activate

# Process a single article through the full pipeline
python3 scripts/pipeline_run.py SRC-20260418-0001

# Process all pending articles
python3 scripts/pipeline_run.py --all

# Synthesize without auto-commit (useful during testing)
python3 scripts/synthesize.py --all --no-commit

# View git-backed operation log
python3 scripts/log.py --since "2026-04-01"

# Run confidence scoring manually
python3 scripts/score_synthesis.py --all

# Rebuild the wiki index
python3 scripts/index_notes.py
```
