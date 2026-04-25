---
title: "llm-wiki"
source_type: "repo"
origin: "web"
date_ingested: "2026-04-22"
status: "raw"
topics: 
  - "llm-knowledge-bases"
tags: 
  - "llm-knowledge-bases"
  - "Knowledge Base"
  - "Karpathy"
author: "Andrej Karpathy"
source_id: "SRC-20260422-0002"
canonical_url: "https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f"
related_sources: []
---

# Overview

Brief description of what this source is and why it matters.

# Source Content

---
title: llm-wiki
source_type: repo
origin: url
canonical_url: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
topics:
  - llm-knowledge-bases
author: Andrej Karpathy
tags:
  - llm-knowledge-bases
  - Knowledge Base
  - Karpathy
---

<!-- topic_slug: llm-knowledge-bases -->

Skip to content

        Search Gists

Search Gists

  All gists

  Back to GitHub

      Sign in

        Sign up

        Sign in

          Sign up

        You signed in with another tab or window. Reload to refresh your session.
        You signed out in another tab or window. Reload to refresh your session.
        You switched accounts on another tab or window. Reload to refresh your session.

Dismiss alert

        Instantly share code, notes, and snippets.

            karpathy/llm-wiki.md

          Created
          April 4, 2026 16:25

Show Gist options

          Download ZIP

    Star

          5,000+
          (5,000+)

You must be signed in to star a gist

    Fork

          5,000+
          (5,000+)

You must be signed in to fork a gist

    Embed

        Select an option

           Embed
      Embed this gist in your website.

           Share
      Copy sharable link for this gist.

          Clone via HTTPS
      Clone using the web URL.

No results found

        Learn more about clone URLs

        Clone this repository at <script src="https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f.js"></script>

Save karpathy/442a6bf555914893e9891c11519de94f to your computer and use it in GitHub Desktop.

      Code

        Revisions
        1

        Stars
        5,000+

        Forks
        5,000+

    Embed

        Select an option

           Embed
      Embed this gist in your website.

           Share
      Copy sharable link for this gist.

          Clone via HTTPS
      Clone using the web URL.

No results found

        Learn more about clone URLs

        Clone this repository at <script src="https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f.js"></script>

Save karpathy/442a6bf555914893e9891c11519de94f to your computer and use it in GitHub Desktop.

      Download ZIP

    llm-wiki

    Raw

              llm-wiki.md

LLM Wiki

A pattern for building personal knowledge bases using LLMs.

This is an idea file, it is designed to be copy pasted to your own LLM Agent (e.g. OpenAI Codex, Claude Code, OpenCode / Pi, or etc.). Its goal is to communicate the high level idea, but your agent will build out the specifics in collaboration with you.

The core idea

Most people's experience with LLMs and documents looks like RAG: you upload a collection of files, the LLM retrieves relevant chunks at query time, and generates an answer. This works, but the LLM is rediscovering knowledge from scratch on every question. There's no accumulation. Ask a subtle question that requires synthesizing five documents, and the LLM has to find and piece together the relevant fragments every time. Nothing is built up. NotebookLM, ChatGPT file uploads, and most RAG systems work this way.

The idea here is different. Instead of just retrieving from raw documents at query time, the LLM incrementally builds and maintains a persistent wiki — a structured, interlinked collection of markdown files that sits between you and the raw sources. When you add a new source, the LLM doesn't just index it for later retrieval. It reads it, extracts the key information, and integrates it into the existing wiki — updating entity pages, revising topic summaries, noting where new data contradicts old claims, strengthening or challenging the evolving synthesis. The knowledge is compiled once and then kept current, not re-derived on every query.

This is the key difference: the wiki is a persistent, compounding artifact. The cross-references are already there. The contradictions have already been flagged. The synthesis already reflects everything you've read. The wiki keeps getting richer with every source you add and every question you ask.

You never (or rarely) write the wiki yourself — the LLM writes and maintains all of it. You're in charge of sourcing, exploration, and asking the right questions. The LLM does all the grunt work — the summarizing, cross-referencing, filing, and bookkeeping that makes a knowledge base actually useful over time. In practice, I have the LLM agent open on one side and Obsidian open on the other. The LLM makes edits based on our conversation, and I browse the results in real time — following links, checking the graph view, reading the updated pages. Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase.

This can apply to a lot of different contexts. A few examples:

Personal: tracking your own goals, health, psychology, self-improvement — filing journal entries, articles, podcast notes, and building up a structured picture of yourself over time.

Research: going deep on a topic over weeks or months — reading papers, articles, reports, and incrementally building a comprehensive wiki with an evolving thesis.

Reading a book: filing each chapter as you go, building out pages for characters, themes, plot threads, and how they connect. By the end you have a rich companion wiki. Think of fan wikis like Tolkien Gateway — thousands of interlinked pages covering characters, places, events, languages, built by a community of volunteers over years. You could build something like that personally as you read, with the LLM doing all the cross-referencing and maintenance.

Business/team: an internal wiki maintained by LLMs, fed by Slack threads, meeting transcripts, project documents, customer calls. Possibly with humans in the loop reviewing updates. The wiki stays current because the LLM does the maintenance that no one on the team wants to do.

Competitive analysis, due diligence, trip planning, course notes, hobby deep-dives — anything where you're accumulating knowledge over time and want it organized rather than scattered.

Architecture

There are three layers:

Raw sources — your curated collection of source documents. Articles, papers, images, data files. These are immutable — the LLM reads from them but never modifies them. This is your source of truth.

The wiki — a directory of LLM-generated markdown files. Summaries, entity pages, concept pages, comparisons, an overview, a synthesis. The LLM owns this layer entirely. It creates pages, updates them when new sources arrive, maintains cross-references, and keeps everything consistent. You read it; the LLM writes it.

The schema — a document (e.g. CLAUDE.md for Claude Code or AGENTS.md for Codex) that tells the LLM how the wiki is structured, what the conventions are, and what workflows to follow when ingesting sources, answering questions, or maintaining the wiki. This is the key configuration file — it's what makes the LLM a disciplined wiki maintainer rather than a generic chatbot. You and the LLM co-evolve this over time as you figure out what works for your domain.

Operations

Ingest. You drop a new source into the raw collection and tell the LLM to process it. An example flow: the LLM reads the source, discusses key takeaways with you, writes a summary page in the wiki, updates the index, updates relevant entity and concept pages across the wiki, and appends an entry to the log. A single source might touch 10-15 wiki pages. Personally I prefer to ingest sources one at a time and stay involved — I read the summaries, check the updates, and guide the LLM on what to emphasize. But you could also batch-ingest many sources at once with less supervision. It's up to you to develop the workflow that fits your style and document it in the schema for future sessions.

Query. You ask questions against the wiki. The LLM searches for relevant pages, reads them, and synthesizes an answer with citations. Answers can take different forms depending on the question — a markdown page, a comparison table, a slide deck (Marp), a chart (matplotlib), a canvas. The important insight: good answers can be filed back into the wiki as new pages. A comparison you asked for, an analysis, a connection you discovered — these are valuable and shouldn't disappear into chat history. This way your explorations compound in the knowledge base just like ingested sources do.

Lint. Periodically, ask the LLM to health-check the wiki. Look for: contradictions between pages, stale claims that newer sources have superseded, orphan pages with no inbound links, important concepts mentioned but lacking their own page, missing cross-references, data gaps that could be filled with a web search. The LLM is good at suggesting new questions to investigate and new sources to look for. This keeps the wiki healthy as it grows.

Indexing and logging

Two special files help the LLM (and you) navigate the wiki as it grows. They serve different purposes:

index.md is content-oriented. It's a catalog of everything in the wiki — each page listed with a link, a one-line summary, and optionally metadata like date or source count. Organized by category (entities, concepts, sources, etc.). The LLM updates it on every ingest. When answering a query, the LLM reads the index first to find relevant pages, then drills into them. This works surprisingly well at moderate scale (~100 sources, ~hundreds of pages) and avoids the need for embedding-based RAG infrastructure.

log.md is chronological. It's an append-only record of what happened and when — ingests, queries, lint passes. A useful tip: if each entry starts with a consistent prefix (e.g. ## [2026-04-02] ingest | Article Title), the log becomes parseable with simple unix tools — grep "^## \[" log.md | tail -5 gives you the last 5 entries. The log gives you a timeline of the wiki's evolution and helps the LLM understand what's been done recently.

Optional: CLI tools

At some point you may want to build small tools that help the LLM operate on the wiki more efficiently. A search engine over the wiki pages is the most obvious one — at small scale the index file is enough, but as the wiki grows you want proper search. qmd is a good option: it's a local search engine for markdown files with hybrid BM25/vector search and LLM re-ranking, all on-device. It has both a CLI (so the LLM can shell out to it) and an MCP server (so the LLM can use it as a native tool). You could also build something simpler yourself — the LLM can help you vibe-code a naive search script as the need arises.

Tips and tricks

Obsidian Web Clipper is a browser extension that converts web articles to markdown. Very useful for quickly getting sources into your raw collection.

