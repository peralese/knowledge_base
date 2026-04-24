---
title: "Auto Research"
note_type: "topic"
compiled_from: 
  - "auto-research-synthesis"
  - "karpathy-s-autoresearch-went-viral-here-s-how-it-works-and-one-idea-to-try-synthesis"
date_compiled: "2026-04-19"
date_updated: "2026-04-22"
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

The Auto Research project by Andrej [[karpathy]] explores the use of autonomous AI agents to optimize machine learning models through iterative experimentation. This initiative involves an LLM-driven loop that modifies a Python script (`train.py`) overnight with strict time constraints, ensuring uniformity and focused exploration. The system consists of three main components: `prepare.py`, which handles data preparation; `train.py`, the modifiable training code; and `program.md`, natural-language instructions guiding the research process.

# Key Insights

- **Single File Iteration Approach**: By focusing on modifying only one Python file (`train.py`) for each iteration, changes are easily reviewable and manageable.
- **Time-Bound Experiments**: Each experiment runs for precisely 5 minutes to maintain uniformity across experiments but restricts direct comparison of results between different computational environments.
- **Efficient Setup**: The project requires minimal external dependencies beyond PyTorch and a few additional packages, making it straightforward to set up on single-GPU systems.
- **Autoresearch Concept**: An LLM-driven loop that iteratively modifies training code to optimize a specific metric.
- **System Structure**:
  - `prepare.py`: Fixed components of the experiment.
  - `train.py`: Model implementation and training loop, modifiable by the agent.
  - `program.md`: Natural-language instructions guiding the research process.

# Related Concepts

- AI Agents in Research
- Autonomous Machine Learning Experiments
- GPT Model Training
- AutoML
- LLM-driven experimentation
- Git-based version control in automated research settings

# Source Notes

- [[auto-research-synthesis]]
- [[karpathy-s-autoresearch-went-viral-here-s-how-it-works-and-one-idea-to-try-synthesis]]

# Lineage

- [[auto-research-synthesis]]
- [[karpathy-s-autoresearch-went-viral-here-s-how-it-works-and-one-idea-to-try-synthesis]]
