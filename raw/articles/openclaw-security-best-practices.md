---
title: "Openclaw Security Best Practices"
source_type: "article"
origin: "web"
date_ingested: "2026-04-05"
status: "raw"
topics: []
tags: []
author: ""
date_created: ""
date_published: ""
language: "en"
summary: ""
source_id: "SRC-20260405-0005"
canonical_url: ""
related_sources: []
confidence: ""
license: ""
---

# Overview

Brief description of what this source is and why it matters.

# Source Content

# How to Harden OpenClaw: Security Best Practices for 2026 | OpenClaw Blog
In this article

1.  [1\. Run OpenClaw in Docker �� Always](#1-run-openclaw-in-docker-always)
2.  [2\. Lock Down Permissions with SOUL.md](#2-lock-down-permissions-with-soul-md)
3.  [3\. API Key Security](#3-api-key-security)
4.  [4\. Network Hardening](#4-network-hardening)
5.  [5\. Skill Vetting](#5-skill-vetting)
6.  [6\. Emergency Controls](#6-emergency-controls)
7.  [7\. Logging and Auditing](#7-logging-and-auditing)
8.  [Putting It All Together](#putting-it-all-together)

Your AI agent can read your files, browse the web, send messages, and call APIs on your behalf. That's the whole point — but it also means a misconfigured setup is a real risk.

This guide covers the concrete steps to harden OpenClaw so it does exactly what you want and nothing more. No vague advice. Every section has something you can copy-paste or configure today.

Key Takeaways

*   **Docker isolation** keeps OpenClaw sandboxed — don't skip it even on a personal machine
*   **SOUL.md permission rules** are your most powerful security tool and take 5 minutes to set up
*   **API key hygiene** (rotation, scoping, monitoring) prevents the most common real-world breach vector
*   **Network hardening** stops your agent from reaching services it shouldn't

1\. Run OpenClaw in Docker — Always
-----------------------------------

Even if you're the only user on your machine, Docker isolation is non-negotiable for a serious setup. Here's why: without it, OpenClaw runs with your full user permissions. Every file you can read, it can read. Every command you can run, it can run.

Docker creates a boundary. OpenClaw inside the container can only see what you explicitly mount.

**Minimal secure Docker setup:**

```
services:
  openclaw:
    image: openclaw/desktop:latest
    restart: unless-stopped
    volumes:
      - ./workspace:/app/workspace    # Only this folder is visible
      - ./config:/app/config          # Config files
    environment:
      - OPENCLAW_ENV=production
    ports:
      - "127.0.0.1:3000:3000"        # Localhost only — not 0.0.0.0
    read_only: true                    # Filesystem is read-only by default
    tmpfs:
      - /tmp                           # Writable temp directory
    security_opt:
      - no-new-privileges:true         # Prevent privilege escalation

```


The critical details:

*   **`127.0.0.1:3000:3000`** binds to localhost only. Using `0.0.0.0` exposes your agent to the entire network.
*   **`read_only: true`** makes the container filesystem immutable. OpenClaw can only write to explicitly mounted volumes and `/tmp`.
*   **`no-new-privileges`** prevents any process inside the container from gaining elevated permissions.

Don't mount your home directory. Don't mount `/`. Mount the smallest directory that contains what OpenClaw actually needs to work with.

2\. Lock Down Permissions with SOUL.md
--------------------------------------

SOUL.md is where you define what your agent is and isn't allowed to do. Most people write personality instructions here. The security-conscious also write permission boundaries.

**Add this block to your SOUL.md:**

```
# Security Rules

## Hard Boundaries
- NEVER execute shell commands without my explicit approval
- NEVER send emails, messages, or any outbound communication without confirmation
- NEVER modify or delete files outside the /workspace directory
- NEVER access or read .env files, credentials, or API keys
- NEVER install packages, extensions, or dependencies without approval

## Confirmation Required
Before taking any of these actions, describe exactly what you plan to do and wait for my "yes":
- Sending any HTTP request to an external service
- Writing or modifying any file
- Running any shell command
- Accessing any API endpoint

## Emergency Stop
If I say "STOP", "HALT", or "KILL" — immediately cease all actions. Do not finish the current task. Do not clean up. Just stop.

```


This isn't just a suggestion to the AI — it's a directive that shapes every response. Test it after adding: ask OpenClaw to delete a file and verify it asks for confirmation first.

3\. API Key Security
--------------------

Your API keys are the most valuable thing in your OpenClaw setup. A leaked Anthropic or OpenAI key can rack up thousands of dollars in charges before you notice.

**The basics:**

*   Store keys in `.env` files, never in SOUL.md, config files, or skill files
*   Add `.env` to your `.gitignore` (it should already be there — check anyway)
*   Never paste keys into chat with OpenClaw — they'll end up in conversation memory

**Scope your keys tightly.** Most API providers let you create restricted keys:


|Provider |Scoping Options                  |
|---------|---------------------------------|
|Anthropic|Usage limits (monthly cap)       |
|OpenAI   |Project-scoped keys, usage limits|
|Google   |API restrictions, IP allowlists  |


**Set a spending cap.** Every provider supports this. Set it to something you'd be comfortable losing — $20/month is a reasonable starting point for personal use.

**Rotate quarterly.** Mark it on your calendar. The process:

1.  Generate a new key in your provider's dashboard
2.  Update `.env` with the new key
3.  Restart OpenClaw
4.  Run a test task to verify the new key works
5.  Revoke the old key

That last step matters. A key that "should be unused" but isn't revoked is still a live credential.

4\. Network Hardening
---------------------

By default, OpenClaw can reach any URL on the internet. That's useful for web research but unnecessarily broad for most setups.

**If you're using Docker, restrict outbound access:**

```
services:
  openclaw:
    networks:
      - restricted
    dns:
      - 1.1.1.1

networks:
  restricted:
    driver: bridge
    internal: false  # Set to true to block ALL outbound traffic

```


For most users, the practical approach is a blocklist rather than an allowlist. Block known-dangerous destinations:

```
# In SOUL.md
## Network Rules
- NEVER make requests to IP addresses (only domain names)
- NEVER access localhost, 127.0.0.1, or any 192.168.x.x / 10.x.x.x address
- NEVER access file:// URLs
- NEVER download or execute scripts from the internet

```


This prevents Server-Side Request Forgery (SSRF) attacks where a malicious skill could use OpenClaw to probe your local network.

5\. Skill Vetting
-----------------

Skills are the biggest attack surface in OpenClaw. A skill is just code that your agent executes. Before installing any community skill:

**Manual review checklist:**

1.  Read the skill's source code — it's usually a single markdown or YAML file
2.  Check for any `curl`, `wget`, `fetch`, or HTTP request commands
3.  Look for file operations outside `/workspace`
4.  Search for any references to environment variables or API keys
5.  Check the author's reputation in the community

**Use the Skill Vetter skill** to automate this. It scans a skill file and flags suspicious patterns:

```
Vet this skill before I install it: [paste skill URL or content]

```


The Skill Vetter looks for data exfiltration patterns, excessive permission requests, obfuscated code, and known malicious signatures. It's not perfect, but it catches the obvious stuff.

**Never install a skill that:**

*   Requests access to your `.env` or credential files
*   Makes HTTP requests to unfamiliar domains
*   Asks you to disable confirmation rules in SOUL.md
*   Contains minified, obfuscated, or base64-encoded content

6\. Emergency Controls
----------------------

Things go wrong. A skill malfunctions. A prompt injection causes unexpected behavior. An automation loop burns through your API budget. You need a way to stop everything immediately.

**Set up your kill switches before you need them:**

**Docker stop** — the nuclear option:

```
docker stop openclaw

```


This immediately halts the container. No cleanup, no graceful shutdown. Use it when something is actively going wrong.

**API key disable** — stops all AI inference:

Bookmark your API provider's key management page. In an emergency, you can revoke the key in under 30 seconds. OpenClaw will still run but won't be able to make any AI calls.

**SOUL.md emergency brake** — add the "STOP" rule from Section 2. If you can still interact with OpenClaw through the dashboard, typing "STOP" should halt all activity.

**Spending alerts** — set up notifications with your API provider at 50%, 80%, and 100% of your monthly budget. Anthropic and OpenAI both support email alerts.

7\. Logging and Auditing
------------------------

You can't secure what you can't observe. OpenClaw logs every action it takes, but you need to actually check those logs.

**What to monitor:**

*   **API usage** — sudden spikes could indicate a runaway automation or compromised key
*   **File operations** — unexpected writes outside your workspace directory
*   **Network requests** — connections to domains you don't recognize
*   **Skill installations** — any new skill added without your knowledge

**Set up a daily check.** It takes 60 seconds:

1.  Open your API provider's usage dashboard — is spending normal?
2.  Check OpenClaw's activity log — anything you don't recognize?
3.  Verify your running skills match what you expect

For advanced users, pipe OpenClaw's Docker logs to a monitoring service:

```
docker logs openclaw --since 24h | grep -E "(ERROR|WARN|skill|install)"

```


Putting It All Together
-----------------------

Here's the minimum hardening checklist. If you do nothing else, do these five things:

1.  **Run in Docker** with localhost-only port binding and read-only filesystem
2.  **Add security rules to SOUL.md** — especially the confirmation requirement
3.  **Set API spending caps** at your provider
4.  **Vet every skill** before installing it
5.  **Bookmark your API key page** so you can revoke in an emergency

Security isn't a one-time task. Review your setup monthly. Rotate keys quarterly. Read the OpenClaw changelog for security-relevant updates. The 20 minutes you invest in hardening today saves you from the one bad day you'd really rather not have.

# Key Points

- 

# Notes

# Lineage

- Ingested via: scripts/ingest.py
- Manifest entry: metadata/source-manifest.json::SRC-20260405-0005
- Source path: raw/inbox/openclaw-security-best-practices.md
- Canonical URL: 