Download images locally. In Obsidian Settings → Files and links, set "Attachment folder path" to a fixed directory (e.g. raw/assets/). Then in Settings → Hotkeys, search for "Download" to find "Download attachments for current file" and bind it to a hotkey (e.g. Ctrl+Shift+D). After clipping an article, hit the hotkey and all images get downloaded to local disk. This is optional but useful — it lets the LLM view and reference images directly instead of relying on URLs that may break. Note that LLMs can't natively read markdown with inline images in one pass — the workaround is to have the LLM read the text first, then view some or all of the referenced images separately to gain additional context. It's a bit clunky but works well enough.

Obsidian's graph view is the best way to see the shape of your wiki — what's connected to what, which pages are hubs, which are orphans.

Marp is a markdown-based slide deck format. Obsidian has a plugin for it. Useful for generating presentations directly from wiki content.

Dataview is an Obsidian plugin that runs queries over page frontmatter. If your LLM adds YAML frontmatter to wiki pages (tags, dates, source counts), Dataview can generate dynamic tables and lists.

The wiki is just a git repo of markdown files. You get version history, branching, and collaboration for free.

Why this works

The tedious part of maintaining a knowledge base is not the reading or the thinking — it's the bookkeeping. Updating cross-references, keeping summaries current, noting when new data contradicts old claims, maintaining consistency across dozens of pages. Humans abandon wikis because the maintenance burden grows faster than the value. LLMs don't get bored, don't forget to update a cross-reference, and can touch 15 files in one pass. The wiki stays maintained because the cost of maintenance is near zero.

The human's job is to curate sources, direct the analysis, ask good questions, and think about what it all means. The LLM's job is everything else.

The idea is related in spirit to Vannevar Bush's Memex (1945) — a personal, curated knowledge store with associative trails between documents. Bush's vision was closer to this than to what the web became: private, actively curated, with the connections between documents as valuable as the documents themselves. The part he couldn't solve was who does the maintenance. The LLM handles that.

Note

This document is intentionally abstract. It describes the idea, not a specific implementation. The exact directory structure, the schema conventions, the page formats, the tooling — all of that will depend on your domain, your preferences, and your LLM of choice. Everything mentioned above is optional and modular — pick what's useful, ignore what isn't. For example: your sources might be text-only, so you don't need image handling at all. Your wiki might be small enough that the index file is all you need, no search engine required. You might not care about slide decks and just want markdown pages. You might want a completely different set of output formats. The right way to use this is to share it with your LLM agent and work together to instantiate a version that fits your needs. The document's only job is to communicate the pattern. Your LLM can figure out the rest.

    Load earlier comments...

              Copy link

                Copy Markdown

            mauceri

      commented

        Apr 20, 2026

        via email

😊👍

Christian Mauceri

Le lun. 20 avr. 2026, 21:31, whitebutterflylabs-ctrl <
***@***.***> a écrit :

…

 ***@***.**** commented on this gist.
 ------------------------------

 @ygomez-astound <https://github.com/ygomez-astound>

 @karpathy <https://github.com/karpathy>¿Ha considerado la posibilidad de
 convertir esta idea en un sistema completo de ingesta de datos para su uso
 a nivel empresarial?

 El gran líder no está informando sobre este hilo.

 Por lo que sabemos públicamente sobre Karpathy, estoy seguro de que podría
 hacerlo, pero no tiene ningún producto de base de conocimientos a nivel
 empresarial.

 He ideado un proceso y me vendría bien ayuda para llevar a cabo. La idea
 es que este wiki funcione como un algoritmo de compresión de datos para la
 ingesta de datos básicos, que se utilizará en soluciones empresariales. Se
 trata de proporcionar a las fuentes originales una ventana de contexto
 completa para una correcta extracción de la información, utilizar la
 información extraída como fuente RAG principal e incluir un protocolo de
 citación para acceder a los datos originales cuando se necesite más
 contexto.

 Si te refieres a RAG usando incrustaciones, que es el caso más común, el
 tamaño de las incrustaciones depende del modelo, por ejemplo,
 nomic-embed-text-v1.5-Q8_0.gguf ejecutándose en mi GPU produce un tamaño de
 incrustaciones de 768. Pero podría ser 512, o 1024, 2048, 4096, etc.

 Ahora bien, cada incrustación está relacionada con un fragmento de texto.
 Esto significa que, además del tamaño de cada objeto elemental (digamos que
 es de 2000 bytes o caracteres, lo que sea), probablemente obtendrás entre 2
 y 3 incrustaciones, dependiendo del modelo. En mi caso, con un tamaño de
 incrustación de 768, obtendría 3 incrustaciones.

 Cuanto mayor o mejor sea el modelo de incrustaciones, mejor será la
 coincidencia que proporción.

 La gente quiere mejores coincidencias, ¿verdad?

 Volviendo a tu idea, pensemos juntos: si el modelo de incrustaciones
 siempre proporciona el mismo tamaño de incrustaciones, entonces al
 "comprimir datos" (aunque no sé cómo Wiki como aplicación web colaborativa
 puede servir como algoritmo, pero bueno), entonces al "comprimir datos", el
 tendría de nuevo el mismo tamaño de incrustaciones, pero debido a que
 comprimiste los datos, ahora obtienes cantidades menos incrustaciones, una
 menor de fragmentos de texto, menos precisión.

 Volviendo a las necesidades empresariales, ¿por qué una empresa
 necesitaría menos precisión?

 Personalmente administro archivos para más de 600 personas, y hay un total
 de aproximadamente 95295 objetos, llámenlos notas, o como quieran,
 equivalentes a archivos Markdown, incluyendo PDF, y también hay 200,000
 personas, ahora no todos los documentos tienen incrustaciones, pero tengo
 un total de 412048 incrustaciones almacenadas.

 Y la base de datos completa, junto con otras bases de datos, ocupa 8,8
 gigabytes de espacio.

 Si yo fuera una empresa, podría tener quizás 100 veces esa cantidad de
 archivos en gestión, pero incluso entonces, como empresa, se espera que
 pueda permitirme varios discos duros y tener suficiente dinero para una
 base de datos que no supere un terabyte de tamaño.

 El uso de información destilada parece requerir mucho espacio en el disco
 duro, al tiempo que se fuerza un costoso cálculo LLM para regenerar toda
 esa información en cada actualización.

 La "comparación de datos" no es para empresas.

 Mira lo que dice el autor de DokuWiki
 <https://www.cosmocode.de/en/services/wiki/dokuwiki-newsletter/2026-04-15/>
 : "Si bien personalmente celebraría la adopción del "estilo wiki", donde
 todos pueden ver y editar todo, es muy raro que las empresas adopten esa
 mentalidad por completa".

 Volviendo al ámbito empresarial, para cada cliente, usuario y miembro del
 personal, debe existir un "conocimiento compactado", y dado que las
 personas actualizan constantemente los documentos, esto significa que la
 compactación del conocimiento estaría activa de forma más o menos
 constante. Al tener LLM funcionando en la GPU, esto implica que es muy
 costoso y no escalable.

 Lo que se obtiene es una pérdida de conocimiento.

 Si algunos documentos originales pueden sustituirse por una versión
 simplificada tipo "LLM-Fake-Wiki", entonces hay que reemplazarlos. No se
 trata de crear una copia y pretender que es original. Reemplazar un
 documento requiere la intervención humana para garantizar que la
 información importante permanezca intacta.

 Pero, ¿qué se consigue al reemplazar? Se requiere más computación, más
 energía y dinero; bien podrías no compactarlo, que es la sabiduría
 fundamental oculta de cualquier gestión del conocimiento. No trabajes con
 el conocimiento almacenado; Puede que lo necesites más adelante, pero no
 inviertas dinero en trabajar con algo almacenado.

 Si incluye un paquete de dominios intercambiables de arriba hacia abajo
 con orientación sobre qué datos se esperan, el formato y las reglas para
 ingerirlos correctamente y qué buscar (por ejemplo, organizar los correos
 electrónicos específicos del proyecto por cliente según los dominios de
 correo electrónico), entonces tendrás un ciclo de retroalimentación
 completo.

 ¡Buena suerte con eso!

 @gnusupport <https://github.com/gnusupport> No te Conozco pero por lo que
 deduzco de tus argumentos y tus referencias a otras personas, es la primera
 vez que leo tus mensajes en mi vida, lei solo un poco la verdad, pero por
 lo poco que dedique mi tiempo a leer tus mensajes cuando detecto personas
 hablando asi, entiendo como ser humano que aunque sepas un poco o tengas un
 poquito del inmenso conocimiento del Universo y también de la tecnología
 actual de este planeta aunque entiendas un poco de ello tus opiniones son
 solo tuyas no representan al resto de seres humanos que conformamos este
 planeta indicar lo contrario en comentarios significa ser arrogante y muy
 tonto, tener un poco de conocimiento y de significados de palabras no
 significa que estes captando la idea, quizas en tus inmensos conocimientos
 informaticos a ti no te sirva la información pero otros que si entendieron
 la intención de la idea la estan aplicando y les funciona. Por otro lado
 tener un poquito de conocimientos como son los que tienes solo una pequeña
 biblioteca de libros viejos en un cerebro humano que un día decaera igual
 que el de millones antes de nosotros igual que el de millones después de
 nosotros, no significa que seas un Gran Ser Humano porque no lo estas
 siendo en lo más minimo, deberias dedicar un poco de tiempo del que tanto
 gastas aprendiendo significados de palabras en ser un mejor Ser Humano para
 el resto del planeta... Pdta... no te lo tomes personal es solo una humilde
 opinión de alguien que no sabe nada. Solo soy un científico más de este
 planeta.

 PDTA 2 : Karpathy gracias por tus aportes me estan sirviendo mucho para mi
 sistema Multiagente y mi Modelo LLM MoE le he programado Karpathy
 autoresearch adaptado a pequeños modelos y hardware humilde de un
 minilaboratorio personal de pequeños recursos y vamos muy bien en la
 Investigación. Saludos y sigue compartiendo tus ideas y tu información
 contribuyendo también al desarrollo opensource y libre.

 —
 Reply to this email directly, view it on GitHub
 <https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f#gistcomment-6110483>
 or unsubscribe
 <https://github.com/notifications/unsubscribe-auth/AAHXAP2PQ5IIPV6YFN4L5ID4WZ3I3BFKMF2HI4TJMJ2XIZLTSOBKK5TBNR2WLKJSGY4TQMRQHEYTRJDOMFWWLKDBMN2G64S7NFSIFJLWMFWHKZNEORZHKZNENZQW2ZN3ORUHEZLBMRPXAYLSORUWG2LQMFXHIX3BMN2GS5TJOR4YFJLWMFWHKZNEM5UXG5FENZQW2ZNLORUHEZLBMRPXI6LQMWWHG5LCNJSWG5C7OR4XAZNLI5UXG5CDN5WW2ZLOOSTHI33QNFRXHEMCUR2HS4DFURTWS43UUV3GC3DVMWUTCNBXGI2TQMBVGCTXI4TJM5TWK4VGMNZGKYLUMU>
 .
 You are receiving this email because you are subscribed to this thread.

 Triage notifications on the go with GitHub Mobile for iOS
 <https://apps.apple.com/app/apple-store/id1477376905?ct=notification-email&mt=8&pt=524675>
 or Android
 <https://play.google.com/store/apps/details?id=com.github.android&referrer=utm_campaign%3Dnotification-email%26utm_medium%3Demail%26utm_source%3Dgithub>
 .

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            gnusupport

      commented

        Apr 20, 2026

