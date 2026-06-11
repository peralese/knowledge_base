---
title: "The biggest local LLM on your machine is useless if it can't call a single tool, no matter how many parameters it has"
source_type: "article"
origin: "web"
date_ingested: "2026-06-10"
domain: "ai"
status: "raw"
topics: []
source_id: "SRC-20260610-0004"
canonical_url: "https://flip.it/WgwO8T"
related_sources: []
---

# Overview

Brief description of what this source is and why it matters.

# Source Content

---
title: The biggest local LLM on your machine is useless if it can't call a single tool, no matter how many parameters it has
domain: ai
source_type: article
origin: url
canonical_url: https://flip.it/WgwO8T
---

Menu

								Sign in now

			Close

                    News

                    Tech Deals

                                                                PC Hardware

                        Submenu

                    CPU

                    GPU

                    Storage

                    Monitors

                    Keyboards & Mice

                            Software
                            Submenu

                    AI tools

                    Productivity

                    Self-Hosting

                    Home Lab

                    Other Software

                            Operating Systems
                            Submenu

                    Windows

                    Linux

                    macOS

                                                                Devices

                        Submenu

                    Single-Board Computers

                    Laptops

                    Gaming Handheld

                    Prebuilt PC

                            Home
                            Submenu

                    Networking

                    Smart Home

                                                                Entertainment

                        Submenu

                    Entertainment

                    Gaming

							Sign in

						Newsletter

				Menu

                                    Follow

                                            Followed

                            Like

Threads

More Action

Summary

																					Generate a summary of this story

						Sign in now

🔥Tech Deals

Claude

ESP32

AI Tools

Entertainment

Forums

			Close

The biggest local LLM on your machine is useless if it can't call a single tool, no matter how many parameters it has

                                                                            By

                                                                            Adam Conway

                                                        Published Jun 10, 2026, 1:00 PM EDT

I’m Adam Conway, an Irish technology fanatic with a BSc in Computer Science and I'm XDA’s Lead Technical Editor. My Bachelor’s thesis was conducted on the viability of benchmarking the non-functional elements of Android apps and smartphones such as performance, and I’ve been working in the tech industry in some way or another since 2017.

In my spare time, you’ll probably find me playing Counter-Strike or VALORANT, and you can reach out to me at adam@xda-developers.com, on Twitter as @AdamConwayIE, on Instagram as AdamConwayIE, or u/AdamConwayIE on Reddit.

Sign in to your XDA account

Add Us On

Summary

															Generate a summary of this story

follow

                                    Follow

followed

                                    Followed

                                    Like

                            Like

								Thread

Log in

							Here is a fact-based summary of the story contents:

							Try something different:

									Show me the facts

									Explain it like I’m 5

									Give me a lighthearted recap

When most people think about running AI locally, the conversation typically collapses into one number: parameters. How many billions can you fit in your VRAM, and is it enough to be useful? The assumption is that bigger is better, and if you can't run a 70B model, you're stuck with something that's barely functional. I bought into that assumption for a long time. My home server has an AMD Radeon RX 7900 XTX, and I spent months at the very beginning chasing bigger and bigger models, convinced that those bigger models were what my setup was missing.

As it turns out, Docker ran a practical evaluation of 21 models through a real agent loop last year, spanning 3,570 tests in total. GPT-4 scored 0.974. A local Qwen3 14B scored 0.971. llama3.3 70B scored 0.607. The 70B model was worse at tool calling than the 8B one, by a lot.

So what does this tell us? Well, your local AI agent doesn't need to be big. It just needs to be good at calling tools.

                        Model size doesn't predict tool-calling ability

            The 70B fallacy

Docker's testing wasn't some academic benchmark, but a real agent loop. Specifically, the model was expected to execute a reasoning process to decide what tool to call, then call it, process the result, and decide what to do next. It took place across up to five rounds. The test harness was made open source, and the methodology was as straightforward as it sounds. It literally just involved giving a model a set of tools like a shopping cart API, telling it to do something, and measuring whether it picked the right tool with the right arguments.

