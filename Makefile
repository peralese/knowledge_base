.PHONY: install setup-dirs setup-services patch-services start stop status logs verify clean

INSTALL_DIR := $(shell pwd)
PYTHON      := $(INSTALL_DIR)/.venv/bin/python
SYSTEMD_DIR := $(HOME)/.config/systemd/user

# ---------------------------------------------------------------------------
# install — full setup from a clean clone
# ---------------------------------------------------------------------------

install:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	$(MAKE) setup-dirs
	@echo ""
	@echo "Installation complete."
	@echo "Next steps:"
	@echo "  1. Pull the Ollama model:  ollama pull qwen2.5:14b"
	@echo "  2. Set up services:        make setup-services"

# ---------------------------------------------------------------------------
# setup-dirs — create all required directories
# ---------------------------------------------------------------------------

setup-dirs:
	mkdir -p raw/inbox/browser raw/inbox/clipboard raw/inbox/feeds raw/inbox/pdf-drop
	mkdir -p raw/articles raw/notes raw/pdfs raw/archive
	mkdir -p compiled/source_summaries compiled/topics compiled/concepts
	mkdir -p metadata/prompts
	mkdir -p outputs/reports outputs/answers
	@echo "Directories created."

# ---------------------------------------------------------------------------
# patch-services — rewrite hardcoded paths/python in unit files
#   Applies substitutions without modifying the git-tracked source files;
#   writes directly to ~/.config/systemd/user/.
# ---------------------------------------------------------------------------

patch-services:
	mkdir -p $(SYSTEMD_DIR)
	@for f in systemd/*.service systemd/*.timer; do \
		dest=$(SYSTEMD_DIR)/$$(basename $$f); \
		sed \
			-e "s|/home/peralese/Projects/Knowledge_Base|$(INSTALL_DIR)|g" \
			-e "s|/usr/bin/python3|$(PYTHON)|g" \
			"$$f" > "$$dest"; \
		echo "  installed: $$dest"; \
	done

# ---------------------------------------------------------------------------
# setup-services — patch, install, enable, and start all services
# ---------------------------------------------------------------------------

setup-services: patch-services
	systemctl --user daemon-reload
	systemctl --user enable kb-inbox-watcher.service
	systemctl --user enable kb-pipeline.service
	systemctl --user enable kb-dashboard.service
	systemctl --user enable kb-feed-poller.service
	systemctl --user enable kb-lint.timer
	$(MAKE) start
	@echo ""
	@echo "Services enabled and started. Dashboard: http://localhost:7842"

# ---------------------------------------------------------------------------
# start / stop / status / logs
# ---------------------------------------------------------------------------

start:
	systemctl --user start kb-inbox-watcher.service
	systemctl --user start kb-pipeline.service
	systemctl --user start kb-dashboard.service
	systemctl --user start kb-feed-poller.service

stop:
	systemctl --user stop kb-inbox-watcher.service
	systemctl --user stop kb-pipeline.service
	systemctl --user stop kb-dashboard.service
	systemctl --user stop kb-feed-poller.service

status:
	@echo "=== kb-inbox-watcher ==="
	@systemctl --user status kb-inbox-watcher.service --no-pager -l || true
	@echo ""
	@echo "=== kb-pipeline ==="
	@systemctl --user status kb-pipeline.service --no-pager -l || true
	@echo ""
	@echo "=== kb-dashboard ==="
	@systemctl --user status kb-dashboard.service --no-pager -l || true
	@echo ""
	@echo "=== kb-feed-poller ==="
	@systemctl --user status kb-feed-poller.service --no-pager -l || true

logs:
	journalctl --user \
		-u kb-inbox-watcher.service \
		-u kb-pipeline.service \
		-u kb-dashboard.service \
		-u kb-feed-poller.service \
		-f --output cat

# ---------------------------------------------------------------------------
# verify — quick health check
# ---------------------------------------------------------------------------

verify:
	@echo "--- Services ---"
	@systemctl --user is-active kb-inbox-watcher.service && echo "  inbox-watcher: OK" || echo "  inbox-watcher: NOT RUNNING"
	@systemctl --user is-active kb-pipeline.service && echo "  pipeline:       OK" || echo "  pipeline:       NOT RUNNING"
	@systemctl --user is-active kb-dashboard.service && echo "  dashboard:      OK" || echo "  dashboard:      NOT RUNNING"
	@systemctl --user is-active kb-feed-poller.service && echo "  feed-poller:    OK" || echo "  feed-poller:    NOT RUNNING"
	@echo ""
	@echo "--- Dashboard ---"
	@curl -sf http://localhost:7842 > /dev/null && echo "  http://localhost:7842  OK" || echo "  http://localhost:7842  NOT RESPONDING"
	@echo ""
	@echo "--- Ollama ---"
	@ollama list 2>&1 | head -10 || echo "  ollama not available"

# ---------------------------------------------------------------------------
# test — run the test suite
# ---------------------------------------------------------------------------

test:
	$(PYTHON) -m pytest tests/ -q

# ---------------------------------------------------------------------------
# clean — remove Python bytecode and caches
# ---------------------------------------------------------------------------

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name "*.pyo" -delete 2>/dev/null || true
	find . -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete."