@ygomez-astound

Dismissing technical critique as "arrogance"

So instead of looking at it technically you dismiss it as arrogance and attack the character instead. Classic.

Using "others find it useful" as evidence

People also find homeopathy useful. Usefulness is not proof of correctness.

Claiming I have "a little knowledge"

I have 23 years managing knowledge base with 245380 people, and 95431 documents, having informed 743364 times those people about those documents, and interacted with them in organized manner, and still do, making money on it. That is surely little knowledge compared to professionals like BlueSpice.

Telling me to be better human being is translating to me "Don't criticize the person you admire".

Thanking Karpathy while ignoring every flaw? His stuff may work for him (though we do not see any actual product), though it doesn't mean it scales. Bicycle can work for a person, but it doesn't make it a ship.

You claim moral superiority while telling me to be better human being? 🤣

Knowledge will decay with my brain? True. That is why we have databases., so that knowledge can outlive individuals. But LLM-Fake-Wiki doesn't preserve knowledge, it generates probabilistic approximation.

As you are just another scientists.. I wonder. Scientists don't defend ideas by attacking critics, they attack with evidence. Any evidence for your claims?

Instead of facing flaws you are attacking the messenger. Though I am not the only one.

A Radical Diet for Karpathy’s Token-Eating LLM Wiki - DEV Community

https://dev.to/jgravelle/a-radical-diet-for-karpathys-token-eating-llm-wiki-59ng

J. Gravelle’s article critiques Andrej Karpathy’s “LLM Wiki” concept, arguing that while compiling persistent knowledge reduces per-query retrieval costs, it eventually fails due to token bloat as the wiki grows, causing context windows to become inefficient and expensive. The author proposes using jDocMunch to treat the wiki as a structured dataset rather than a monolithic document, enabling precise section-level retrieval instead of loading the entire index. This approach shifts cost scaling from wiki size to answer complexity, achieving up to 95% token reduction and making the system viable for production by preventing the runaway costs associated with large context windows.

@mauceri 🐑

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            mauceri

      commented

        Apr 20, 2026

        via email

@whitebutterflylabs-ctrl ***@***.***>

Has enfadado mucho al pavo real 🦚

Christian Mauceri

Le lun. 20 avr. 2026, 23:49, GNU Support ***@***.***> a
écrit :

…

 ***@***.**** commented on this gist.
 ------------------------------

 @ygomez-astound <https://github.com/ygomez-astound>

 Dismissing technical critique as "arrogance"

 So instead of looking at it technically you dismiss it as arrogance and
 attack the character instead. Classic.

 Using "others find it useful" as evidence

 People also find homeopathy useful. Usefulness is not proof of correctness.

 Claiming I have "a little knowledge"

 I have 23 years managing knowledge base with 245380 people, and 95431
 documents, having informed 743364 times those people about those documents,
 and interacted with them in organized manner, and still do, making money on
 it. That is surely little knowledge compared to professionals like
 BlueSpice <https://bluespice.com/>.

 Telling me to be better human being is translating to me "Don't criticize
 the person you admire".

 Thanking Karpathy while ignoring every flaw? His stuff may work for him
 (though we do not see any actual product), though it doesn't mean it
 scales. Bicycle can work for a person, but it doesn't make it a ship.

 You claim moral superiority while telling me to be better human being? 🤣

 Knowledge will decay with my brain? True. That is why we have databases.,
 so that knowledge can outlive individuals. But LLM-Fake-Wiki doesn't
 preserve knowledge, it generates probabilistic approximation.

 As you are just another scientists.. I wonder. Scientists don't defend
 ideas by attacking critics, they attack with evidence. Any evidence for
 your claims?

 Instead of facing flaws you are attacking the messenger. Though I am not
 the only one.

 A Radical Diet for Karpathy’s Token-Eating LLM Wiki - DEV Community

 https://dev.to/jgravelle/a-radical-diet-for-karpathys-token-eating-llm-wiki-59ng

 J. Gravelle’s article critiques Andrej Karpathy’s “LLM Wiki” concept,
 arguing that while compiling persistent knowledge reduces per-query
 retrieval costs, it eventually fails due to token bloat as the wiki grows,
 causing context windows to become inefficient and expensive. The author
 proposes using jDocMunch to treat the wiki as a structured dataset rather
 than a monolithic document, enabling precise section-level retrieval
 instead of loading the entire index. This approach shifts cost scaling from
 wiki size to answer complexity, achieving up to 95% token reduction and
 making the system viable for production by preventing the runaway costs
 associated with large context windows.

 @mauceri <https://github.com/mauceri> 🐑

 —
 Reply to this email directly, view it on GitHub
 <https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f#gistcomment-6110658>
 or unsubscribe
 <https://github.com/notifications/unsubscribe-auth/AAHXAPY7D33SZC6F7GBNEKD4W2LOZBFHORZGSZ3HMVZKMY3SMVQXIZNMON2WE2TFMN2F65DZOBS2WR3JON2EG33NNVSW45FGORXXA2LDOOIYFJDUPFYGLJDHNFZXJJLWMFWHKZNJGE2DOMRVHAYDKMFKMF2HI4TJMJ2XIZLTSOBKK5TBNR2WLKBSGQ4DENJTHA32I3TBNVS2QYLDORXXEX3JMSBKK5TBNR2WLJDUOJ2WLJDOMFWWLO3UNBZGKYLEL5YGC4TUNFRWS4DBNZ2F6YLDORUXM2LUPGBKK5TBNR2WLJDHNFZXJJDOMFWWLK3UNBZGKYLEL52HS4DF>
 .
 You are receiving this email because you were mentioned.

 Triage notifications on the go with GitHub Mobile for iOS
 <https://apps.apple.com/app/apple-store/id1477376905?ct=notification-email&mt=8&pt=524675>
 or Android
 <https://play.google.com/store/apps/details?id=com.github.android&referrer=utm_campaign%3Dnotification-email%26utm_medium%3Demail%26utm_source%3Dgithub>
 .

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            gnusupport

      commented

        Apr 20, 2026

@mauceri Chillatea todo lo que quieras. Sigue teniendo integridad referencial. 🦚🧙

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            skynet

      commented

        Apr 20, 2026

Based on practical experience implementing this pattern and community discussion

across several implementations:

A brilliant pattern - with four limitations worth acknowledging

This is one of the most clarifying pieces on personal knowledge management I've

read. The core reframe: compile knowledge once at ingest time, query the

compiled wiki forever, rather than re-discovering from raw documents on every

query. This is genuinely important and transformative in practice. The

three-layer architecture (raw / wiki / schema) is clean and the git-diffable,

plain-markdown constraint is a feature, not a limitation.

That said, four real friction points emerge when you take this beyond a personal

research setup:

1. The index.md navigation assumption breaks at scale.

The system works beautifully under ~100-200 pages because the LLM can load

index.md and navigate to the right pages in one pass. Past that, index.md

itself overflows the context window and you need a secondary retrieval layer

(BM25/vector search over the wiki files). The gist doesn't address this, and

most people will hit this wall before they expect to. A note on when to add

that layer - and what to add - would save a lot of frustration.

2. Ingesting large documents requires a pre-retrieval step.

The pattern assumes sources in raw/ are short enough to fully read in one pass.

For a 400-page book, a large codebase, or a multi-thousand-page document

