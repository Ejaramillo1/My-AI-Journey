---
title: "The Non-Engineer's Guide to Running an AI Agent"
date: 2026-05-21
draft: false
tags: ["AI Agents", "Beginners", "Self-Hosting", "No-Code", "Productivity"]
categories: ["AI & Automation"]
author: "Ed Jaramillo"
description: "I'm not a software engineer. I'm a pricing analyst. And I run my own AI agent 24/7. Here's what nobody told me about getting started."
ShowToc: true
ShowBreadCrumbs: true
---

I'm not a software engineer. I'm a pricing analyst.

I work in competitive pricing. I write SQL and DAX, not Python microservices. When I decided to set up my own AI agent, I was in over my head from day one.

The good news: you can do this. The honest news: it will take longer than you think, and the documentation assumes you know things you might not know.

## The Confusion Points

### Which Terminal Is Which?

You've got your Windows terminal, your WSL terminal, your Docker terminal, and the sandbox terminal inside all of that. I spent hours running commands in the wrong place.

### Which Code Runs Where?

OpenShell policies run on the host. Agent logic runs in the sandbox. Gateway config runs on the gateway. Mix them up and nothing works.

### YAML Indentation Will Break You

Two spaces vs four spaces. Tabs vs spaces. A single misaligned line and your config is invisible to the system. No error message. Just silence.

## What Actually Helped

1. **Draw the layers.** Host → WSL → Docker → Sandbox → Gateway. Label what runs where.
2. **Save your API keys in a password manager.** I used to generate keys and lose them within a week. Now I have a system.
3. **Rebuilds happen.** Don't keep anything valuable inside the sandbox. It's disposable by design.
4. **Start with one task.** I tried to automate everything at once. Pick one workflow. Make it work. Then expand.
5. **Test network policies one endpoint at a time.** The sandbox blocks everything by default. Add things slowly.

## Why It's Worth It

After all the frustration, I have an AI agent that runs my daily briefings, tracks my finances, researches competitors, and drafts my emails. It works while I sleep. It costs almost nothing to run. And I built it — not a dev team, not a vendor. Me.

If a pricing analyst in Tijuana can do this, you probably can too.
