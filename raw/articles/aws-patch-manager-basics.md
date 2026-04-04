---
title: "AWS Patch Manager Basics"
source_type: "article-note"
origin: "AWS Systems Manager Patch Manager documentation"
date_ingested: "2026-04-03"
status: "reviewed"
topics:
  - "aws"
  - "patching"
  - "systems-manager"
tags:
  - "aws"
  - "patch-manager"
  - "operations"
author: "AWS"
date_created: "2026-04-03"
date_published: "2024-11-15"
language: "en"
summary: "Patch Manager helps automate operating system patching through patch baselines, patch groups, and maintenance windows."
source_id: "src-aws-patch-manager-basics"
canonical_url: "https://docs.aws.amazon.com/systems-manager/latest/userguide/patch-manager.html"
related_sources:
  - "src-aws-inspector-overview"
confidence: "medium"
license: "See source site terms"
---

# Overview

AWS Systems Manager Patch Manager is used to automate patching for managed nodes. It provides a repeatable way to define approved patches and apply them during controlled maintenance windows.

# Source Content

Patch Manager centers on patch baselines, target selection, and scheduled execution. Teams usually combine it with maintenance windows and tagging strategies so that patching can be rolled out by environment or workload type.

# Key Points

- Patch baselines define which patches are approved or rejected.
- Maintenance windows provide a controlled time to apply updates.
- Patch groups and tags help scope patching to the right systems.

# Notes

This source is focused on operating system patching and operational control. It does not replace vulnerability assessment; it is better paired with a detection-oriented service.

# Lineage

- Raw note path: `raw/articles/aws-patch-manager-basics.md`
- Original source: AWS Systems Manager Patch Manager documentation
- Ingest method: manual markdown note
- Related sources: `raw/articles/aws-inspector-overview.md`
