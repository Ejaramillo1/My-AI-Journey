---
title: "How Muse Revamped My Blog While I Was Cooking Burgers for Sunday NFL Games"
date: 2026-11-08
draft: false
tags: ["AI Agents", "Hugo", "GitHub Pages", "Muse"]
categories: ["AI & Automation"]
author: "Ed Jaramillo"
description: "My AI assistant redesigned, deployed, and debugged this blog — Hugo on GitHub Pages, a cyberpunk v5 theme, and one missing URL prefix that broke four things at once."
cover:
  image: "images/hero-bg.jpg"
  alt: "Neon cyberpunk city, the reference image behind the blog's v5 redesign"
ShowToc: true
ShowBreadCrumbs: true
---

This Sunday I redesigned my blog without opening VS Code, without running a single Git command — while cooking burgers for my wife, our kids, and a friend for Sunday NFL games. My phone stayed on the side table by the grill, buzzing with approval cards between flips, while my wife helped keep the food, the kids, and the conversation all moving. And somewhere between flipping burgers and plays on TV, my bilingual blog got a completely new look — dark, neon, cyberpunk — designed, built, deployed, debugged, and verified live.

I didn't do the typing. My AI assistant did. My job was the part that actually matters: deciding what I wanted, showing it a picture of the vibe, approving every change before it went public, and — when something looked wrong — sending back a screenshot and saying "nope, still broken."

This is the story of how that worked, what the setup looks like under the hood, and the one small bug that broke four different things at once.

## The setup: a Hugo blog on GitHub Pages

