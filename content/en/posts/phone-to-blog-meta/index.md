---
title: "How I Launched a Bilingual Blog From My Phone at 2 AM Using an AI Agent"
date: 2026-05-21
draft: false
tags: ["Blog", "Hugo", "GitHub Pages", "AI Agents", "Meta"]
categories: ["AI & Automation"]
author: "Ed Jaramillo"
description: "No laptop. No terminal. Just a phone, Telegram, and an AI agent that pushed to GitHub while I was in bed."
ShowToc: true
ShowBreadCrumbs: true
---

Tonight I launched this blog.

Not from my laptop. Not from a terminal. From my phone. At 2 AM. Lying in bed.

Here's exactly how it happened, because the workflow says more about AI agents than any benchmark ever could.

## The Setup

I've been keeping my notes, ideas, and drafts in a private Obsidian vault for months. Some of those drafts deserved to be public — but moving them from a private vault to a public blog felt like friction I didn't have time for.

So I asked my AI agent, Dae, to handle it.

## The Stack

- **Hugo** — static site generator, fast and markdown-native
- **PaperMod** — clean, bilingual-ready theme with dark mode
- **GitHub Actions** — builds and deploys on every push
- **GitHub Pages** — free hosting, no servers to manage

## The Flow

1. I told Dae: "Create a Hugo blog in a public GitHub repo."
2. Dae built the full structure — config, theme, posts, GitHub Actions workflow, everything — in the sandbox.
3. The first theme approach failed (Hugo modules didn't load). The second failed too (git submodules). The third worked: vendor the theme files directly.
4. The Hugo version was wrong (0.145.0 vs 0.146.0 minimum for PaperMod). Dae caught it.
5. Each fix was a single commit. Each commit was a single push — from the sandbox, via HTTPS, token-authenticated.
6. GitHub Actions built and deployed. The blog went live.

I never opened a terminal on my laptop. I never even touched my computer.

## What This Actually Demonstrates

This isn't about a blog. It's about what changes when you have a persistent AI agent with access to your files and the ability to execute.

Dae didn't just generate text. It:
- Diagnosed why the theme wasn't loading
- Switched from Hugo modules to vendored files
- Found the Hugo version mismatch in theme.toml
- Fixed and redeployed — all through Telegram

That's not a chatbot. That's an operator.

## The Real Story

The blog took maybe 30 minutes from idea to live. A month ago, this would have been a weekend project I never got around to.

The difference isn't skill. It's leverage.

My agent runs 24/7 on a repurposed Dell OptiPlex in my house. It costs almost nothing. And tonight it helped me ship something real while I was half asleep.

**This is the blog post about launching the blog. Meta enough for you?**
