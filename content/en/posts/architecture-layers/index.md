---
title: "The Architecture You Need to Understand Before You Touch a Terminal"
date: 2026-05-21
draft: false
tags: ["AI Agents", "Architecture", "Self-Hosting", "OpenShell", "Beginners"]
categories: ["AI & Automation"]
author: "Ed Jaramillo"
description: "Nobody explained the layers clearly to me, so I'll explain them now. Host, WSL, Docker, sandbox, gateway — here's what runs where."
ShowToc: true
ShowBreadCrumbs: true
---

Nobody explained this clearly to me, so I'll explain it now. There are three layers, and mixing them up will cost you hours.

## The Three Layers

- **OpenShell** — the sandbox. Think of it as a locked-down Linux container where your AI agent actually runs. It has its own filesystem, its own network rules, and it doesn't trust anything by default.
- **NemoClaw** — NVIDIA's distribution of the agent framework. Comes with GPU-optimized inference and an NVIDIA API key for testing. That key? It's for *testing only*. You don't get a warning when it stops working.
- **OpenClaw** — the gateway that connects your sandbox to chat platforms (Telegram, Discord, etc.), schedules cron jobs, and manages the agent lifecycle.

If you're on Windows like me, add another layer: **WSL → Docker → OpenShell sandbox**. Four layers deep. A mistake in any layer breaks the whole thing.

## Network Policies: The Silent Killer

The sandbox blocks all outbound traffic by default. You need to *explicitly* allow every API endpoint your agent will call.

This is good security — but it's also the #1 reason my agent sat there doing nothing for hours while I debugged.

I didn't understand the policy syntax. I messed up indentation in YAML files. YAML doesn't forgive indentation errors. One extra space and your policy silently fails.

## Rebuilding the Sandbox Erases Everything

This one hurt. You tweak a sandbox config, rebuild, and all your work inside the sandbox is gone. Every script, every credential, every config file.

You learn to externalize everything fast — or you learn the hard way.

**Key takeaway:** Keep your work outside the sandbox. Mount volumes. The sandbox is disposable by design.

## What I'd Tell Myself on Install #1

1. Draw the architecture on paper first. Seriously.
2. Save every API key you generate. I cannot stress this enough.
3. Test network policies one endpoint at a time.
4. Indentation is not optional in YAML. Use a linter.
5. Assume you'll rebuild the sandbox at least once. Plan for it.
