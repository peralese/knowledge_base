---
title: "Karpathy’S Autoresearch Went Viral. Here’S How It Works (And One Idea To Try)"
source_type: "article"
origin: "web"
date_ingested: "2026-04-22"
status: "raw"
topics: 
  - "auto-research"
tags: 
  - "Auto Research"
  - "auto-research"
  - "Karpathy"
author: "Alexey Grigorev"
date_published: "2026-03-16"
source_id: "SRC-20260422-0001"
canonical_url: "https://alexeyondata.substack.com/p/karpathys-autoresearch-went-viral"
related_sources: []
---

# Overview

Brief description of what this source is and why it matters.

# Source Content

---
title: Karpathy’S Autoresearch Went Viral. Here’S How It Works (And One Idea To Try)
source_type: article
origin: file
canonical_url: https://alexeyondata.substack.com/p/karpathys-autoresearch-went-viral
topics:
  - auto-research
author: Alexey Grigorev
date_published: 2026-03-16
tags:
  - Auto Research
  - auto-research
  - Karpathy
---

<!-- topic_slug: auto-research -->

Alexey On Data

SubscribeSign in

Karpathy’s Autoresearch Went Viral. Here’s How It Works (and One Idea to Try)

An agent that runs experiments, edits training code, and improves models in a loop.

Alexey Grigorev

Mar 16, 2026

16

1

5

Share

Over the last few days, Andrej Karpathy’s autoresearch project
 has been widely shared and discussed. Many people on X (Twitter) are
exploring the idea and trying to apply the same pattern to their own
projects.

I
 looked through the repository and decided to write a short note
explaining what the project actually does and why it is attracting so
much interest.

Subscribe

Core Idea

At
 a high level, autoresearch automates something that normally takes a
large amount of human time: running experiments and iterating on models.
 In a typical workflow, a researcher modifies the training code or
parameters, runs an experiment, evaluates the result, logs the metrics,
and then repeats the process.

Autoresearch
 delegates this entire loop to an agent. You start the system, let it
run for hours, and it performs many small experiments on its own,
gradually improving the model.

Conceptually, this resembles
AutoML, where algorithms search through hyperparameters and
architectures. The difference is that autoresearch uses an LLM to
perform the search directly in code. Instead of selecting parameters
from predefined spaces, the model edits the training script itself and
proposes new ideas for the architecture or training procedure.

Repository Structure

The repository implementing this system is surprisingly small.

It revolves around three files:

prepare.py:
 Contains the fixed components of the experiment: data preparation,
dataset downloads, and the evaluation logic. The agent cannot modify
this file.

train.py: Contains the model implementation and training loop. This is the file the agent edits when proposing new experiments.

program.md:
 Contains instructions for the agent written in natural language.
Karpathy describes it as “research org code written in English.”

When
 the system starts, the agent establishes a baseline by creating a new
Git branch, running the unmodified training script, and recording the
initial metric.

After that, it enters the experiment loop:

Edits train.py, commits the change

Runs the experiment

Extracts the resulting metrics from the logs

If
 the metric improves, the commit is kept. If the result is worse or
unchanged, the repository is reset to the previous state. Each
experiment runs under the same fixed time budget, which ensures that
results remain comparable even if the agent modifies the model size or
training procedure.

The most interesting aspect of the project is the system's structure. There are effectively three layers of programming:

First layer: Traditional code in prepare.py, which defines the rules of the environment and the evaluation metric.

Second layer: Python code in train.py, which represents the model and can be modified during experiments.

Third layer: program.md, where the human writes natural-language instructions describing how the agent should behave as a researcher.

In
 practice, this creates an unusual chain where a human writes
instructions in English, the LLM translates them into modifications to
Python code, and the Python code trains a neural network. Instead of
directly improving the model, the human is programming the experimental
process using natural language.

Share

Optimization Process

The
 system works because the experimentation process is tightly
constrained. Each experiment has a strict time budget, so runs cannot
expand indefinitely. Every change is evaluated using a single metric,
and only modifications that improve the metric are kept. If a change
fails or produces worse results, it is automatically reverted. These
rules keep the exploration focused and prevent the system from drifting
into unproductive directions.

The
 objective of the loop is to optimize a metric that measures model
quality. In Karpathy’s example, the metric is validation bits per byte
(val_bpb). Lower values indicate better performance. This metric is
useful because it remains comparable even if the tokenizer or vocabulary
 size changes during experimentation.

Each iteration follows a
simple structure: the agent modifies the training code, runs the
experiment, evaluates the metric, and keeps the change only if the
result improves. Otherwise, it rolls back the change and tries something
 else. This process continues indefinitely.

Results

Karpathy reported
 that the system produced 110 successful changes in about twelve hours,
improving the validation metric from 0.862415 to 0.858039. He also noted
 that much of his recent effort has gone into refining the experimental