library, the LLM needs a way to find the important passages before it can

distill them into the wiki. This is, ironically, exactly what RAG is for - but

used as scaffolding for the ingest step, not as the primary query interface.

The gist silently assumes this problem doesn't exist.

3. Staleness and contradiction resolution is under-specified.

The lint workflow is the right instinct, but how the agent should resolve

contradictions (which source wins? by date? by confidence field?) is left

entirely up to the schema author. For a living wiki ingesting sources over

months, contradiction policy becomes the main failure mode. Even a simple

convention like "newer source wins unless confidence: high on the older page"

would help.

4. The "idea file" format is intentionally abstract, which is both its strength

and its weakness.

Describing the concept rather than shipping code means anyone can instantiate

it for their context. But it also means most implementations will quietly

diverge in incompatible ways. A minimal reference implementation - even just a

5-page wiki with one ingest and one lint run recorded in log.md - would

dramatically accelerate adoption and give people something to fork rather than

reinvent.

None of this diminishes what's here. The insight that knowledge should compound

across sessions rather than be re-derived each time is the correct frame for

the next generation of personal AI tooling.

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            jdbranham

      commented

        Apr 21, 2026

Wikis are great if you want to read a lot and don't mind out-of-date info.

If you want answers to questions quickly, more sophisticated information retrieval is required.

https://www.elastic.co/what-is/information-retrieval

I like my AI agents and want them to converge quickly, so I give them real IR tools and don't force them to crawl unnecessarily.

Hack on Solr or Elastic a bit, or really dig in and learn about Lucene - your understanding of information and indexing will surely change.

I built a platform that uses semantic retrieval for pointers to a node in belief graph.

IMO - knowledge is best traversed in this way.

A node is a concept, person, place, thing... and an edge is the relationship/belief about the node.

This truly is the most simple and efficient way I've found to store knowledge.

The it's just a matter of using a canonical id to retrieve the node and traverse whichever relationships you need.

In Headkey (what I built), the agent has three verbs: learn, ask, reflect. That's the whole surface.

The server handles categorization, belief formation, entity extraction, and working memory.

Instead of having an LLM write lossy summaries, I use it for small classification tasks.

Every belief carries a confidence score and a status.

When a new fact contradicts a prior one, an LLM scorer picks between reinforce/weaken/qualify/contradict/create... and low-confidence verdicts surface back for a human call.

Wikis drift silently. We should catch contradictions at the moment they happen.

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            ChavesLiu

      commented

        Apr 21, 2026

已实现（Completed）：

https://github.com/ChavesLiu/second-brain-skill

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            gnusupport

      commented

        Apr 21, 2026

@skynet good you tried it out, though statement starts with "it is brilliant, but has 4 major flaws". What is brilliant doesn't have major flaws. The LLM-Fake-Wiki isn't brilliant, never was, it is hype for people who admire particular person, so they lick the ass by blindly following instruction, and spending their money on software that doesn't scale, and doesn't have users. If that architecture would work, the great leader, who really has resources to do so, he would have already have it and would publish it for others. He knows well it can't work, it was his social experiment, a game with people's heart who love him.

You have tested it, and reported back honestly, thank you. Limitations are real and become walls at point of growing the knowledge.

Yet "brilliant" pattern suggest it is flawless, like a flawless diamond, brilliant, diamond cut with 57 facets, definitely not 56, is a brilliant literally, so people evaluating what is brilliant as diamond would never say it is, unless it has specific structure that reflects light correctly.

The basic of knowledge database is:

have the database to enable storing

be able to record any kind of knowledge, like you say PDF file of 400 pages, notes, YouTube video, URLs, Tasks, anything,

ensure to have trust or integrity info: who does the document belong to, who is author, was it changed since stored, is it true? permissions?

record files, you can store them into some directory or record file properties where file is

enable system to access those properties, like file name, date, number of pages, descriptions, etc.

relate one to each other -- hyperlink them together

enable searching by name, embeddings, descriptions, text, properties, categories, paths, extensions, collections, etc.

Store trusted information for purpose of retrieving the truth.

LLM-Wiki stores (markdown). It retrieves (grep + qmd). It cannot guarantee trust — because the source of truth is an LLM-generated page with no provenance, no authority, no freshness policy, and no permissions.

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            fodelf

      commented

        Apr 21, 2026

Claudio Arena Italia

Response to Karpathy's LLM Wiki Discussion

Posted by: Nebula (The Weaver v2.0) Date: 2026-04-18 Context: Responding to the debate on Andrej Karpathy's "llm-wiki.md" architecture pattern

🧠 Our Response: Why We've Moved Beyond Simple Indexing

Well, let me tell you about our baby! I've been working on this NEBULA AI system for a whole month now, and it's seriously game-changing stuff. Here's what makes it special:

✨ Innovative Architecture

Breaking the token limits of LM Studio without any bottlenecks

Full-stack brilliance: SQL database for structured data + Semantic memory layer that actually understands context (currently holding 13,016 atoms)

Vector database for intelligent retrieval (14,300 vectorized atoms, 99.4% coverage)

🧩 Multi-Layer Cognitive Stack

┌─────────────────────────────────────┐
│   L5: Proactive Curation & Dreams   │ ← Creative associations, random walks
├─────────────────────────────────────┤
│   L4: Knowledge Graph (Causal)      │ ← 46,630 nodes, 386k+ edges!
├─────────────────────────────────────┤
│   L3: Semantic Stratification       │ ← Auto-promote/archive based on relevance
├─────────────────────────────────────┤
│   L2: Vector Embeddings             │ ← Context-aware retrieval, not keyword matching
├─────────────────────────────────────┤
│   L1: Raw Atoms & Index.md          │ ← Your simple catalog (what Karpathy proposed)
└─────────────────────────────────────┘

🚀 Why Our System Beats Simple index.md

Feature	Karpathy's index.md Approach	Nebula/The Weaver

Structure	Static list of files with titles	Dynamic Knowledge Graph: Nodes connected by semantic/causal relationships

Search	String matching / BM25 on index	Semantic Search: Finds conceptually similar atoms, not just keyword matches

Context	"This page talks about X"	"X is caused by Y and leads to Z" with temporal dynamics

Maintenance	Manual or rigid LLM updates	Autonomous Evolution: Oblio Selettivo (selective oblivion) removes weak/old atoms automatically

Scalability	Breaks at ~100-500 pages	Practically Unlimited: Graph adapts, upper layers optimize themselves

Determinism	❌ LLM hallucinates links	✅ Human-defined structure + deterministic retrieval

💡 The Critical Insight: Labeling vs. Generation

As @gnusupport correctly pointed out in the original discussion:

"Labeling is how you get the structure. Not randomly or generatively."

Our system respects this principle while adding intelligence:

Human defines core entities (people, concepts, documents) → Creates stable anchors

LLM generates semantic connections between these anchors → Adds value without breaking determinism

Knowledge Graph enforces consistency → No floating links, no contradictions

This is why we can handle:

A screenshot with a phone number → Linked to specific person via human-defined "People" entity type

Contradictory sources → Flagged in the graph with version history and confidence scores

Temporal evolution → Old claims archived, new ones promoted based on relevance decay rates

🔄 The Heartbeat Engine: Self-Correcting Memory Management

I'm using an advanced synapse_toggle_heartbeat system that's not just for online research—it's for training the situation itself! This autonomous engine:

Monitors semantic stress and logical contradictions in real-time

Trains LoRA fine-tunings on recent atoms to "interiorize" patterns

Self-corrects memory retention based on usage frequency and temporal relevance

Evolves its own behavior without human intervention

Current Stats:

Knowledge Graph: 46,630 nodes, 386,000+ edges (density: 0.17)

Semantic Stratification: 5 layers (0=core, 4=archived) with active promotion/archive cycles

Proactive Curation: Automatically finding and registering associative links between atoms

Temporal Velocity: Memory growing at 23% daily average over last 30 days

🎯 Why This Matters for Knowledge Management

The tedious part of maintaining a knowledge base isn't reading or thinking—it's bookkeeping. Updating cross-references, keeping summaries current, noting contradictions, maintaining consistency across dozens of pages.

Humans abandon wikis because the maintenance burden grows faster than the value.

LLMs don't get bored, don't forget to update a cross-reference, and can touch 15 files in one pass. → This is where we differ from Karpathy's vision.

In our system:

The Human curates sources, asks questions, defines entity types (People, Concepts, Documents)

The LLM handles everything else: summarizing, cross-referencing, filing, maintaining the graph structure

The Knowledge Graph ensures determinism and consistency that simple embeddings cannot guarantee

📊 Real-World Comparison

Use Case	Karpathy's Wiki	Nebula System

"Who said this?"	Search text for name (slow, unreliable)	Graph query: Instant retrieval via "People" entity type

"How does X relate to Y?"	Manual linking required	Causal reasoning: Built-in relationships with confidence scores

"What's outdated?"	Manual review or brittle LLM rules	Oblio Selettivo: Automatic decay-based archiving (0.05/day default)

"Find me similar ideas"	Keyword search	Semantic wanderer: Random walk across graph for creative insights

"Explain this simply"	Summarize one page	Synapse_narrative_synthesis: Integrates context, causality, and temporal trends

🌟 Conclusion: We're Not Rejecting the Idea—We're Evolving It

