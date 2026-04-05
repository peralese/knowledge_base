---
title: "Open Claw Security"
source_type: "article"
origin: "web"
date_ingested: "2026-04-05"
status: "raw"
topics: []
tags: []
author: ""
date_created: ""
date_published: ""
language: "en"
summary: ""
source_id: "SRC-20260405-0002"
canonical_url: ""
related_sources: []
confidence: ""
license: ""
---

# Overview

Brief description of what this source is and why it matters.

# Source Content

# OpenClaw Setup Guide — Don’t Launch Your Bot Before Reading This / Habr
This guide covers how to set up OpenClaw (formerly Clawdbot) on your local machine and, most importantly, how to secure it so strangers can’t access your computer. If you are ready, then let’s get started! :)

![](https://habrastorage.org/r/w1560/getpro/habr//post_images/3c7/f45/1ab/3c7f451ab7ab6b8ac67c3d0230a43ad5.png)

### How to Set Up OpenClaw

#### Install OpenClaw

First, open your terminal (Command Prompt or Terminal on Mac/Linux). You need to install the tool globally. Run this command:

```
curl -fsSL https://openclaw.ai/install.sh | bash

```


OR if using npm directly:

```
npm install -g openclaw

```


#### Run the Onboarding Wizard

Once installed, start the configuration process:

```
openclaw onboard

```


*   **Security Warning:** You will see a warning that the bot works on your local machine. Read it and accept.

*   **Quick Start:** Select “Quick Start” for the easiest setup.


![Install OpenClaw](https://habrastorage.org/r/w1560/getpro/habr//post_images/4e8/fcf/56b/4e8fcf56b151a7be5c01a75174454bc2.png)

Install OpenClaw

**Model Selection:** Choose your AI provider (e.g., OpenAI Codex or GPT-4). You will need to log in to your provider account.

**Connect a chat platform** — After the model is selected, OpenClaw asks you to set up a chat interface. Select your preferred platform (e.g., **Telegram**).

1.  Open Telegram and search for **[@BotFather](https://habr.com/users/BotFather)**.

2.  Send the command `/newbot`.

3.  Give your bot a name and a username (must end in `_bot`).

4.  **Copy the Token** provided by BotFather.

5.  Paste this token into your terminal when OpenClaw asks for it.


A similar process applies to WhatsApp, Discord, and other chat platforms.

**Get Your User ID**

You need to tell OpenClaw _who_ is allowed to talk to it.

1.  Search for **[@userinfobot](https://habr.com/users/userinfobot)** in Telegram.

2.  Click “Start” to see your ID (a number).

3.  Copy and paste this ID into the OpenClaw terminal.


**Pair Your Bot**

Restart your gateway to apply changes:

```
openclaw gateway restart

```


![Pair Your Bot](https://habrastorage.org/r/w1560/getpro/habr//post_images/108/71c/d35/10871cd35655b7b493f234f1b89b7b00.png)

Pair Your Bot

**Configure skills (optional)** — OpenClaw can install skills (tools) to perform tasks such as sending emails or editing files. During onboarding, you can skip or install skills. If you choose to install, use **npm** as the node manager; otherwise, select **Skip for now**.

**Provide API keys (optional)** — Some skills require API keys (e.g., Brave Search API). During setup, you can say **No** if you don’t have keys yet.

**Choose UI** — OpenClaw offers a web‑based **Control UI** or a **TUI**. The TUI keeps everything in the command line and is recommended for first‑time setup. When ready, select **Hatch in TUI** to start the bot’s personality configuration. The bot will ask for its name and how to address you. After that, OpenClaw is ready to chat via the terminal and your chosen chat platform

If you get stuck, please watch my YouTube tutorial:

**_Watch on YouTube:_** [**_How to Set Up OpenClaw_**](https://youtu.be/D9j2t_w5lps?si=UjSh5YFC-16u8fbv)

#### Extending capabilities

OpenClaw can perform additional tasks after the initial setup.

*   **Web searches** — If you ask the bot how to perform web searches, it will guide you through obtaining an API key (for example, from the Brave Web Search API) and sending it to the bot via chat. Once the key is set, OpenClaw can search the web and return results.

*   **File operations** — You can instruct your bot to research a topic and save the results to a Markdown file. The bot will generate the file and include citations.


Remember that each new capability increases the bot’s permissions, so enable them carefully and keep security in mind.

### How to Secure OpenClaw

By default, giving an AI access to your computer carries risks. Follow these steps to lock it down.

#### Restrict Gateway Access

Your bot shouldn’t be visible to the whole internet.

*   Open your config file: `~/.openclaw/openclaw.json`

*   Find the `gateway` section.

*   Change the address `0.0.0.0` to `127.0.0.1` (loopback) This ensures only _you_ (localhost) can access the gateway.


#### Enable Authentication

Make sure your gateway requires a token:

*   In the same config file, ensure `authentication` is set to `mode: "token"`.

*   Verify a token is present. Treat this token like a password.


#### Set Channel Policies

Don’t let your bot talk to strangers.

*   **DM Policy:** Set to `"pairing"` (requires approval) \*\*.

*   **Group Policy:** Set to `"disabled"` so the bot can't be added to public groups where it might leak data.


```
...
  "channels": {
    "telegram": {
      "dmPolicy": "pairing",
      "groupPolicy": "mention"
    }
  }
...

```


#### Secure Your Credentials

Protect the files that store your API keys. Run this command to make sure only _your user_ can read the credentials file:

```
chmod 700 ~/.openclaw/credentials

```


#### Run a Security Audit

OpenClaw has a built-in tool to check for holes. Run this regularly:

```
openclaw security audit --deep --fix

```


![Run a Security Audit](https://habrastorage.org/r/w1560/getpro/habr//post_images/122/4ce/c21/1224cec211fcb7d522a51e6357ba5035.png)

Run a Security Audit

If it finds issues, you can often fix them automatically with:

```
openclaw doctor --fix

```


#### Watch Out for “Prompt Injection”

Be careful when asking your bot to browse the web or read untrusted files. Bad actors can hide commands in text that trick the AI. Always use the Sandbox environment when experimenting with untrusted data.

#### Final Step

After applying these security fixes, always restart your gateway:

```
openclaw gateway restart

```


If you want a simple walkthrough, please check my video tutorial:

**_Watch on YouTube:_** [**_How to secure OpenClaw Bot_**](https://youtu.be/rep62KFHtRE?si=FONdBK7aoKCoEddD)

### Conclusion

OpenClaw gives you the power of a personal AI assistant that runs on your own hardware. When configured correctly, it can search the web, manage files, and respond to your chat messages across multiple platforms. However, because it uses tools that can execute commands on your system, security must be a first‑class concern.

Stay safe! Cheers! :)

# Key Points

- 

# Notes

# Lineage

- Ingested via: scripts/ingest.py
- Manifest entry: metadata/source-manifest.json::SRC-20260405-0002
- Source path: raw/inbox/open_claw_security.md
- Canonical URL: 

