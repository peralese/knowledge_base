# Reference Library — Plan & Session Handoff

_Last updated: 2026-10-02_

## How we got here

- **The problem:** The knowledge base pipeline works, but nobody uses it. Commits were 129 in June, 5 in July and 13 in August. September had only the automated weekly lint reports, and nobody read them. Obsidian hasn't been opened to review notes since June.
- **What started this conversation:** I found agent and sub-agent articles while studying for the Claude Certified Architect exam (end of October 2026), then asked myself why I'd add them to a system I don't use. Studying already has its own separate project, so this plan is *not* about studying.
- **The diagnosis:** The knowledge base is built around an activity I don't do: coming back to browse and read notes. Better browsing or retrieval features (the Concepts/Entities Browser, hybrid retrieval, Docling) won't fix that.
- **The new direction:** Turn the knowledge base into a **reference library that Claude reads for me**. Claude Code queries it through an MCP server while I do normal work, and cites passages from my books and reference articles. I never have to open Obsidian.
- **The rule for adding anything:** *Will this make Claude more useful on work I'm actually doing?* If not, don't add it.

## What goes in the library

**Reference material only.** That means books, papers and lasting engineering write-ups, all stored as full text split into passages with citations. Timely or news-style articles stay in the current pipeline or get skipped.

- **Books:** 83 unique O'Reilly titles, each in both EPUB and PDF. Use the **EPUBs**, which have cleaner chapter structure. File sizes run 3.8–21 MB.
- **Articles:** reference-quality pieces, for example Anthropic's "Building Effective Agents" (https://www.anthropic.com/engineering/building-effective-agents). The ~20 articles already saved in `raw/domains/ai/articles/` keep their full text and can be indexed directly once I've sorted reference pieces from timely ones.
- **Categories:** every source is tagged with one category, and search can filter by it.
  1. Enterprise & Software
  2. Cloud, Platform & Infrastructure Engineering
  3. Integration, APIs & Automation
  4. Data, AI & Machine Learning Engineering
  5. Cybersecurity & Security Architecture
  6. AI Strategy, Society & Emerging Technology
  7. Developer & Systems Reference

## Pilot (start here)

| Source | Category | What it tests |
|---|---|---|
| AI Engineering | 4 | Searching by meaning across concepts and tradeoffs |
| Fundamentals of Enterprise Architecture | 1 | Frameworks and vocabulary used in design discussions |
| Learning Git | 7 | Exact-word search for specific commands and how-tos |
| Hands-On Machine Learning with Scikit-Learn, Keras & TensorFlow | 4 | **Book in active use, expected to be queried most.** Passages that mix code and explanation, where code blocks must stay whole. Also the reading-partner book for the pilot |
| Building Effective Agents (article) | 4 | Articles handled the same way as books |

**Success test:** use the library for about two weeks of normal work. Did Claude bring up something useful I wouldn't otherwise have had? If yes, index the remaining books. If no, freeze the knowledge base and turn off the weekly lint jobs.

## Planned design