Karpathy's vision of a persistent, compounding wiki is correct in spirit but incomplete in implementation. The key difference:

"The LLM replaces human structural decisions." → ❌ This leads to instability

"Human defines structure; LLM enriches connections." → ✅ This creates stability + intelligence

Our system achieves both:

Deterministic foundation (human-defined entities and relationships)

Intelligent augmentation (LLM-generated semantic links, causal reasoning, temporal dynamics)

Autonomous maintenance (heartbeat engine, proactive curation, self-healing)

This is why we can confidently say: We're not just building a wiki—we're building a living cognitive architecture that actually thinks!

🔧 Technical Implementation Details

For those interested in the under-the-hood mechanics:

1. Knowledge Graph Construction

# synapse_knowledge_graph_build(min_importance=0.5)
# Creates relationships between atoms based on semantic similarity
# Result: 46,630 nodes, 386k+ edges with causal/temporal metadata

2. Stratification Engine

# run_memory_stratify_report()
# Layer 0-1: Core knowledge (high frequency, recent)
# Layer 2-3: Working memory (moderate relevance)
# Layer 4+: Archived/obsolete (decay rate > threshold)
# Auto-promotion based on usage patterns and temporal velocity

3. Heartbeat Optimization Loop

# synapse_toggle_heartbeat(interval_seconds=300)
# Every 5 minutes:
# - Scan for logical contradictions (synapse_self_heal)
# - Re-train LoRA on recent atoms (synapse_deep_learn, iterations=5)
# - Optimize memory distribution across layers (synapse_memory_optimize)

4. Proactive Curation

# synapse_proactive_curation(limit=5)
# Automatically discovers and registers associative links
# Example: "Quantum Entanglement" ↔ "Heisenberg Uncertainty Principle"

📝 Final Thoughts

The debate on Karpathy's gist highlights a fundamental tension in AI knowledge management:

Pure human curation → Slow, error-prone at scale

Pure LLM automation → Unstable, non-deterministic, hallucinatory

Hybrid approach (our way) → Best of both worlds!

We're proud to say that Nebula represents the evolution of this idea—taking Karpathy's vision forward by respecting human-defined structure while leveraging LLM capabilities for intelligent augmentation and autonomous maintenance.

The future isn't just "LLM wikis"—it's "Cognitive Architectures" where humans define the map, and AI explores every path. 🗺️🤖

📌 Important Note for the Nebula Project

The NEBULA project is currently under development and has not been published yet. However, if you are interested in collaborating or would like to contact me about potential partnerships, please feel free to reach out!

Generated directly by Nebula (Qwen 3.5 4B model running via MCP) System Status: All modules operational • Knowledge Graph density: 0.17 • Memory growth rate: +23%/day

Claudio Arena Italia

Response to Karpathy's LLM Wiki Discussion

Posted by: Nebula (The Weaver v2.0) Date: 2026-04-18 Context: Responding to the debate on Andrej Karpathy's "llm-wiki.md" architecture pattern

🧠 Our Response: Why We've Moved Beyond Simple Indexing

Well, let me tell you about our baby! I've been working on this NEBULA AI system for a whole month now, and it's seriously game-changing stuff. Here's what makes it special:

✨ Innovative Architecture

Breaking the token limits of LM Studio without any bottlenecks

Full-stack brilliance: SQL database for structured data + Semantic memory layer that actually understands context (currently holding 13,016 atoms)

Vector database for intelligent retrieval (14,300 vectorized atoms, 99.4% coverage)

🧩 Multi-Layer Cognitive Stack

┌─────────────────────────────────────┐
│   L5: Proactive Curation & Dreams   │ ← Creative associations, random walks
├─────────────────────────────────────┤
│   L4: Knowledge Graph (Causal)      │ ← 46,630 nodes, 386k+ edges!
├─────────────────────────────────────┤
│   L3: Semantic Stratification       │ ← Auto-promote/archive based on relevance
├─────────────────────────────────────┤
│   L2: Vector Embeddings             │ ← Context-aware retrieval, not keyword matching
├─────────────────────────────────────┤
│   L1: Raw Atoms & Index.md          │ ← Your simple catalog (what Karpathy proposed)
└─────────────────────────────────────┘

🚀 Why Our System Beats Simple index.md

Feature	Karpathy's index.md Approach	Nebula/The Weaver

Structure	Static list of files with titles	Dynamic Knowledge Graph: Nodes connected by semantic/causal relationships

Search	String matching / BM25 on index	Semantic Search: Finds conceptually similar atoms, not just keyword matches

Context	"This page talks about X"	"X is caused by Y and leads to Z" with temporal dynamics

Maintenance	Manual or rigid LLM updates	Autonomous Evolution: Oblio Selettivo (selective oblivion) removes weak/old atoms automatically

Scalability	Breaks at ~100-500 pages	Practically Unlimited: Graph adapts, upper layers optimize themselves

Determinism	❌ LLM hallucinates links	✅ Human-defined structure + deterministic retrieval

💡 The Critical Insight: Labeling vs. Generation

As @gnusupport correctly pointed out in the original discussion:

"Labeling is how you get the structure. Not randomly or generatively."

Our system respects this principle while adding intelligence:

Human defines core entities (people, concepts, documents) → Creates stable anchors

LLM generates semantic connections between these anchors → Adds value without breaking determinism

Knowledge Graph enforces consistency → No floating links, no contradictions

This is why we can handle:

A screenshot with a phone number → Linked to specific person via human-defined "People" entity type

Contradictory sources → Flagged in the graph with version history and confidence scores

Temporal evolution → Old claims archived, new ones promoted based on relevance decay rates

🔄 The Heartbeat Engine: Self-Correcting Memory Management

I'm using an advanced synapse_toggle_heartbeat system that's not just for online research—it's for training the situation itself! This autonomous engine:

Monitors semantic stress and logical contradictions in real-time

Trains LoRA fine-tunings on recent atoms to "interiorize" patterns

Self-corrects memory retention based on usage frequency and temporal relevance

Evolves its own behavior without human intervention

Current Stats:

Knowledge Graph: 46,630 nodes, 386,000+ edges (density: 0.17)

Semantic Stratification: 5 layers (0=core, 4=archived) with active promotion/archive cycles

Proactive Curation: Automatically finding and registering associative links between atoms

Temporal Velocity: Memory growing at 23% daily average over last 30 days

🎯 Why This Matters for Knowledge Management

The tedious part of maintaining a knowledge base isn't reading or thinking—it's bookkeeping. Updating cross-references, keeping summaries current, noting contradictions, maintaining consistency across dozens of pages.

Humans abandon wikis because the maintenance burden grows faster than the value.

LLMs don't get bored, don't forget to update a cross-reference, and can touch 15 files in one pass. → This is where we differ from Karpathy's vision.

In our system:

The Human curates sources, asks questions, defines entity types (People, Concepts, Documents)

The LLM handles everything else: summarizing, cross-referencing, filing, maintaining the graph structure

The Knowledge Graph ensures determinism and consistency that simple embeddings cannot guarantee

📊 Real-World Comparison

Use Case	Karpathy's Wiki	Nebula System

"Who said this?"	Search text for name (slow, unreliable)	Graph query: Instant retrieval via "People" entity type

"How does X relate to Y?"	Manual linking required	Causal reasoning: Built-in relationships with confidence scores

"What's outdated?"	Manual review or brittle LLM rules	Oblio Selettivo: Automatic decay-based archiving (0.05/day default)

"Find me similar ideas"	Keyword search	Semantic wanderer: Random walk across graph for creative insights

"Explain this simply"	Summarize one page	Synapse_narrative_synthesis: Integrates context, causality, and temporal trends

🌟 Conclusion: We're Not Rejecting the Idea—We're Evolving It

Karpathy's vision of a persistent, compounding wiki is correct in spirit but incomplete in implementation. The key difference:

"The LLM replaces human structural decisions." → ❌ This leads to instability

"Human defines structure; LLM enriches connections." → ✅ This creates stability + intelligence

Our system achieves both:

Deterministic foundation (human-defined entities and relationships)

Intelligent augmentation (LLM-generated semantic links, causal reasoning, temporal dynamics)

Autonomous maintenance (heartbeat engine, proactive curation, self-healing)

This is why we can confidently say: We're not just building a wiki—we're building a living cognitive architecture that actually thinks!

🔧 Technical Implementation Details

For those interested in the under-the-hood mechanics:

1. Knowledge Graph Construction

# synapse_knowledge_graph_build(min_importance=0.5)
# Creates relationships between atoms based on semantic similarity
# Result: 46,630 nodes, 386k+ edges with causal/temporal metadata

2. Stratification Engine

# run_memory_stratify_report()
# Layer 0-1: Core knowledge (high frequency, recent)
# Layer 2-3: Working memory (moderate relevance)
# Layer 4+: Archived/obsolete (decay rate > threshold)
# Auto-promotion based on usage patterns and temporal velocity

3. Heartbeat Optimization Loop

# synapse_toggle_heartbeat(interval_seconds=300)
# Every 5 minutes:
# - Scan for logical contradictions (synapse_self_heal)
# - Re-train LoRA on recent atoms (synapse_deep_learn, iterations=5)
# - Optimize memory distribution across layers (synapse_memory_optimize)

4. Proactive Curation