setup rather than directly modifying the model. In other words, the work
 has shifted toward improving the system that runs the research.

Andrej Karpathy@karpathy

nanochat now trains GPT-2 capability model in just 2 hours on a single 8XH100 node (down from ~3 hours 1 month ago). Getting a lot closer to ~interactive! A bunch of tuning and features (fp8) went in but the biggest difference was a switch of the dataset from FineWeb-edu to

5:30 PM · Mar 5, 2026 · 584K Views

332 Replies · 555 Reposts · 6.43K Likes

Others Experimenting with the Pattern

Since the project was published, others have started experimenting with the same pattern.

One example is Autosearcher,
 a distributed system in which multiple agents run experiments in
parallel and share their discoveries. In early runs, the system
rediscovered techniques such as Kaiming initialization and RMSNorm
purely through experimentation.

Another example is AutoVoiceEvals,
 in which the same iterative loop is applied to optimize prompts for
voice agents via adversarial evaluation. In one reported experiment,
twenty automated iterations improved a scheduling agent’s success rate
from 25 percent to 100 percent, while the final prompt became shorter
rather than longer.

Project Idea

One possible experiment with the autoresearch approach is applying it to writing style optimization.

When
 working with LLMs, the generated text often differs noticeably from my
own writing style. To reduce this gap, I currently maintain a style
guide that describes how I phrase things, structure sentences, and
revise outputs that do not match my voice. Over time, this guide grows
as I manually correct generated text and add new rules.

The idea is to automate this process using an autoresearch-style loop.

Instead
 of refining the style guide manually, the system would treat the prompt
 or style guide itself as the artifact being optimized. The loop would
use a dataset consisting of texts I wrote or texts where I corrected LLM
 output after generation.

Each iteration would follow a pattern similar to the autoresearch workflow:

Modify the style prompt or guide

Generate sample outputs from the model

Compare the outputs to reference texts

Evaluate stylistic similarity using a metric

Keep the change if the score improves

Possible
 evaluation signals could include embedding similarity, a classifier
trained to distinguish my writing from generated text, or LLM-based
evaluation.

This approach turns prompt tuning into an automated
search process. Instead of manually adjusting instructions, the agent
iteratively improves the prompt based on measurable feedback.

Thanks for reading Alexey On Data! Subscribe for free to receive new posts and support my work.

Subscribe

Why People Find It Interesting

autoresearch’s
 underlying optimization loop is not fundamentally new. What has changed
 is that LLMs can now participate directly in the research workflow.
They can read code, propose modifications, run experiments, analyze
results, and generate the next hypothesis. Instead of manually exploring
 ideas, the human defines the rules and constraints of the research
environment and lets the system explore it automatically.

That shift in how experimentation is organized is what makes autoresearch interesting to so many people right now.

Edited by Valeriia Kuka

Subscribe to Alexey On Data

Launched 5 months ago

Practical
 writing on building, testing, and operating AI systems, workflows, and
automation, based on my projects and experiments. Subscribe to get ideas
 you can reuse in your own work.

Subscribe

By subscribing, you agree Substack's Terms of Use, and acknowledge its Information Collection Notice and Privacy Policy.

16 Likes∙
5 Restacks

16

1

5

Share

PreviousNext

Discussion about this post

CommentsRestacks

Pastor Soto

Mar 16

Liked by Valeriia Kuka

That's a great idea to try. It would be interesting to see the metrics moving around in each iteration, like the good old days!!

Like (1)

Reply

Share

TopLatestDiscussions

How I Dropped Our Production Database and Now Pay 10% More for AWS

I’m working on expanding the AI Shipping Labs website and wanted to migrate its current version from static GitHub Pages to AWS.

Mar 6 • Alexey Grigorev

156

31

12

I Built an AI Agent Team for Software Development and Tested on 5 Real Projects

I assigned agents to PM, SWE, QA, and on-call roles and used the setup across five different software projects.

Apr 3 • Alexey Grigorev

29

4

4

An Unexpected Entry Into AI Memory: Milla Jovovich’s Open-Source MemPalace

Why this offline, memory-palace-based system stands out from the usual model-heavy approach to assistant memory.

Apr 7 • Alexey Grigorev

24

1

1

See all

Ready for more?

Subscribe

© 2026 Alexey Grigorev · Privacy ∙ Terms ∙ Collection notice

 Start your SubstackGet the app

Substack is the home for great culture

# Key Points

- 

# Notes

# Lineage

- Ingested via: scripts/ingest.py
- Manifest entry: metadata/source-manifest.json::SRC-20260422-0001
- Source path: /home/peralese/Projects/Knowledge_Base/raw/inbox/browser/karpathy-s-autoresearch-went-viral-here-s-how-it-works-and-one-idea-to-try.md
- Canonical URL: https://alexeyondata.substack.com/p/karpathys-autoresearch-went-viral