1. **Splitting into passages.** Parse each EPUB using its own chapter and section headings. Passages are a few paragraphs long. Each one keeps book, chapter, section and page or location. **No LLM summarizing**, because the full passage is what's worth citing.
2. **Search index.** Exact-word search (SQLite FTS5) plus search by meaning (local `nomic-embed-text` via Ollama), combined into one result list. The current `scripts/vector_index.py` compares against every item in pure Python and was built for fewer than 1,000 notes, so it **won't scale** to about 80,000 passages. Use a proper vector search setup such as sqlite-vec.
3. **MCP server** for Claude Code, registered at user level so it works in any project. It offers three tools: `search` (with an optional category filter), `list_sources`, and `read_section` (pulls the surrounding section when one passage isn't enough).
4. **Standing instruction** telling Claude to check the library on architecture and design questions. Without it, Claude will answer from its own knowledge and never look.
5. **Adding new material in one step:** "add this URL" or "add this EPUB" fetches, saves and indexes it.

## Workflow

You never send queries to the library directly. You ask Claude about your work, and Claude decides to search:

```
You -> Claude -> (sees a design question; the standing instruction says check the library)
    -> MCP search(query, category?) -> local index -> passages + citations
    -> MCP read_section(...)   (only if more surrounding text is needed)
    -> Claude answers using your code + its own knowledge + cited passages -> You
```

- Claude may search several times per question.
- MCP is an open standard, so any MCP client (Claude Code, Claude Desktop, Cursor, ...) can use the same server. Each client needs its own copy of the standing instruction.

## Learning from the books

The same library supports reading a book with Claude as a reading partner, with nothing new to build. Claude can give a chapter overview before you read, explain hard parts using your own projects, quiz you afterwards, and compare books against each other.

- **Don't build a learning system.** That means no progress trackers, flashcards or saved chapter summaries. That's the review-and-come-back pattern that already failed.
- During the pilot, use *Hands-On Machine Learning* as the reading-partner book, since you're already working through it. Build a small feature only if you keep needing it.

## Relationship to the existing knowledge base

**Build alongside it, don't tear it down.**
- New code goes in its own top-level `library/` folder with its own index. It doesn't import from the compile and synthesis pipeline. Copy anything useful rather than linking to it.
- Reuse the full-text articles in `raw/domains/ai/articles/` and the local Ollama setup. Don't reuse `vector_index.py`.
- Pause the weekly lint jobs now.
- **If the pilot works:** tag the repo `pre-library`, then delete the compile pipeline, compiled notes, topic registry and lint jobs.
- **If it doesn't:** delete `library/` and freeze everything else.

## As built (pilot)

- **Code:** `library/` (own Python 3.12 venv; MCP SDK 2.x `MCPServer`). Registered with `claude mcp add --scope user reference-library`. The standing instruction is in `~/.claude/CLAUDE.md` and also in the server's `instructions` field, so other MCP clients get it too.
- **Sections follow each book's table of contents**, not heading tags. *Learning Git* (an InDesign export) uses `<h1>` for sub-sections, while the TOC is reliable in all four books.
- **No page numbers.** None of the EPUBs have page-break markers, so citations are `Title — Chapter > Section`.
- **Articles are stored on the NAS too**, in `<category>/articles/<slug>.html` with a `.url.json` sidecar holding the source URL, so the folder sets the category for articles as well.
- **Indexing is faster than estimated:** ~20 s per book, so all 83 books would take ~30 min, not 1–3 h. The full index would be ~350 MB.

## Storage decisions

- **Free space:** 342 GB on the internal SSD (500 GB). No external drives are connected. iCloud Drive is on but holds no books.
- **Size estimate for all 83 books:** EPUBs ~0.8 GB (1.7 GB worst case) plus index ~0.5–1 GB. That's about 1.3–2.2 GB, or ~4.5 GB worst case with PDFs too. Space isn't a concern.
- **Indexing time is the real cost.** All 83 books will take roughly 1–3 hours one time, run in the background or overnight. After that, each new book takes a minute or two. The pilot will give real numbers.
- **Book location (decided):** the NAS share `//peralese@192.168.68.173/peralese`, mounted at `~/Network/peralese`. Books go in `Books/Technical Books/`, one subfolder per category (`1 - Enterprise & Software` … `7 - Developer & Systems Reference`). **The folder a book sits in sets its category.** The indexer reads only `~/Books/library`, a link to that folder, so the rest of the share (Dr Who, Asterix, etc.) stays out. If the books ever move, update the link and nothing else.
- **Use the `~/Network/peralese` mount only.** The share is also mounted at `/Volumes/peralese` from Finder. That's harmless, but never point the indexer at it.
- **The index stores full passage text.** `search` and `read_section` work entirely from the local index, so they keep working when the NAS is asleep or you're away from home. The NAS only needs to be reachable when adding or re-indexing books.
- **Not in iCloud Drive.** "Optimize Mac Storage" can swap files for cloud placeholders the indexer can't read.
- **The index must stay local, never on a network share.** SQLite file locking is unreliable over SMB/NFS and can corrupt the database. The MCP server would also break whenever the share isn't mounted. The index can always be rebuilt from the books, so only the books need backing up.

## Open items / next steps

- [x] Decide where the books live: NAS, `~/Books/library` → `~/Network/peralese/Books/Technical Books` (category folders created 2026-10-02).
- [x] Copied the 4 pilot EPUBs into their category folders (AI Engineering → 4, Hands-On Machine Learning → 4, Fundamentals of Enterprise Architecture → 1, Learning Git → 7).
- [ ] Pause the weekly lint jobs.
- [ ] Commit or discard the leftover changes from the last compile run.
- [x] Built the pilot (2026-10-02): passage splitting, index, MCP server, standing instruction and `add_url.py`. See `library/README.md`. 4 books plus *Building Effective Agents* make 1,892 passages and a 17 MB index, indexed in ~90 s. Test questions returned the right book and chapter for both meaning and exact-word queries.
- [ ] **Start the two-week trial (2026-10-03 → 2026-10-17).** Restart Claude Code so it picks up the server, then just work normally. Each time a library citation actually helped (or got in the way), jot down one line.
- [ ] Sort the existing saved articles into reference and timely.
- [ ] Two-week trial, then decide: add the remaining books, or freeze the knowledge base.
- **Paused until the pilot proves useful:** the Concepts/Entities Browser, hybrid retrieval over compiled notes, and the Docling spike (the items in `context.md`).

## Resume prompt

> Read `docs/reference-library-plan.md` and `library/README.md`. The pilot is built and in its two-week trial. Let's review how it's going.