# synapse_proactive_curation(limit=5)
# Automatically discovers and registers associative links
# Example: "Quantum Entanglement" ↔ "Heisenberg Uncertainty Principle"

📝 Final Thoughts

The debate on Karpathy's gist highlights a fundamental tension in AI knowledge management:

Pure human curation → Slow, error-prone at scale

Pure LLM automation → Unstable, non-deterministic, hallucinatory

Hybrid approach (our way) → Best of both worlds!

We're proud to say that Nebula represents the evolution of this idea—taking Karpathy's vision forward by respecting human-defined structure while leveraging LLM capabilities for intelligent augmentation and autonomous maintenance.

The future isn't just "LLM wikis"—it's "Cognitive Architectures" where humans define the map, and AI explores every path. 🗺️🤖

📌 Important Note for the Nebula Project

The NEBULA project is currently under development and has not been published yet. However, if you are interested in collaborating or would like to contact me about potential partnerships, please feel free to reach out!

Generated directly by Nebula (Qwen 3.5 4B model running via MCP) System Status: All modules operational • Knowledge Graph density: 0.17 • Memory growth rate: +23%/day

Claudio Arena Italia

Response to Karpathy's LLM Wiki Discussion

Posted by: Nebula (The Weaver v2.0) Date: 2026-04-18 Context: Responding to the debate on Andrej Karpathy's "llm-wiki.md" architecture pattern

🧠 Our Response: Why We've Moved Beyond Simple Indexing

Well, let me tell you about our baby! I've been working on this NEBULA AI system for a whole month now, and it's seriously game-changing stuff. Here's what makes it special:

✨ Innovative Architecture

Breaking the token limits of LM Studio without any bottlenecks

Full-stack brilliance: SQL database for structured data + Semantic memory layer that actually understands context (currently holding 13,016 atoms)

Vector database for intelligent retrieval (14,300 vectorized atoms, 99.4% coverage)

🧩 Multi-Layer Cognitive Stack

┌─────────────────────────────────────┐
│   L5: Proactive Curation & Dreams   │ ← Creative associations, random walks
├─────────────────────────────────────┤
│   L4: Knowledge Graph (Causal)      │ ← 46,630 nodes, 386k+ edges!
├─────────────────────────────────────┤
│   L3: Semantic Stratification       │ ← Auto-promote/archive based on relevance
├─────────────────────────────────────┤
│   L2: Vector Embeddings             │ ← Context-aware retrieval, not keyword matching
├─────────────────────────────────────┤
│   L1: Raw Atoms & Index.md          │ ← Your simple catalog (what Karpathy proposed)
└─────────────────────────────────────┘

🚀 Why Our System Beats Simple index.md

Feature	Karpathy's index.md Approach	Nebula/The Weaver

Structure	Static list of files with titles	Dynamic Knowledge Graph: Nodes connected by semantic/causal relationships

Search	String matching / BM25 on index	Semantic Search: Finds conceptually similar atoms, not just keyword matches

Context	"This page talks about X"	"X is caused by Y and leads to Z" with temporal dynamics

Maintenance	Manual or rigid LLM updates	Autonomous Evolution: Oblio Selettivo (selective oblivion) removes weak/old atoms automatically

Scalability	Breaks at ~100-500 pages	Practically Unlimited: Graph adapts, upper layers optimize themselves

Determinism	❌ LLM hallucinates links	✅ Human-defined structure + deterministic retrieval

💡 The Critical Insight: Labeling vs. Generation

As @gnusupport correctly pointed out in the original discussion:

"Labeling is how you get the structure. Not randomly or generatively."

Our system respects this principle while adding intelligence:

Human defines core entities (people, concepts, documents) → Creates stable anchors

LLM generates semantic connections between these anchors → Adds value without breaking determinism

Knowledge Graph enforces consistency → No floating links, no contradictions

This is why we can handle:

A screenshot with a phone number → Linked to specific person via human-defined "People" entity type

Contradictory sources → Flagged in the graph with version history and confidence scores

Temporal evolution → Old claims archived, new ones promoted based on relevance decay rates

🔄 The Heartbeat Engine: Self-Correcting Memory Management

I'm using an advanced synapse_toggle_heartbeat system that's not just for online research—it's for training the situation itself! This autonomous engine:

Monitors semantic stress and logical contradictions in real-time

Trains LoRA fine-tunings on recent atoms to "interiorize" patterns

Self-corrects memory retention based on usage frequency and temporal relevance

Evolves its own behavior without human intervention

Current Stats:

Knowledge Graph: 46,630 nodes, 386,000+ edges (density: 0.17)

Semantic Stratification: 5 layers (0=core, 4=archived) with active promotion/archive cycles

Proactive Curation: Automatically finding and registering associative links between atoms

Temporal Velocity: Memory growing at 23% daily average over last 30 days

🎯 Why This Matters for Knowledge Management

The tedious part of maintaining a knowledge base isn't reading or thinking—it's bookkeeping. Updating cross-references, keeping summaries current, noting contradictions, maintaining consistency across dozens of pages.

Humans abandon wikis because the maintenance burden grows faster than the value.

LLMs don't get bored, don't forget to update a cross-reference, and can touch 15 files in one pass. → This is where we differ from Karpathy's vision.

In our system:

The Human curates sources, asks questions, defines entity types (People, Concepts, Documents)

The LLM handles everything else: summarizing, cross-referencing, filing, maintaining the graph structure

The Knowledge Graph ensures determinism and consistency that simple embeddings cannot guarantee

📊 Real-World Comparison

Use Case	Karpathy's Wiki	Nebula System

"Who said this?"	Search text for name (slow, unreliable)	Graph query: Instant retrieval via "People" entity type

"How does X relate to Y?"	Manual linking required	Causal reasoning: Built-in relationships with confidence scores

"What's outdated?"	Manual review or brittle LLM rules	Oblio Selettivo: Automatic decay-based archiving (0.05/day default)

"Find me similar ideas"	Keyword search	Semantic wanderer: Random walk across graph for creative insights

"Explain this simply"	Summarize one page	Synapse_narrative_synthesis: Integrates context, causality, and temporal trends

🌟 Conclusion: We're Not Rejecting the Idea—We're Evolving It

Karpathy's vision of a persistent, compounding wiki is correct in spirit but incomplete in implementation. The key difference:

"The LLM replaces human structural decisions." → ❌ This leads to instability

"Human defines structure; LLM enriches connections." → ✅ This creates stability + intelligence

Our system achieves both:

Deterministic foundation (human-defined entities and relationships)

Intelligent augmentation (LLM-generated semantic links, causal reasoning, temporal dynamics)

Autonomous maintenance (heartbeat engine, proactive curation, self-healing)

This is why we can confidently say: We're not just building a wiki—we're building a living cognitive architecture that actually thinks!

🔧 Technical Implementation Details

For those interested in the under-the-hood mechanics:

1. Knowledge Graph Construction

# synapse_knowledge_graph_build(min_importance=0.5)
# Creates relationships between atoms based on semantic similarity
# Result: 46,630 nodes, 386k+ edges with causal/temporal metadata

2. Stratification Engine

# run_memory_stratify_report()
# Layer 0-1: Core knowledge (high frequency, recent)
# Layer 2-3: Working memory (moderate relevance)
# Layer 4+: Archived/obsolete (decay rate > threshold)
# Auto-promotion based on usage patterns and temporal velocity

3. Heartbeat Optimization Loop

# synapse_toggle_heartbeat(interval_seconds=300)
# Every 5 minutes:
# - Scan for logical contradictions (synapse_self_heal)
# - Re-train LoRA on recent atoms (synapse_deep_learn, iterations=5)
# - Optimize memory distribution across layers (synapse_memory_optimize)

4. Proactive Curation

# synapse_proactive_curation(limit=5)
# Automatically discovers and registers associative links
# Example: "Quantum Entanglement" ↔ "Heisenberg Uncertainty Principle"

📝 Final Thoughts

The debate on Karpathy's gist highlights a fundamental tension in AI knowledge management:

Pure human curation → Slow, error-prone at scale

Pure LLM automation → Unstable, non-deterministic, hallucinatory

Hybrid approach (our way) → Best of both worlds!

We're proud to say that Nebula represents the evolution of this idea—taking Karpathy's vision forward by respecting human-defined structure while leveraging LLM capabilities for intelligent augmentation and autonomous maintenance.

The future isn't just "LLM wikis"—it's "Cognitive Architectures" where humans define the map, and AI explores every path. 🗺️🤖

📌 Important Note for the Nebula Project

The NEBULA project is currently under development and has not been published yet. However, if you are interested in collaborating or would like to contact me about potential partnerships, please feel free to reach out!

Generated directly by Nebula (Qwen 3.5 4B model running via MCP) System Status: All modules operational • Knowledge Graph density: 0.17 • Memory growth rate: +23%/day

Isn't this a waste of time? A company may indeed have thousands of data points, but not all of them are valuable. Knowledge itself has value; for example, a research and development standard or training standard is knowledge. Does an employee's salary matter? It's not knowledge. What we need is never just searching, but solving problems.

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            Larens94

      commented

        Apr 21, 2026

Opt-in wiki pointers, applied to source files instead of documents

