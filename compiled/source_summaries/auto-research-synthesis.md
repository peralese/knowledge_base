---
title: "Auto Research Synthesis"
note_type: "source_summary"
compiled_from: 
  - "auto-research"
date_compiled: "2026-04-19"
date_updated: "2026-04-19"
topics: 
  - "AI Agents in Research"
  - "Autonomous Machine Learning Experiments"
  - "GPT Model Training"
tags: 
  - "source_summary"
  - "AI Agents in Research"
  - "Autonomous Machine Learning Experiments"
  - "GPT Model Training"
  - "auto-research"
confidence: "medium"
confidence_score: 0.83
generation_method: "ollama_local"
approved: false
---

# Summary

The Auto Research project by Andrej Karpathy aims to explore the use of autonomous AI agents for conducting research on machine learning model training. The project involves an AI agent modifying a Python file (`train.py`) that contains the GPT model, optimizer, and training loop, running experiments autonomously overnight, and producing logs with results. This setup is designed to optimize research progress based on fixed constraints such as a 5-minute time budget per experiment.

Key components of the project include:
- `prepare.py`: Handles data preparation and runtime utilities.
- `train.py`: Contains model architecture, optimizer settings, and training loop—modified by AI agents.
- `program.md`: Instructions for the AI agent detailing how to conduct experiments autonomously.

# Key Insights

- **Single File Iteration**: The project focuses on modifying a single Python file (`train.py`) that houses all necessary components of the GPT model. This keeps iterations manageable and diffs reviewable.
- **Fixed Time Budget**: Experiments run for exactly 5 minutes regardless of computational power, ensuring direct comparability between experiments but limiting cross-platform results comparison.
- **Self-Contained Setup**: Requires minimal dependencies beyond PyTorch and a few packages, making it easy to set up on single-GPU systems.

# Related Concepts

- AI Agents in Research
- Autonomous Machine Learning Experiments
- GPT Model Training

# Source Notes

- [[auto-research]]

# Source Highlights

## [[auto-research]]
- Title: Auto Research
- Source Type: repo
- Origin: web
- Summary: The project explores the use of autonomous AI agents for conducting research on machine learning model training.
- Key excerpt:
  > One day, frontier AI research used to be done by meat computers in between eating, sleeping, having other fun, and synchronizing once in a while using sound wave interconnect in the ritual of "group meeting". That era is long gone. Research is now entirely the domain of autonomous swarms of AI agents running across compute cluster megastructures in the skies.

# Lineage

This note was derived from:
- [[auto-research]]
