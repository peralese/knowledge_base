---
name: design-review
description: Review an architecture or design — a codebase, a diff, or a design doc/ADR — against the user's own technical books (reference-library MCP), producing findings ranked by impact, each with a book citation and a concrete suggestion. Use when the user asks for a "design review", "architecture review", "/design-review", to "check this design against my books", or for a cited ADR/decision write-up.
---

# Design review against the books

Review the user's design using their reference library (MCP server `reference-library`) as the standard to check against. Every finding cites a book.

## Target

The argument says what to review: a path (project or directory), a document (a design doc, ADR or README), `diff` (the current git changes), or a description pasted in chat. With no argument, review the current project and say so.

## Steps

1. **Understand the design first.** Read the target. For a codebase, read the README, the entry points, the module layout, the data stores and the integration points; don't read every file. Write down, for yourself, the 4–8 **decisions** the design makes. Examples: service boundaries, sync vs async communication, data ownership and consistency, failure handling, deployment unit, API style, security boundaries, observability.
2. **Check each decision against the library.** Run `search` for the decision and its trade-off, e.g. "shared database between services", "orchestration vs choreography", "API versioning". Use 1–2 phrasings each, then `read_section` where you need the full argument. Pull from several books where you can.
3. **Report findings ranked by impact.** For each one:
   - **Finding:** what the design does, and the risk or missed opportunity.
   - **Books say:** the relevant guidance, cited as (Title, Chapter > Section).
   - **Suggestion:** a concrete change, or "keep, and here's why", plus what it would cost.
   - **Confidence:** high, medium or low. Say what you couldn't see.
4. **Note what's sound too.** Briefly list the decisions the books support, with citations, so the review isn't only negative.
5. **Offer an ADR.** If the user wants it, write the key decision up as an ADR (Context, Decision, Consequences, Alternatives considered) with the citations inline.

## Rules

- Only cite passages you actually read. If the library has nothing on a decision, say so and give your own view, labelled as your own.
- Prefer the user's constraints (team size, scale, deadline) over textbook ideals. Books often assume a larger organisation.
- Keep it to the findings that matter. Five strong findings beat fifteen weak ones.
