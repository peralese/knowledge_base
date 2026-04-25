---
title: "Auto Research"
note_type: "topic"
compiled_from: 
  - "auto-research-synthesis"
  - "karpathy-s-autoresearch-went-viral-here-s-how-it-works-and-one-idea-to-try-synthesis"
date_compiled: "2026-04-19"
date_updated: "2026-04-25"
topics:
  - "Auto Research"
tags:
  - "topic"
  - "auto-research"
confidence: "medium"
generation_method: "ollama_local"
approved: true
---

# Summary

The Auto Research project by Andrej Karpathy automates the process of running experiments and iterating on machine learning models. This initiative leverages autonomous AI agents, using large language models (LLMs) to modify a Python training script (`train.py`) overnight within strict time constraints. Each iteration involves evaluating metrics and retaining only those changes that improve model performance.

# Key Insights

- **Single File Iteration Approach**: By focusing on modifying only one Python file (`train.py`), iterations are easily reviewable and manageable.
- **Time-Bound Experiments**: Each experiment runs for precisely 5 minutes to ensure uniformity across experiments, though this limits direct comparison between different computational environments.
- **LLM-Driven Code Editing**: The system uses an LLM to propose modifications directly in the Python training script rather than traditional hyperparameter tuning.
- **Efficient Setup and Automation**: Requires minimal external dependencies beyond PyTorch and a few additional packages, making it straightforward to set up on single-GPU systems. The project introduces automation techniques for conducting AI research focused on optimizing training processes through autonomous agents.

# Related Concepts

- AI Agents in Research
- Autonomous Machine Learning Experiments
- GPT Model Training
- AutoML
- LLM-driven experimentation
- Git-based version control in automated research settings
- AI-driven research automation
- Autonomous experimentation in neural networks
- Hyperparameter optimization through autonomous agents
- Large Language Models (LLMs)

# Source Notes

- [[auto-research-synthesis]]
- [[karpathy-s-autoresearch-went-viral-here-s-how-it-works-and-one-idea-to-try-synthesis]]

# Lineage

- [[auto-research-synthesis]]
- [[karpathy-s-autoresearch-went-viral-here-s-how-it-works-and-one-idea-to-try-synthesis]]
