---
title: "Auto Research"
note_type: "source_summary"
compiled_from: 
  - "auto-research"
date_compiled: "2026-04-05"
topics: 
  - "Autonomous agents"
  - "Neural architecture search (NAS)"
  - "Hyperparameter optimization"
  - "Self-improving systems"
  - "Human-in-the-loop AI"
tags: 
  - "source_summary"
  - "Autonomous agents"
  - "Neural architecture search (NAS)"
  - "Hyperparameter optimization"
  - "Self-improving systems"
  - "Human-in-the-loop AI"
  - "auto-research"
confidence: "medium"
generation_method: "prompt_pack"
---

# Summary

“Auto Research” describes an experimental framework for autonomous AI-driven research, where agents iteratively modify and train machine learning models without direct human intervention. Built around a minimal single-GPU setup, the system allows an AI agent to run repeated short training cycles, evaluate results, and refine the model over time. The approach shifts the role of the human from directly editing code to designing high-level instructions (`program.md`) that guide the agent’s research process, enabling continuous experimentation and optimization. :contentReference[oaicite:0]{index=0}

# Key Insights

- The core idea is autonomous experimentation: an AI agent modifies training code, runs short experiments (~5 minutes), evaluates performance, and iterates continuously.
- Human involvement is abstracted to writing high-level instructions (`program.md`), rather than directly editing model or training code.
- The system enforces a fixed time budget per experiment, enabling consistent comparison across different model configurations.
- A minimal architecture (single GPU, few files) keeps the research loop simple, inspectable, and reproducible.
- The optimization metric (validation bits per byte, val_bpb) allows fair comparison across architectural changes and vocabularies.

# Related Concepts

- Autonomous agents  
- Neural architecture search (NAS)  
- Hyperparameter optimization  
- Self-improving systems  
- Human-in-the-loop AI  

# Source Notes

- [[auto-research]]

# Source Highlights

## [[auto-research]]
- Title: Auto Research
- Source Type: article
- Origin: web
- Summary: 
- Key excerpt:
  - "give an AI agent a small but real LLM training setup and let it experiment autonomously overnight"
  - "It modifies the code, trains for 5 minutes, checks if the result improved, keeps or discards, and repeats"
  - "you are programming the `program.md` Markdown files that provide context to the AI agents"
  - "training runs for a fixed 5-minute time budget"
  - "the agent only touches `train.py`"

# Lineage

This note was derived from:
- [[auto-research]]
