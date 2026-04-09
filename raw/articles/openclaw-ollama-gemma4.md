---
title: "Openclaw Ollama Gemma4"
source_type: "article"
origin: "web"
date_ingested: "2026-04-08"
status: "raw"
topics: []
tags: []
author: ""
date_created: ""
date_published: ""
language: "en"
summary: ""
source_id: "SRC-20260408-0002"
canonical_url: ""
related_sources: []
confidence: ""
license: ""
---

# Overview

Brief description of what this source is and why it matters.

# Source Content

# How to Set Up Gemma 4 with OpenClaw Using Ollama (2026 Guide) | haimaker.ai Blog
Google released Gemma 4 on April 2, 2026, and it runs on Ollama out of the box. If you’re using OpenClaw as your coding agent, you can point it at a local Gemma 4 instance and skip the API bills for routine work.

Here’s the full setup on a Mac with Apple Silicon: install Ollama, pull Gemma 4, and wire it into OpenClaw.

What you need
-------------

*   Mac with Apple Silicon (M1/M2/M3/M4/M5) and at least 16GB unified memory
*   macOS with Homebrew installed
*   OpenClaw installed (`npm install -g openclaw`)

The 8B default model uses about 9.6GB when loaded, leaving enough headroom on a 16GB machine. If you have 24GB or more, you’ll barely notice it running.

Step 1: Install Ollama
----------------------

Install the Ollama macOS app via Homebrew:

```
brew install --cask ollama-app

```


This gives you `Ollama.app` in `/Applications/` and the `ollama` CLI at `/opt/homebrew/bin/ollama`.

Step 2: Start Ollama
--------------------

```
open -a Ollama

```


The Ollama icon appears in the menu bar. Give it a few seconds to initialize, then verify:

```
ollama list

```


Step 3: Pull Gemma 4
--------------------

```
ollama pull gemma4

```


This downloads roughly 9.6GB. Once it finishes, confirm the model is available:

```
ollama list
# NAME             ID              SIZE      MODIFIED
# gemma4:latest    ...             9.6 GB    ...

```


A quick sanity check:

```
ollama run gemma4:latest "Hello, what model are you?"

```


Verify GPU acceleration is working:

```
ollama ps
# Should show CPU/GPU split, e.g. 14%/86% CPU/GPU

```


On Apple Silicon, Ollama v0.19+ automatically uses Apple’s MLX framework for faster inference. No extra configuration needed.

Step 4: Configure OpenClaw to use Gemma 4
-----------------------------------------

The fastest way is the onboarding wizard:

```
openclaw onboard --auth-choice ollama

```


Or add Ollama manually in `~/.openclaw/openclaw.json`:

```
{
  models: {
    providers: {
      ollama: {
        baseUrl: "http://localhost:11434/v1",
        api: "openai-completions",
        models: [
          {
            id: "gemma4:latest",
            name: "Gemma 4 8B",
            reasoning: false,
            contextWindow: 131072,
            maxTokens: 8192
          }
        ]
      }
    }
  },
  agents: {
    defaults: {
      model: { primary: "ollama/gemma4:latest" },
      models: {
        "ollama/gemma4:latest": { alias: "gemma4" }
      }
    }
  }
}

```


Switch to Gemma 4 in OpenClaw:

```
/model gemma4

```


Step 5: Keep Gemma 4 loaded and ready
-------------------------------------

By default, Ollama unloads models after 5 minutes of inactivity. That means cold starts every time you come back from a coffee break.

Fix it by setting the keep-alive to indefinite:

```
launchctl setenv OLLAMA_KEEP_ALIVE "-1"

```


Then restart Ollama. To persist across reboots, add this to your `~/.zshrc`:

```
export OLLAMA_KEEP_ALIVE="-1"

```


You can also set Ollama to launch at login: click the Ollama menu bar icon and enable **Launch at Login**.

#### Auto-preload on startup

Create a launch agent that warms the model after each reboot:

```
cat << 'EOF' > ~/Library/LaunchAgents/com.ollama.preload-gemma4.plist
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ollama.preload-gemma4</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/ollama</string>
        <string>run</string>
        <string>gemma4:latest</string>
        <string></string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>StandardOutPath</key>
    <string>/tmp/ollama-preload.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ollama-preload.log</string>
</dict>
</plist>
EOF

launchctl load ~/Library/LaunchAgents/com.ollama.preload-gemma4.plist

```


This sends an empty prompt every 5 minutes, keeping Gemma 4 warm in memory.

What Gemma 4 handles well in OpenClaw
-------------------------------------

After a few sessions with Gemma 4 running locally in OpenClaw, here’s what it’s actually good at:

