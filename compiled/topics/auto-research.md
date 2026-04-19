---
title: "Auto Research"
note_type: "topic"
compiled_from: 
  - "auto-research-synthesis"
date_compiled: "2026-04-19"
date_updated: "2026-04-19"
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

The Auto Research project, initiated by Andrej Karpathy, aims to explore how autonomous AI agents can be used to conduct research on machine learning model training. The core of this initiative involves an AI agent that modifies a Python script (`train.py`), which contains the GPT model architecture and training loop. This modified script is then executed autonomously overnight with strict time constraints (5 minutes per experiment) to ensure consistency in experimental conditions.

Key aspects of the project include:
- **Prepare Script**: A `prepare.py` script handles data preparation and provides runtime utilities.
- **Training Script**: The `train.py` file encapsulates all necessary components for GPT model training, including optimizer settings and the training loop. It is the primary object of modification by AI agents.
- **Program Instructions**: Detailed instructions in a `program.md` file guide the autonomous conduct of experiments by AI agents.

# Key Insights

- **Single File Iteration Approach**: By focusing on modifying only one Python file (`train.py`) for each iteration, the project ensures that changes are easily reviewable and manageable. This approach simplifies tracking progress and understanding experimental differences.
- **Time-Bound Experiments**: Each experiment runs for precisely 5 minutes to maintain uniformity across experiments. However, this time limitation restricts direct comparison of results between different computational environments.
- **Efficient Setup**: The project requires minimal external dependencies beyond PyTorch and a few additional packages, making it straightforward to set up on single-GPU systems.

# Related Concepts

- AI Agents in Research
- Autonomous Machine Learning Experiments
- GPT Model Training

# Source Notes

- [[auto-research-synthesis]]

# Lineage

- [[auto-research-synthesis]]
