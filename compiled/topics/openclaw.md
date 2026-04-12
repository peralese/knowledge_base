---
title: "OpenClaw"
created: "2026-04-08"
sources: 
  - "openclaw-ollama-gemma4.md"
tags: 
  - "topic"
  - "Ollama"
  - "Local AI Model Setup"
  - "OpenClaw Agent Configuration"
  - "openclaw-ollama-gemma4"
status: "draft"
note_type: "topic"
compiled_from: 
  - "openclaw-ollama-gemma4"
date_compiled: "2026-04-08"
topics: 
  - "Ollama"
  - "Local AI Model Setup"
  - "OpenClaw Agent Configuration"
confidence: "medium"
generation_method: "ollama_local"
---

# Summary

This note provides a detailed guide on setting up Gemma 4, an AI model from Google, to work seamlessly with OpenClaw coding agent using the Ollama platform. The setup instructions are tailored for Mac users with Apple Silicon processors and at least 16GB of unified memory. Key steps include installing Ollama via Homebrew, pulling the Gemma 4 model, configuring OpenClaw to use Gemma 4, and maintaining the model's availability by setting a keep-alive flag. The guide also discusses performance optimizations for local usage, such as auto-preloading on startup.

# Key Insights

- **Setup Requirements**: Mac with Apple Silicon (M1/M2/M3/M4/M5) and at least 16GB unified memory.
- **Installation Steps**:
    - Install Ollama via Homebrew (`brew install --cask ollama-app`).
    - Pull Gemma 4 model using `ollama pull gemma4`.
    - Configure OpenClaw to use the installed Gemma 4 model.
- **Optimizations**: Set `OLLAMA_KEEP_ALIVE=-1` in `.zshrc` for persistent model loading, and create a launch agent for auto-preloading on startup.

# Related Concepts

- Ollama
- Local AI Model Setup
- OpenClaw Agent Configuration

# Source Notes

- [[openclaw-ollama-gemma4]]

# Source Highlights

## [[openclaw-ollama-gemma4]]
- **Title**: How to Set Up Gemma 4 with OpenClaw Using Ollama (2026 Guide) | haimaker.ai Blog
- **Source Type**: article
- **Origin**: web
- **Summary**: This source provides detailed instructions on setting up the latest version of Google's AI model, Gemma 4, for local use in OpenClaw coding agent with Ollama.
- **Key excerpt**:
    ```
    Install the Ollama macOS app via Homebrew: brew install --cask ollama-app
    Pull Gemma 4 using `ollama pull gemma4`.
    Configure OpenClaw to use Gemma 4 by adding settings in `~/.openclaw/openclaw.json`.
    ```

# Lineage

This note was derived from:
- [[openclaw-ollama-gemma4]]
