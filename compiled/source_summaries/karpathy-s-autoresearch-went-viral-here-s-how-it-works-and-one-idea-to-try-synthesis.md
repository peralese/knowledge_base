---
title: "Karpathy’S Autoresearch Went Viral. Here’S How It Works And One Idea To Try Synthesis"
note_type: "source_summary"
compiled_from: 
  - "karpathy-s-autoresearch-went-viral-here-s-how-it-works-and-one-idea-to-try"
date_compiled: "2026-04-22"
date_updated: "2026-04-22"
topics: 
  - "AutoML"
  - "LLM-driven experimentation"
  - "Git-based version control in automated research settings"
tags: 
  - "source_summary"
  - "AutoML"
  - "LLM-driven experimentation"
  - "Git-based version control in automated research settings"
  - "karpathy-s-autoresearch-went-viral-here-s-how-it-works-and-one-idea-to-try"
confidence: "medium"
confidence_score: 0.75
generation_method: "ollama_local"
approved: false
---

# Summary

Karpathy's autoresearch project involves automating the process of running experiments and iterating on models, which typically requires substantial human effort. The system uses an LLM to edit training code directly in a loop, evaluating changes based on predefined metrics. It consists of three main components: `prepare.py`, which sets up data preparation and evaluation logic; `train.py`, where modifications are made by the agent during experiments; and `program.md`, containing natural-language instructions for the agent. The system operates under strict constraints to ensure focused exploration and metric improvement, leading to iterative enhancements in model performance over time.

# Key Insights

- **Autoresearch Concept**: An LLM-driven loop that iteratively modifies training code to optimize a specific metric.
- **System Structure**:
  - `prepare.py`: Fixed components of the experiment.
  - `train.py`: Model implementation and training loop, modifiable by the agent.
  - `program.md`: Natural-language instructions guiding the research process.
- **Optimization Process**: Strict time budgets for experiments to ensure comparable results and prevent unproductive drifts.

# Related Concepts

- AutoML
- LLM-driven experimentation
- Git-based version control in automated research settings

# Source Notes

- [[karpathy-s-autoresearch-went-viral-here-s-how-it-works-and-one-idea-to-try]]

# Source Highlights

## [[karpathy-s-autoresearch-went-viral-here-s-how-it-works-and-one-idea-to-try]]
- **Title**: Karpathy’s Autoresearch Went Viral. Here’s How It Works (and One Idea to Try)
- **Source Type**: article
- **Origin**: web
- **Summary**:
  - Overview of Andrej Karpathy's autoresearch project, which automates model optimization through iterative experiments.
  - Explanation of the three-layer system structure: fixed environment setup, modifiable training code, and natural-language instructions for experimentation.
- **Key excerpt**:
  > "Autoresearch delegates this entire loop to an agent. You start the system, let it run for hours, and it performs many small experiments on its own, gradually improving the model."

# Lineage

This note was derived from:
- [[karpathy-s-autoresearch-went-viral-here-s-how-it-works-and-one-idea-to-try]]