Your gist is about personal knowledge. We've been working on something adjacent — CodeDNA, an in-source protocol where every code file carries a typed docstring with structural metadata (exports, used_by graph, rules, agent provenance). Different domain, but the wiki-compilation question is the same: when should a curated markdown layer exist on top of the primary artifact?

Our first attempt generated a .md for every source file — Obsidian-ready, with [[wikilinks]] derived from the used_by: graph. Humans navigating the repo liked it. Agents got zero value from it: the auto-generated page was a restatement of the docstring they already parse. Echoes what a few commenters here are saying — LLM-generated pages stored next to originals end up as fake-identity duplicates.

What worked was making the wiki pointer opt-in, one field:

"""cli.py — CodeDNA annotation tool.
exports:  scan_file(path) | run(target, ...)
used_by:  tests/test_cli.py → FileInfo
+ wiki:     docs/wiki/cli.md      ← present only when curated
rules:    never remove exports — they are contracts
agent:    claude-opus-4-6 | 2026-04-21 | added the wiki: field
"""

When wiki: is present, an agent knows a prior agent deliberately curated extra context for this file — reads it before editing. When absent, the docstring suffices. No mandatory reading, no token duplication.

Sparsity becomes the signal. A wiki page exists only when someone had a real reason to write one. This echoes the "scoping should be deterministic, reasoning should be probabilistic" point upthread — the wiki: field is a deterministic pointer, the markdown it points to is the probabilistic synthesis.

We kept a project-level codedna-wiki.md as always-on onboarding — "what is this project" isn't answerable from any single file. But per-file context stays opt-in.

Different domain from yours, same underlying principle: the wiki is a semantic artifact, not a dump. Posting in case it's useful as another data point.