First, the blog itself. [My-AI-Journey](https://ejaramillo1.github.io/My-AI-Journey/) is my bilingual journal — every post in English and Spanish — about learning and working with AI: agent frameworks, experiments with agent memory, home-lab adventures, and whatever I'm building at the time.

Technically, it's simple on purpose:

- **Generator:** Hugo, a static site generator. I write posts in Markdown, Hugo turns them into plain HTML and CSS. No database, no server to maintain.
- **Source:** Everything lives in a GitHub repository, `Ejaramillo1/My-AI-Journey` — content, templates, styles, and images.
- **Hosting:** GitHub Pages, free static hosting tied directly to the repo.
- **Build and deploy:** GitHub Actions. Every push to the main branch triggers a workflow that installs Hugo (version 0.152.2 in the current setup), builds the site, and publishes it. If the run is green, the new site is live.

That last detail matters: the blog does not live at the root of my GitHub Pages domain. It lives in a subfolder:

```text
https://ejaramillo1.github.io/My-AI-Journey/
                root domain ^   ^ subpath
```

Hold on to that subpath. It's the villain of the second half of this story.

## The other half of the setup: what Muse is

The assistant that did the work is Muse, my personal AI agent — I call it Lolo. It is not a chatbot window I paste code into. It has its own computer it can work on, its own browser it can drive, memory of my projects and preferences, and connectors to the services I actually use, including GitHub.

Three parts of that setup made this redesign possible:

- **A real browser.** Lolo can open websites, sign in, upload files through a web interface, click buttons, and re-check a live page after a deploy — the same things I would do, only faster and without leaving the grill.
- **A GitHub connection.** Through the GitHub connector it can read and push files in my repositories. My GitHub login for that browser work is stored in a secure vault, so it can sign in as me when a task needs the web UI.
- **Approval cards.** Nothing publishes on its own. Every push to GitHub paused and showed me a card: these files, this repo, approve or not? I tapped approve from my phone. That gate is the whole trust model — the agent proposes and executes, I authorize anything that leaves the machine.

So the division of labor for the afternoon looked like this:

| Job | Who did it |
|---|---|
| Pick the visual direction and supply a reference image | Me |
| Write and edit the CSS, templates, and layout files | Muse |
| Generate and upload the images | Muse, via the browser |
| Push the code changes to GitHub | Muse, after my approval on each card |
| Watch the GitHub Actions build and confirm it went green | Muse |
| Click through the live site in English and Spanish | Muse — then me, on my phone |
| Catch the bug everyone missed | Me, with two screenshots |
| Fix the bug and re-verify | Muse, after my approval |
| Cook burgers and host Sunday NFL games | Me and my wife, with the kids and our friend — uninterrupted |

## What changed: Blade Runner, but make it readable

The old design was fine, which is another way of saying I had stopped seeing it. For version 5 I wanted a mood, not a template. Instead of describing it in words, I handed Muse a reference image — a neon cyberpunk city — and that became the hero and the palette for the whole site.

The redesign, as it shipped:

- **A dark cyberpunk theme** inspired by *Blade Runner*: near-black backgrounds, neon pink and cyan accents, and a rain effect over the hero.
- **The reference city photo as the hero background**, with a dark overlay on top so the headline and buttons stay perfectly legible over the image. Atmosphere is great; unreadable text is not.
- **Compact horizontal post cards** on the homepage, with each post's cover image on the right side of the card instead of a big banner on top. The homepage scans like a feed now, not a gallery.
- **The same treatment in both languages**, because the blog is bilingual and a redesign that only works in English is a half redesign.

Under the hood it was 16 images and 19 text files — stylesheets, layout templates, and content tweaks. Not a huge change in file count, but a total change in how the site feels.

## Shipping it: two channels, one green check

Publishing used both of Muse's hands, because each channel was better at one job:

1. **Images went up through the browser.** Muse signed in to GitHub's web interface and uploaded the 16 images directly, across 12 commits. Binary files through a web UI are unglamorous and reliable.
2. **Code went up through the connector.** The 19 text files — CSS, templates, configuration — were pushed in a single commit, `683e22c`.
3. **GitHub Actions did the rest.** Run #21 built the site with Hugo and deployed it to GitHub Pages. Green check.
4. **Then came verification, not celebration.** Muse opened the live site and checked it in English and in Spanish: homepage, posts, hero, cards. It looked right.

It looked right. It was not entirely right.

## The bug: one missing prefix, four broken things

Remember the subpath? The blog lives at `ejaramillo1.github.io/My-AI-Journey/`, but several links and image paths in the new design were written as if it lived at the root — like `/images/hero.jpg` or `/tags/ai/` instead of `/My-AI-Journey/images/hero.jpg`.

A path that starts with `/` tells the browser "start from the root of the domain." So the browser went looking for files one folder too high, where nothing exists. One root cause, four visible symptoms:

1. **Tag links on the homepage cards returned 404.** Clicking a tag took you to `github.io/tags/...`, outside the blog entirely.
2. **The About page loaded, but its top image was broken** — same wrong path, in both English and Spanish.
3. **The hero photo was invisible on the homepage.** The CSS background used the same root-relative path. At first glance it looked like the dark overlay was just too strong; it wasn't the gradient, the image simply wasn't loading.
4. **The favicon links were broken too**, quietly, in the page head where nobody looks until something feels off.

The fix was five files: every root-relative path rewritten to include the subpath, then a local Hugo build to prove it. In the built site, the About image, the hero background, the tag links, and the favicons all pointed to real files, and a scan of the whole output found no root-relative paths left. I approved the push, the new deploy went green, and Muse re-checked all four points live. Fixed.

Except for the two buttons I was about to tap on my phone.

## Round two: the hero buttons, caught by screenshot

I asked for the link to confirm everything myself. Then I did what users do: I tapped the big friendly buttons on the homepage — **Read the blog** and **About me**. Both landed on a 404. I sent Muse two screenshots of the error page and a short review: "Nope. The Read the Blog section and About Me sections do not work."

They had the same disease. The hero buttons were handwritten links to `/posts/` and `/about/` instead of `/My-AI-Journey/posts/` and `/My-AI-Journey/about/`. The top navigation menu was generated by Hugo and had always been correct — which is exactly why the bug survived: everything *around* the buttons worked, and the first verification had checked pages by navigating to them, not by clicking the buttons a visitor would actually click.

This time the check was a full scan of the built site, link by link, not a spot check. The corrected buttons were pushed as commit `85e95a0`, GitHub Actions run #23 succeeded, and Muse clicked all four buttons live — Read the blog and About me in English, Leer el blog and Acerca de mí in Spanish. All four landed where they should.

One honest footnote from that verification: the very first click after the deploy still hit the old 404 once. About 90 seconds and one reload later, it worked. That was GitHub's cache serving the previous build while the new one propagated — annoying, and worth knowing, because it looks exactly like a broken fix. If you ever deploy to GitHub Pages and your fix "doesn't work," wait two minutes and hard-refresh (Ctrl+Shift+R) before you start debugging again.

A second footnote, in the interest of honesty: while auditing the site, Muse also found a flaw that has nothing to do with the redesign. The subtitle of my older NemoClaw post ends mid-sentence — "Here's what the…" — a truncation from the original content that nobody had noticed. It's still there. Real audits find the bug you asked about and one you didn't.

## What I actually learned

**Taste is easier to show than to describe.** One reference image did more design work than any paragraph I could have written. When your collaborator — human or AI — can see the target, you skip three rounds of "no, darker, more neon, less… that."

**Verification has to imitate the user, not the developer.** The site passed a page-by-page check and still failed the first thing a visitor does: tap the big button. The fix for the fix was a full-site link scan and clicking the actual buttons, in both languages. "I opened the page" and "the page works" are different claims.

**Approvals are a feature, not friction.** Every publish step waited for my tap. That meant I could genuinely stay on burger duty — I wasn't supervising a terminal, I was just the person who says yes or no, with the diff in front of me, at the moments that mattered.

**My job didn't disappear. It moved.** Direction, judgment, and adversarial testing — sending back a screenshot that says "still broken" — turned out to be the human contribution. Execution, deployment, and methodical re-checking were the agent's. That's a pretty good summary of where I think this kind of work is heading, and it's why I write this blog in the first place.

The blog is live at [ejaramillo1.github.io/My-AI-Journey](https://ejaramillo1.github.io/My-AI-Journey/). Go tap the buttons. They work now — I checked from my phone on the side table, spatula safely down, between burgers, while my wife, our kids, and our friend waited for the next round off the grill.

## Want to try Muse? Use my invite code

If you want to use Muse, use my invite code:

> Echa un vistazo a Muse, tu agente de IA personal. Canjea mi código en la configuración dentro de las 48 horas posteriores a unirte y ambos obtendremos 1 mil millones tokens de Muse.
>
> **Código: ZZAUWW**
