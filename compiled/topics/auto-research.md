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

The Auto Research project by Andrej Karpathy explores the use of autonomous AI agents to optimize machine learning models through iterative experimentation. This initiative involves an LLM-driven loop that modifies a Python script (`train.py`) overnight with strict time constraints, ensuring uniformity and focused exploration. The system consists of three main components: `prepare.py`, which handles data preparation; `train.py`, the modifiable training code; and `program.md`, natural-language instructions guiding the research process.

# Key Insights

- **Single File Iteration Approach**: By focusing on modifying only one Python file (`train.py`) for each iteration, changes are easily reviewable and manageable.
- **Time-Bound Experiments**: Each experiment runs for precisely 5 minutes to maintain uniformity across experiments but restricts direct comparison of results between different computational environments.
- **Efficient Setup**: The project requires minimal external dependencies beyond PyTorch and a few additional packages, making it straightforward to set up on single-GPU systems.
- **Automation in AI Research**: The project introduces automation techniques for conducting AI research, particularly focusing on optimizing training processes through autonomous agents.

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

# Source Notes

- [[auto-research-synthesis]]
- [[karpathy-s-autoresearch-went-viral-here-s-how-it-works-and-one-idea-to-try-synthesis]]

# Lineage

- [[auto-research-synthesis]]
- [[karpathy-s-autoresearch-went-viral-here-s-how-it-works-and-one-idea-to-try-synthesis]]