GPT-4, at the time, was the ceiling with its 0.974 score. Qwen3 14B at 0.971 was functionally identical. Qwen3 8B at 0.933 beat GPT-4o at 0.857, beat Claude 3.5 Sonnet at 0.851, and matched Claude 3 Haiku. llama3.1 8B managed 0.835, which is pretty solid. Gemma 3 4B got 0.733. Llama 3.2 3B got 0.727. These are all local models you can run on consumer hardware.

And then there's Llama 3.3 70B at 0.607. A model with more than twenty times the parameters of Llama3.2 3B, scoring noticeably lower on the thing that actually makes an agent useful. Meanwhile, two models explicitly advertised as tool-calling specialists, xLAM 8B and Watt 8B, scored 0.570 and 0.484 respectively.

Parameter count tells you almost nothing about whether a model will reliably call the right tool when you ask it to do something. If you're building an agent, tool-calling reliability is what you should be shopping for, and parameters are largely irrelevant. In fact, a smaller model can use tools to gain more information about whatever task you want to complete and store it in its context, and that's often enough for a smaller model to close the gap with a larger one.

                        Tool calling is what makes an agent an agent

            Reasoning without action is dead weight

I see people get this wrong all the time, so I want to make it clear from the beginning. Tool calling isn't the same thing as general reasoning capability, even if the two often go hand-in-hand. A model can be brilliant at logic puzzles, coding challenges, and long-form analysis, and still be completely useless as an agent if it can't reliably invoke a function when it needs to.

The inverse is more interesting than that, though, as a model with mediocre reasoning that can reliably call tools is at least capable of doing things. It can fetch data, run commands, edit files, and search the web. If tool calling is the part of a model that can hold it back the most, and I'd argue that for an agent it is, then reasoning without tool calling is dead weight. You can't think your way out of not being able to act.

This is where a lot of the benchmark obsession goes wrong, and it's why I'm apprehensive of benchmarks in general. There are a lot of allegations of so-called "benchmaxxing," as many benchmarks are known targets at this point. Even when the industry's favorite benchmarks, like MMLU, HumanEval, and GPQA, try to avoid contamination or overfitting, they still mostly test what a model knows and how well it reasons. They don't test whether it does the thing, and a model can look excellent on paper while still failing in practice if the benchmark never tested the behavior you needed in the first place. Plus, even when you do test tool calling, the results can be wildly inconsistent depending on how you set things up. Remember Docker's evaluation of Llama 3.2 3B scoring a rather impressive 0.727 on a shopping cart agent? Well, another independent benchmark of the same model got entirely different results.

Using a ReAct agent on more complex tasks with that model found zero tool invocations across nine attempts. So, it's the same model, but with completely different behavior. In that test, it would reason partway through a problem, acknowledge it needed information it didn't have, and then hallucinate an answer instead of reaching for the tools sitting right in front of it. Adding a routing layer to simplify the task made it worse, dropping to a perfect 0% accuracy. It's not a contradiction between benchmarks, but rather something that highlights the gamble you take on much smaller models like these and what they can do when it comes to tool calls.

Benchmaxxing is a real problem, and the models that top the reasoning leaderboards aren't necessarily the ones you want driving your agent. What matters is whether the model picks the right tool, calls it with the right arguments, and integrates the result. That's a trainable skill, not a function of scale, and the models that get it right are the ones that were trained for tool calls.

                        The models that work, at every scale

            From 2.3B to 123B, the pattern holds

For running agents locally in mid-2026, the Qwen family is the default for a reason. I used to run Qwen 3 Coder Next all the time, but now I run Qwen3.6 27B on my 7900 XTX and Qwen3.6 35B A3B on my MacBook Pro and Lenovo ThinkStation PGX, and all of them have been the most reliable tool-callers I've used locally. Qwen 3.5 9B is the sweet spot if you're on a single GPU and want something that fits comfortably while still handling real workloads, as it still handles tool calls exceptionally well.