*   **Reading and summarizing code.** Ask it to explain what a function does and you get a solid answer. It handles navigating unfamiliar codebases reasonably well.
*   **Boilerplate and scaffolding.** Config files, CRUD operations, test templates, simple React components. It writes functional code on the first try for common patterns.
*   **File operations.** Listing files, searching for patterns, renaming variables. Mechanical work that doesn’t need deep reasoning.
*   **Quick edits.** Single-file changes, fixing typos, updating imports, adding a new field to a struct.

Where it falls short
--------------------

*   **Multi-file refactors.** Anything touching 5+ files gets unreliable. The model loses track of changes across files.
*   **Complex debugging.** If a bug spans multiple abstraction layers, Gemma 4 8B tends to suggest surface-level fixes. This is where bigger models earn their keep.
*   **Long context.** While Gemma 4 supports large context windows on paper, inference quality degrades on consumer hardware past 32K tokens. Keep your context window config realistic.

Go hybrid: local Gemma 4 + cloud models through Haimaker
--------------------------------------------------------

Most people end up using Gemma 4 for routine work and sending harder tasks to cloud models. [Haimaker](https://haimaker.ai/) makes this easy — one API key gets you access to Claude Opus, GPT-5, Gemini Pro, and others. Add it alongside Ollama in your OpenClaw config:

```
{
  models: {
    providers: {
      ollama: {
        baseUrl: "http://localhost:11434/v1",
        api: "openai-completions",
        models: [
          {
            id: "gemma4:latest",
            name: "Gemma 4 8B",
            reasoning: false,
            contextWindow: 131072,
            maxTokens: 8192
          }
        ]
      },
      haimaker: {
        baseUrl: "https://api.haimaker.ai/v1",
        apiKey: "YOUR_HAIMAKER_API_KEY",
        api: "openai-completions",
        models: [
          {
            id: "anthropic/claude-sonnet-4-6",
            name: "Claude Sonnet 4.6",
            reasoning: true,
            contextWindow: 200000,
            maxTokens: 16384
          }
        ]
      }
    }
  },
  agents: {
    defaults: {
      model: {
        primary: "ollama/gemma4:latest",
        thinking: "haimaker/anthropic/claude-sonnet-4-6"
      }
    }
  }
}

```


Gemma 4 handles file reads, simple edits, and boilerplate — probably 60-70% of a typical session. Sonnet picks up the debugging and multi-file work. Your API bill drops to a few dollars a day instead of $20+.

Switch manually when you hit something hard:

```
/model sonnet

```


Or use [Haimaker’s auto-router](https://haimaker.ai/blog/openclaw-auto-router-setup/) to detect task complexity and route automatically.

Sign up at [haimaker.ai](https://haimaker.ai/) to get your API key and browse the full [model catalog](https://haimaker.ai/models).

[GET YOUR HAIMAKER API KEY](https://app.haimaker.ai/sign-up?utm_source=blog&utm_medium=cta&utm_campaign=gemma4-openclaw)

Troubleshooting
---------------

**Model loads slowly or crashes.** You’re probably running low on memory. Check what else is using your unified memory — close browser tabs running heavy WebGL or video. On a 16GB machine, Gemma 4 8B should load fine, but competing processes can push you into swap.

**Tool calls fail.** Set `"reasoning": false` in your model config. Gemma 4 handles tool calling, but reasoning mode can cause formatting issues with OpenClaw’s expected tool-call format.

**Slow generation speed.** On Apple Silicon with Ollama v0.19+, you should see decent speeds thanks to the MLX backend. If you’re getting unexpectedly slow output, make sure you’re on the latest Ollama version — older versions don’t use MLX.

**Context window errors.** Set `contextWindow` to 131072 (128K) if you have 24GB+ memory. On 16GB, use 32768 to avoid quality degradation under memory pressure.

Useful Ollama commands
----------------------


|Command                  |Description                         |
|-------------------------|------------------------------------|
|ollama list              |List downloaded models              |
|ollama ps                |Show running models and memory usage|
|ollama run gemma4:latest |Interactive chat                    |
|ollama stop gemma4:latest|Unload model from memory            |
|ollama pull gemma4:latest|Update to latest version            |
|ollama rm gemma4:latest  |Delete model                        |


* * *

_For more local model options, see [best Ollama models for OpenClaw](https://haimaker.ai/blog/best-local-models-for-openclaw). For cloud model pricing, check [cheapest models for OpenClaw](https://haimaker.ai/blog/cheapest-models-openclaws)._

# Key Points

- 

# Notes

# Lineage

- Ingested via: scripts/ingest.py
- Manifest entry: metadata/source-manifest.json::SRC-20260408-0002
- Source path: raw/inbox/openclaw_ollama_gemma4.md
- Canonical URL: 