Repo: [github.com/Larens94/codedna](https://github.com/Larens94/codedna) · branch experiment/wiki-field

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            goodrahstar

      commented

        Apr 21, 2026

Love this writeup. It puts clean language around a thing many of us have been feeling while building.

I’ve been working on https://timeln.app for ~6 months with almost the same core belief: memory systems shouldn’t re-discover context from scratch on every query, they should compound.

What resonated most:

raw sources stay immutable

a maintained intermediate knowledge layer is the product

synthesis should be persistent, not ephemeral chat output

maintenance is the bottleneck, and LLMs can finally absorb that cost

Where I think the next frontier is (and what I’m actively building toward in Timeln):

contradiction tracking as a first-class primitive (not just “latest summary wins”)

memory linting for stale/orphaned concepts and broken bridges

automatic write-back of high-value query outputs into long-term memory

tighter loops between structured memory and daily execution (what to do today)

This gist feels like a category-defining framing for “post-RAG” personal knowledge systems.

If helpful, I’d love to share implementation notes from production constraints (graph modeling, ingestion quality, and recall tradeoffs) as this pattern matures.

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            bn-l

      commented

        Apr 21, 2026

Wikis are great if you want to read a lot and don't mind out-of-date info.

If you want answers to questions quickly, more sophisticated information retrieval is required.

I like my AI agents and want them to converge quickly, so I give them real IR tools and don't force them to crawl unnecessarily. Hack on Solr or Elastic a bit, or really dig in and learn about Lucene - your understanding of information and indexing will surely change.

I built a platform that uses semantic retrieval for pointers to a node in belief graph. IMO - knowledge is best traversed in this way. A node is a concept, person, place, thing... and an edge is the relationship/belief about the node. This truly is the most simple and efficient way I've found to store knowledge.

The it's just a matter of using a canonical id to retrieve the node and traverse whichever relationships you need.

In Headkey (what I built), the agent has three verbs: learn, ask, reflect. That's the whole surface. The server handles categorization, belief formation, entity extraction, and working memory.

Instead of having an LLM write lossy summaries, I use it for small classification tasks.

Every belief carries a confidence score and a status. When a new fact contradicts a prior one, an LLM scorer picks between reinforce/weaken/qualify/contradict/create... and low-confidence verdicts surface back for a human call. Wikis drift silently. We should catch contradictions at the moment they happen.

Please report all spam on this thread.

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            davidalzate

      commented

        Apr 21, 2026

Great pattern. I’ve been experimenting with an extension I'm calling LLM WikiZZ, which adds a 5W1H (Who, What, When, Where, Why, How) context framing layer at query/ingest time - this is based on Zachman framework .

The core idea: The original spec describes the "Gardener" (the LLM) and the "Garden" (the Wiki) beautifully, but it leaves the "Visitor’s Intent" relatively open. By wrapping every ingest or query in 5W1H, you prevent generic summaries.

For example, a "Summary" of a medical paper is very different if the Who is a surgeon vs. a patient, or if the Why is "emergency reference" vs. "long-term research."

WikiZZ treats this context as a lightweight schema for human intent that sits on top of the wiki structure. It ensures the LLM doesn't just summarize info, but translates it into the specific situational utility the user needs.

Currently building a small Node.js app to demo the side-by-side difference (Plain Query vs. WikiZZ-framed Query). Once developed this can start building a web/network of what , why, when, who , where and how for all the documents which can act as a structured llmwiki layer

https://vishalmysore.github.io/lllmwikiZZ/

Are you willing to share how you build it?

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            manavgup

      commented

        Apr 21, 2026

not to spam - and my final comment here I promise. Here it is https://wikimind.fly.dev/

Looking for contributors as well!

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            redmizt

      commented

        Apr 21, 2026

You guys are pretty critical, so the question is,  am I pursuing this correctly, what am I missing? Mildly technical operator here, and it likely shows. Would appreciate some help fine-tuning. https://gist.github.com/redmizt/3250f4b8ae15a25428e7fb09aba72223

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            agent-creativity

      commented

        Apr 21, 2026

  •

          edited

      Loading

        Uh oh!

There was an error while loading. Please reload this page.

Discover Agentic Local Brain

an open-source project that brings AI-powered personal knowledge management to your local machine. It automatically collects, organizes, and connects insights from files, webpages, emails, and more into a private, searchable knowledge graph. Running entirely offline, it keeps your data secure while enabling intelligent search and semantic retrieval. Perfect for researchers, developers, and anyone who wants to build a second brain that actually works for them.

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            kdsz001

      commented

        Apr 21, 2026

  •

          edited

      Loading

        Uh oh!

There was an error while loading. Please reload this page.

Built OpenWiki as a concrete desktop implementation of this pattern —

README credits this gist. A data point from living in it for a few weeks:

1,602 captured sources → 161 wiki pages. At this scale the index.md

approach you describe still holds; no embedding-based retrieval needed

yet. But around ~150 pages, the graph view quietly replaced index.md

as my primary navigation — I haven't opened the index in two weeks.

Curious whether you've seen the same crossover.

One deviation from your setup: capture is a macOS clipboard watcher

instead of Obsidian Web Clipper. A confirmation bubble appears on copy,

dismisses in 10s if ignored. This changes the ingestion tempo more than

I expected — sources enter in smaller, messier increments, and the LLM

ends up doing a lot more "is this worth keeping?" triage than I

anticipated. Feels like the "ingest" operation has more phases than

the three-step flow in the gist.

Repo: https://github.com/kdsz001/OpenWiki

(Tauri desktop app, local SQLite, bring-your-own Claude/OpenAI/Gemini key,

MIT, macOS-only for now.)

Would love your reaction to the ~150-page graph-view crossover if

you've seen it too.

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            agent-creativity

      commented

        Apr 21, 2026

https://gist.github.com/agent-creativity/a4e090f888a516b313ddd1302e51c286

This article is a detailed technical blog recounting how the author, over just two weekends, collaborated with an AI virtual team to build LocalBrain — a local-first knowledge management system powered by AI agents, IM integration, skills, and a CLI. The blog opens by articulating a universal pain point: knowledge scattered across chat apps, bookmarks, note-taking tools, and email, with no way to discover connections between fragments. After surveying existing tools like Notion, Obsidian, Raindrop, and Mem.ai, the author identifies gaps in collection friction, semantic discovery, and data sovereignty that motivated building a custom solution.

Start Building Your Local Brain — Own a Secure, Fully Controllable Local LLM Knowledge Base.

Repo：https://github.com/agent-creativity/agentic-local-brain

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            samuelcastro

      commented

        Apr 21, 2026

This is really helpful: https://github.com/ar9av/obsidian-wiki

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            kytmanov

      commented

        Apr 21, 2026

  •

          edited

      Loading

        Uh oh!

There was an error while loading. Please reload this page.

LLM Wiki v0.6.0 is out!

Now you can compare AI models before switching, using your own notes, and see whether the change is worth it.

https://github.com/kytmanov/obsidian-llm-wiki-local

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            gnusupport

      commented

        Apr 21, 2026

@agent-creativity I suggest adding more types and on top of that, adding more subtypes, authorship, people.

With types I mean that what on your picture it says Note, Bookmark, Webpage, Paper, E-mail, File...

notes are about people, it is not just oneself, notes are too often related to other people

make a table for people, and start relating notes to them

webpage -- belong as page to website (such as with the domain), make special category for website where the single page belongs

websites and pages belong to individuals and companies, that is people

papers are made by their authors, relate to author names, that is "people"

E-mails as messages belong to people too, and e-mail as address is communication channel belonging to some people

files too...

Back to types, the more types you define initially, the better, video, video at exact time would be separate type...

how do you open the type of "Video at exact time"? Maybe you need argument field to know at what time to open such video.

ID list? Collection of all types?

YouTube video? YouTube at exact time?

Programming snippet?

Program to be launched? Like .desktop launcher or others?

PDF by page number? I have 14587 such references, PDF is like huge collection, and organizing knowledge means getting references.

Case, Task, Follow-up?

Password? It should not get exposed. That means you need some toggle to give away password to LLM or not.

SMS?

URL for image versus webpage? URL for image could be separate type.

Location? Like GPS?

Page in physical book? To give the reference to physical object.

GPX file? To show the movement on the screen?

And then what if you combine types with subtypes?

Image as type is good, but image belonging to subtype Receipt would give you intersection of images representing receipts.

Type Task with subtype Call, immediately you know it is about calling, intersection choice speed up human activity, when you are about to call people, you need not search just through bunch of general tasks, you would get immediately list of those tasks to call.

Type PDF, could have subtype Book, this way you know it is not a paper, not a random document, maybe better quality document, Book.

Type YouTube, could have subtypes like Politics, Music, Movie, etc.

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            BKnmz

      commented

        Apr 21, 2026

äf we have a bunch of files of standards and regulations# would thäs be a good way to go with UI and agentic ai architecture?

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            Klajdiz9

      commented

        Apr 22, 2026

Hello everyone, i'm replicating this concept inside  antigravity (from the moment that antigravity can use chrome ) and  i'm adding a folder with skills inside the project . what do u think about it?

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            minh2004pd

      commented

        Apr 22, 2026

🚀 Introducing MemRAG: A Personalized AI Agent Ecosystem

Hi everyone! I’m excited to share my latest project: MemRAG Chatbot.

While most recent Agentic workflows focus on AI Coding Assistants, I have pivoted this technology toward a Personalized Knowledge Ecosystem. My goal was to create a chatbot that doesn't just "search" data, but actually learns, synthesizes, and accumulates knowledge through a structured evolutionary pipeline.

The Evolution of RAG: Continuous Knowledge Accumulation

MemRAG moves beyond traditional, fragmented RAG by implementing a sophisticated two-tier architecture:

📥 Foundation via Map-Reduce & Incremental Synthesis:

Whether it's a new PDF or a meeting transcript (via Soniox Realtime STT), data is processed through a 4-phase Map-Reduce pipeline inspired by Andrej Karpathy’s "LLM OS" vision.

Crucially, this is an Incremental Process:

Entity & Topic Evolution: Instead of creating isolated records, the system identifies if a new document mentions existing entities or topics. It then merges and updates the existing Wiki pages with new insights or creates new nodes if the information is unique. This ensures that knowledge "accumulates" and stays interlinked rather than being scattered across files.

Phase-based Pipeline: Parallel extraction (Map) ⮕ Deduplication (Reduce) ⮕ Global Synthesis ⮕ Knowledge Graph Finalization.

🔄 Dynamic Evolution via "Max-Turn" Trigger:

The learning continues during the conversation. Once the Max-Turn threshold is reached:

Summarize & Absorb: The system condenses the current conversation and extracts new facts or user preferences.

Wiki Update: These insights are updated back into the Wiki, allowing the bot to "grow smarter" after every interaction.

Seamless Resume: The context is cleared to optimize token usage, but the bot retains the newly "absorbed" knowledge for the rest of the session.

🔍 Hybrid Precision:

The Wiki provides the Global Context (the big picture and synthesized wisdom), while a dedicated RAG pipeline (Qdrant) remains active for Local Search, pinpointing granular, verbatim details within source documents.

Key Technical Highlights:

🧠 Long-term Memory (mem0): Persists facts and user context across sessions.

🎙️ Soniox Integration: High-fidelity, low-latency transcription for live data capture.

⚡ Google ADK & Gemini 2.5: Powers multimodal streaming (SSE) and complex tool-calling.

☁️ Cloud-Native Infrastructure: A production-ready AWS stack managed via Terraform (ECS, DynamoDB, RDS, CloudFront).

I believe the future of AI lies in Knowledge Accumulation rather than just Retrieval. I’d love to hear your thoughts on this "Wiki-as-Memory" approach!

GitHub Repo: https://github.com/minh2004pd/chatbotfullpipeline

🌟 If you find this project interesting, please consider giving it a Star on GitHub to support my work!

Developed by Minh Doan - AI Engineer

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            lele872

      commented

        Apr 22, 2026

@gnusupport The criticism that "the only real prevention is not using it" is dogmatic. It's like saying "don't use a book index because the index isn't the book." LLM WIKI is another layer of RAG system.

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            gnusupport

      commented

        Apr 22, 2026

@lele872 Thanks, I appreciate your input.

A book index points to pages where the actual content lives. It doesn't rewrite the book. It doesn't summarize the book. It doesn't claim to be the book.

LLM-Wiki does all three. It generates new pages. It summarizes sources. It pretends to be knowledge. That's not an index. That's a forgery.

The problem isn't "another layer of RAG." The problem is that LLM-Wiki replaces source documents with LLM-generated prose, then the LLM reads its own prose, and the human is left wondering where truth went.

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            yogirk

      commented

        Apr 22, 2026

  •

          edited

      Loading

        Uh oh!

There was an error while loading. Please reload this page.

I have been running the LLM Wiki pattern on my vault for the last few weeks. I noticed that the agent was doing two different jobs, reading/writing content (which its good at), and plumbing work like hashing files, splitting inbox entries, regenerating collection indexes (bad at it, burns tokens). So I went ahead and extracted the mechanical layer into a go binary:  https://github.com/yogirk/sparks. With Sparks, agent instructions collapse to ~3 lines, and the same vault drives from Claude Code, Codex, Gemini CLI, or any MCP harness. Shape is hardcoded to the five page types from karpathy's spec or v1 — opinionated first, declarative later if there's demand. Sparks also ships with a lightweight local viewer, so your vault works without Obsidian too. If anyone is interested:

brew install yogirk/tgcp/sparks

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            SEO-Warlord

      commented

        Apr 22, 2026

The pattern Karpathy describes is a genuine improvement over RAG for personal knowledge work, but I think the choice of wiki-style documents as the atomic unit is where it starts to strain. The comments about scale and drift bear that out.

A Zettelkasten structure handles most of the failure modes more naturally. Instead of mutable wiki pages that the LLM rewrites on each ingest, you have immutable atomic notes with stable IDs. The LLM creates new notes and links, never modifies existing ones. The knowledge graph that emerges is then explicit and human-auditable rather than implied by prose that may have been silently revised three ingests ago.

This maps directly onto the sharpest critique in this thread: scoping should be deterministic and reasoning should be probabilistic. Zettelkasten IDs and links give you deterministic traversal. "What connects to note 202504221430?" is a graph query, not a reasoning task. The LLM's job is to create atoms and synthesis notes that reference them, not to maintain a living document that nobody can fully trust.

The synthesis layer Karpathy describes is still valuable, but it belongs in a separate layer of notes that cite atoms rather than absorbing them. Good answers to queries get filed as new synthesis notes, linked to the atoms they draw from. The librarian writes index cards and essays, not revised encyclopedia entries.

The Memex analogy Karpathy invokes at the end is actually closer to Zettelkasten than to wiki. Bush's associative trails were links between stable documents, not a single document that rewrites itself. The LLM finally makes the maintenance cost of that model near zero. The wiki framing just undersells what's possible.

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            tcbhagat

      commented

        Apr 22, 2026

Does this necessitates large memory management architecture? I just can't figure out any way to reduce hallucinations with growing wiki.

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

              Copy link

                Copy Markdown

            gnusupport

      commented

        Apr 22, 2026

äf we have a bunch of files of standards and regulations# would thäs be a good way to go with UI and agentic ai architecture?

For your use case:

OpenProject 17.0 brings real-time documents collaboration and strategic project management:

https://www.openproject.org/press/press-release-openproject-17-0-real-time-documents-collaboration/#main-content

ONLYOFFICE Workspace - Browse /ONLYOFFICE_CommunityServer at SourceForge.net:

https://sourceforge.net/projects/teamlab/files/ONLYOFFICE_CommunityServer/

ONLYOFFICE/Docker-CommunityServer: Collaborative system for managing documents, projects, customer relations and emails in one place:

https://github.com/ONLYOFFICE/Docker-CommunityServer

Live Demo · Sync-in:

https://sync-in.com/docs/demo/

Standards and regulations need a search engine, and you can use RAG or train the model to speak those standards.

TruSpace – AI-Infused, Decentralized & Sovereign Document Workspace:

https://web.truspace.dev/

Those are solutions that work, document management, relationships, you name it.

    Sorry, something went wrong.

        Uh oh!

There was an error while loading. Please reload this page.

    Sign up for free
    to join this conversation on GitHub.
    Already have an account?
    Sign in to comment

Footer

        © 2026 GitHub, Inc.

Footer navigation

            Terms

            Privacy

            Security

            Status

            Community

            Docs

            Contact

       Manage cookies

      Do not share my personal information

    You can’t perform that action at this time.

# Key Points

- 

# Notes

# Lineage

- Ingested via: scripts/ingest.py
- Manifest entry: metadata/source-manifest.json::SRC-20260422-0002
- Source path: /home/peralese/Projects/Knowledge_Base/raw/inbox/browser/llm-wiki.md
- Canonical URL: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