Qwen's own published BFCL V4 results back this up: Qwen3.5 27B scores 68.5% and Qwen3.5 9B hits 66.1% and then there's a big drop: Qwen 3.5 4B drops to 50.3%, and Qwen 3.5 2B to 43.6%. In those smaller models, it seems pretty clear that there's a capability cut-off around the 7 to 9 billion parameter mark for general-purpose models. Docker's evaluation found the same thing: Qwen3 14B and 8B were the top local performers.

Mistral 7B v0.3 was one of the first open-weight models with native function-calling tokens, and it still works. It's old, mind you, releasing in May 2024, but it supports the same idea: a 7B model with explicit tool-calling support is more useful as an agent than a much larger general-purpose model without it.

But here's where it gets interesting: that 7B floor is more likely to be a training gap. We've already seen that off-the-shelf generic small models are inconsistent at tool calling, like with Llama 3.2 3B scoring well in Docker's shopping cart test but failing to invoke a tool even once in a more complex ReAct agent setup. Below 7B, it seems like you're taking a gamble on whether your agent framework and task complexity happen to align with what the model can handle... except for a notable exception: Google's Gemma 4 E2B, a 2.3 billion effective-parameter model with native function calling. It can even     run on a phone.

Google's own press release calls it "purpose-built for advanced reasoning and agentic workflows," so it makes sense to a degree. They didn't shrink a general-purpose model and hope the tool calling would survive, unlike smaller general-purpose models where tool calling often appears to be a surviving capability rather than a primary training target. Instead, they trained it specifically for agentic workloads at the edge, and the official docs demonstrate full multi-turn tool-calling loops with proper syntax, JSON schema support, and Python function integration. It runs in under 1.5GB of memory with quantization. Is it going to match a Qwen3.6 27B on complex multi-step tasks? Of course not. But it can call tools, and it wouldn't be able to if Google hadn't made that a training priority.

There's a wealth of academic research that proves the same point, too. In just one example, UC Berkeley's TinyAgent project found that a 1.1B model surpassed GPT-4 Turbo on Mac function calling after domain-specific fine-tuning. The same model before fine-tuning couldn't do it at all. Fine-tuning can massively change a model's capabilities, which I've demonstrated in my own testing when I fine-tuned a 7B Qwen model to create my own Home Assistant automations.

And at the other end of the scale of local models, the massive ones that most people can't run, the story doesn't change. Nvidia's Nemotron 3 Super 120B lists "agentic workflows, tool use, RAG" as its primary use cases. Mistral's Devstral 2 123B was purpose-built for agents that use tools to explore codebases, edit files, and run multi-step software engineering tasks, and it ships with dedicated TOOL_CALLS tokens. Qwen3 Coder Next, at 80 billion parameters, was trained from the ground up for agentic coding with a custom tool-call parser. OpenAI's gpt-oss-120b, which you can run on a 24GB VRAM GPU thanks to its MoE architecture, also comes with native function calling. Nobody is releasing a 120 billion parameter model in 2026 without tool calling as a headline feature.

						Deals

Computers & Work Setup deals: savings on PCs, GPUs, and gear

Find discounts and offers across Computers & Work Setup — save on desktops, laptops, GPUs, RAM, storage, networking, and workstation accessories to boost local AI performance without breaking the bank.

							Deals

						Explore Computers & Work Setup Deals

I've spent a lot of time in the past couple of years playing around with local models. If you're setting up an AI agent to run locally, whether that's through     Hermes Agent, Claude Code pointed at your own endpoint, Open WebUI with tool-calling plugins, or something you've wired together yourself, look specifically for tool-calling reliability. Pick a model that was trained to call tools, not just the biggest model you can squeeze into your VRAM. A 14B model that calls the right function every time beats a 70B model that gets it right only half the time.

                        Quantization isn't the problem you think it is

            Docker tested it, and the results were fine

Everyone quantizes for local deployment. It's how you fit a 14B model into 12GB of VRAM instead of needing 28GB at full precision. Still, people worry, understandably, that quantizing a model might degrade its ability to produce the precise, structured outputs that tool calling requires.

