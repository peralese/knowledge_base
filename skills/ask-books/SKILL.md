---
name: ask-books
description: Answer a technical question from the user's own book library (reference-library MCP), across books, with citations — what the books say, where they agree or disagree, and what they don't cover. Use when the user asks "what do my books say about X", "ask the books", "/ask-books", or wants a book-backed answer on architecture, distributed systems, APIs, data/ML, LLMs and agents, security, cloud, Linux or git.
---

# Ask the books

Answer the user's question from their reference library (MCP server `reference-library`), not from general knowledge alone.

## Steps

1. **Search broadly.** Call `search` with 2–4 phrasings of the question: the user's words, the standard technical term, and the trade-off or problem it addresses. Add `category` when the question clearly sits in one (1 Enterprise & Software, 2 Cloud & Infra, 3 Integration & APIs, 4 Data/AI/ML, 5 Security, 6 AI Strategy, 7 Developer & Systems). Put exact commands or terms in double quotes.
2. **Read the strongest hits.** For the 2–5 most relevant passages, especially from *different* books, call `read_section` when the passage is cut short or the argument needs its context.
3. **Answer in this shape** (skip a part when it has nothing):
   - **Short answer:** two or three sentences.
   - **What the books say:** the main points, each cited inline as (Title, Chapter > Section).
   - **Where they agree or disagree:** name the books and the actual difference, such as different assumptions, scale or era.
   - **Not covered:** what the library doesn't address. Add your own knowledge here, labelled as such.
   - **For your situation:** if the user's context is known (their project, their day job), apply the points to it.
4. **Be honest about coverage.** If the searches return nothing relevant, say "the library has nothing on this" and answer normally. Never cite a passage you didn't read.

Keep quotes short. Paraphrase with citations instead of pasting long passages.