That fear isn't without evidence, either. Baseten's inference engineering team has argued exactly this: most quantization is calibrated on generic text that contains zero tool calls, so the model loses schema adherence after quantization. If you're reducing precision, and the thing you need precision for wasn't in the calibration data, you should expect degraded outputs.

With that said, Docker tested both quantized and unquantized variants of the same models, and found no significant difference in tool-calling behavior. Qwen3 8B at Q4_K_M scored 0.919, the same model at full precision scored 0.933. There is a gap, but it's small, and it's certainly not the difference between a model being classified as working as opposed to broken. It's not just Docker, either: Scorable's analysis of quantized LLMs backs this up: 8-bit quantized models are generally safe, and 4-bit quantized models can regress on structured output tasks, but they usually don't.

All of this is to say that if you're using standard GGUF quants, which most people running local models are, tool calling should hold up fine. It's still worth testing your specific workflow, but quantization isn't the silent killer it's sometimes made out to be. Tool calling is the most important aspect of your local LLM for real work, and you can rest assured that you don't need a big and powerful GPU to have that experience.

AI tools

AI

                                                                        Follow

                                                            Followed

                                                            Like

    Share

                        Facebook

                        X

                        WhatsApp

                        Threads

                        Bluesky

                        LinkedIn

                        Reddit

                        Flipboard

                        Copy link

                        Email

            Close

                    Subscribe for practical local AI tips in our newsletter

Expand your local AI toolkit with the newsletter: deeper analyses, model recommendations, and hands-on guidance on tool-calling reliability, quantization trade-offs, and picking models that reliably invoke functions in real agent setups.

                    Get Updates

By subscribing, you agree to receive newsletter and marketing emails, and accept our Terms of Use and Privacy Policy. You can unsubscribe anytime.

            Trending Now

			I use Claude Code and Codex together, and the combination does something neither can do alone

			I paid for Gemini, Claude, and Copilot for a month, but only one of them is worth the subscription

			3 useful sideloaded Android Auto apps I use almost every day

                                    Thread

Sign in to your XDA account

We want to hear from you. Share your perspective in the comments below, and please keep the conversation respectful.

                                    Be the first to post

                                    Attachment(s)

                                    Please respect our community guidelines. No links, inappropriate language, or spam.

Your comment has not been saved

                Send confirmation email

This space is open for discussion.

Be the first to share your thoughts.

Terms

Privacy

Feedback

Recommended

                                    AMD's next-gen RDNA 5 GPUs likely won't arrive until late 2027, and that's if we're lucky

                                    Your SSD will outlive your PC — unless you ignore these Windows habits

                                    I started using Gemini Actions in Android Auto, and it’s been a game-changer

                                    AMD is resurrecting a 4-year-old CPU, and it exposes some uncomfortable truths about the PC industry

Shorts

                                                By

                                                    Alex Dobie

                                    1:39

                            NVIDIA RTX Spark: The 4 things you need to know

                                                By

                                                    Alex Dobie

                                    1:14

                            Can Intel's Arc G3 beat AMD on gaming handhelds?

                                                By

                                                    Alex Dobie

                                    1:11

                            RIP MacBook Neo?

                                                By

                                                    Alex Dobie

                                    1:16

                            Can the Galaxy S2 run modern Android?

                                                By

                                                    Alex Dobie

                                    1:07

                            Android 17: Top 4 features worth caring about

Join Our Team

Our Audience

About Us

Press & Events

Media Coverage

Contact Us

Follow Us

Advertising

Careers

Terms

Privacy

Policies

                            XDA is part of the
                            Valnet Publishing Group

                Copyright © 2026 Valnet Inc.

# Key Points

- 

# Notes

# Lineage

- Ingested via: scripts/ingest.py
- Manifest entry: metadata/domains/ai/source-manifest.json::SRC-20260610-0004
- Source path: /Users/erickperales/Projects/knowledge_base/raw/domains/ai/inbox/browser/the-biggest-local-llm-on-your-machine-is-useless-if-it-can-t-call-a-single-tool-no-matter-how-many-parameters-it-has.md
- Canonical URL: https://flip.it/WgwO8T

