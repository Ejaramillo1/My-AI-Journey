"""B3 integrated test: serve the Hugo build and assert the homepage.

Portable: no machine-specific paths, no fixed port, no pinned browser
binary. Expected values are read from data/identity.yaml (the single
source of truth) with yaml.safe_load (PyYAML 6.0.2, pinned), so the test
checks that the rendered page matches the data, not a hardcoded copy.

Two modes. Local mode is the default: it reports partial results
explicitly when a check cannot run (skips are listed, not hidden), and
it may fall back to an existing public/ build when no Hugo binary is
available, verified only by file timestamps. That timestamp fallback
is a heuristic, not release evidence. Strict mode (--strict, or
B3_STRICT=1) is the release gate: exit 0 only if every check passes
AND zero checks are skipped; Hugo is required (no timestamp fallback);
and a missing historical baseline fails loudly instead of skipping.
Use strict mode for a release decision; use local mode for day to day
development. Exit codes: 0 pass, 1 a check failed (or, in strict
mode, a check was skipped), 2 a setup failure (missing dependency,
missing Hugo in strict mode, missing baseline in strict mode, missing
or stale build, server did not start).

The test server runs in-process on loopback only (127.0.0.1, port 0:
the OS assigns a free port and the server keeps the bound socket, so
there is no port race and the build is never exposed on the network).
The served tree is a copy of the build inside a TemporaryDirectory, so
the temporary directory is removed even if setup fails, and no symlink
is used (the test runs on Linux and macOS without admin rights or
Developer Mode; Windows support is not independently tested, and the
setup examples below use POSIX venv paths).

The build is fresh. When a Hugo binary is available (HUGO_BIN, or
hugo on PATH) the site is built into a fresh temporary destination,
never into the existing public/ directory, so a stale file from an
earlier build cannot survive and make a deleted route look healthy.
The test then serves that exact fresh output. When no Hugo binary is
available, local mode verifies public/ exists and is newer than every
source file and serves that copy; strict mode fails loudly instead,
because a timestamp check is not release evidence.

Historical routes are checked against the pinned PR base, not the
mutable main branch. The versioned inventory below (BASE_INVENTORY)
lists every historical post URL and the title its detail page must
carry, generated from the pinned base commit. The test also fetches
the slug list from the GitHub API at that exact base SHA and uses the
fetched list when it is available; when the fetch fails it falls back
to the embedded inventory (so the test works offline when the
inventory is available). When neither source can provide the
inventory, strict mode fails loudly and local mode records the base
checks as skipped. Redirects are NOT permitted for historical post
URLs: the URL must return 200 directly and render the post carrying
its expected title. A redirect means the URL moved, which is a
preservation failure, so the test asserts the final URL equals the
requested URL and the expected title appears in the page.

Checks, per theme (dark/light) x viewport (1920/1440/390/320) x language
(EN/ES): H1, eyebrow role, tagline, bio, chips, the 3 publications
(full titles and URLs, new-tab target/rel/aria-label/marker), the
Substack CTA, the 5 social links (same new-tab indication), the actual
theme (data-theme attribute plus computed body background), and no
horizontal overflow (320px reflow included). JSON-LD invariants are
checked on every homepage load: Person (name, @id, jobTitle, knowsAbout,
6 sameAs in order) and Organization (sameAs is the Substack publication
only, no personal profiles). Post routes are checked separately:
  /posts/ and /es/posts/ return 200 with 6 / 5 entries, the list links
match the candidate content tree, and every historical post URL from
the pinned base still resolves (200, no redirect) and renders the post
carrying its expected title.
The homepage carries no post list.

Usage, from the repo root (work-d4):
    python3 scripts/test-b3.py
    python3 scripts/test-b3.py --strict
Requires Playwright and PyYAML. Set them up once in a repo-local venv,
then rerun:
    python3 -m venv .venv
    .venv/bin/pip install "playwright" "pyyaml==6.0.2"
    .venv/bin/playwright install chromium
    .venv/bin/python scripts/test-b3.py
Set HUGO_BIN to a hugo binary to rebuild the site before testing;
otherwise run `hugo --gc --minify` first. Screenshots and measurements
go to a temporary directory, printed at the end; set B3_TEST_OUT to
keep them in a fixed place. Test hooks (not for normal use):
B3_GITHUB_API_BASE overrides the GitHub API base URL, and
B3_NO_EMBEDDED_BASE=1 disables the embedded baseline fallback, so an
offline strict run can be simulated.
"""
import functools
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WORK = Path(__file__).resolve().parents[1]
IDENTITY = WORK / "data" / "identity.yaml"
CERTIFICATES = WORK / "data" / "certificates.yaml"
PUBLIC = WORK / "public"

# Pinned PR base for the historical route inventory. The inventory
# below was generated from this exact commit, so it does not move when
# main moves. The titles are verbatim from the post frontmatter at
# that commit; they are data, not prose, and must match exactly for
# the content-identity check.
BASE_SHA = "752423511a272ecd1c488fe1f97957c69604a39e"
BASE_INVENTORY = {
    "en": [
        ("architecture-layers",
         "The Architecture You Need to Understand Before You Touch a Terminal"),
        ("deepseek-vs-openai",
         "I Burned $20 in OpenAI Credits in 2 Hours — and Found a Better Way"),
        ("how-muse-revamped-my-blog",
         "How Muse Revamped My Blog While I Was Cooking Burgers for Sunday NFL Games"),
        ("nemoclaw-20-installs",
         "I Installed NemoClaw 20 Times and Here's What I Learned"),
        ("non-engineer-guide",
         "The Non-Engineer's Guide to Running an AI Agent"),
        ("phone-to-blog-meta",
         "How I Launched a Bilingual Blog From My Phone at 2 AM Using an AI Agent"),
    ],
    "es": [
        ("architecture-layers",
         "La Arquitectura Que Necesitas Entender Antes de Tocar una Terminal"),
        ("deepseek-vs-openai",
         "Quemé $20 en Créditos de OpenAI en 2 Horas — y Encontré Algo Mejor"),
        ("nemoclaw-20-installs",
         "Instalé NemoClaw 20 Veces y Esto Es Lo Que Aprendí"),
        ("non-engineer-guide",
         "La Guía del No-Ingeniero para Correr un Agente de IA"),
        ("phone-to-blog-meta",
         "Cómo Lancé un Blog Bilingüe Desde Mi Celular a las 2 AM Usando un Agente de IA"),
    ],
}

# Modes and test hooks. --strict (or B3_STRICT=1) is the release gate.
STRICT = "--strict" in sys.argv or os.environ.get("B3_STRICT") == "1"
GITHUB_API_BASE = os.environ.get("B3_GITHUB_API_BASE",
                                 "https://api.github.com").rstrip("/")
NO_EMBEDDED_BASE = os.environ.get("B3_NO_EMBEDDED_BASE") == "1"

# Computed body background on list pages (the homepage is one).
# PaperMod themes/PaperMod/assets/css/core/theme-vars.css:
#   .list { background: var(--code-bg); }
#   [data-theme="dark"] .list { background: var(--theme); }
# so light body bg is the light --code-bg, dark body bg is the dark
# --theme, both from assets/css/extended/custom.css.
THEME_BG = {"dark": "rgb(7, 11, 31)", "light": "rgb(232, 236, 248)"}
NEW_TAB = {"en": "opens in a new tab", "es": "se abre en una pestaña nueva"}
BIO_MARK = {
    "en": "central home of my research",
    "es": "hogar central de mi investigación",
}
POST_COUNT = {"en": 6, "es": 5}


def fail(msg):
    print(f"FATAL: {msg}", file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------- identity
try:
    import yaml
except ImportError:
    print("PyYAML is not installed for this Python.", file=sys.stderr)
    print("Set it up once, then rerun:", file=sys.stderr)
    print('  python3 -m venv .venv', file=sys.stderr)
    print('  .venv/bin/pip install "playwright" "pyyaml==6.0.2"', file=sys.stderr)
    print("  .venv/bin/playwright install chromium", file=sys.stderr)
    print("  .venv/bin/python scripts/test-b3.py", file=sys.stderr)
    sys.exit(2)


def parse_identity(path):
    """Read identity.yaml with yaml.safe_load and extract the fields
    this test asserts. Raises ValueError if any expected field is
    missing, so a schema change fails loudly instead of silently
    passing with a stale expectation.
    """
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"identity.yaml: cannot read: {exc}")
    except yaml.YAMLError as exc:
        raise ValueError(f"identity.yaml: invalid YAML: {exc}")
    if not isinstance(data, dict):
        raise ValueError("identity.yaml: expected a top-level mapping")

    def field(name):
        v = data.get(name)
        if v is None or (isinstance(v, str) and not v.strip()):
            raise ValueError(f"identity.yaml: missing field {name}")
        return str(v)

    def str_list(name):
        v = data.get(name)
        if not isinstance(v, list) or not v or not all(isinstance(x, str) for x in v):
            raise ValueError(f"identity.yaml: missing list {name}")
        return list(v)

    pubs = data.get("publications")
    if (not isinstance(pubs, list) or len(pubs) != 3
            or any(not isinstance(p, dict) or not p.get("title") or not p.get("url")
                   for p in pubs)):
        raise ValueError("identity.yaml: expected 3 publications with titles and urls")
    profiles = data.get("profiles")
    need = ["github", "githubSecond", "linkedin", "orcid", "medium",
            "substackAuthorProfile", "substackPublication"]
    if (not isinstance(profiles, dict)
            or any(not profiles.get(k) for k in need)):
        raise ValueError("identity.yaml: missing profile urls")

    return {
        "displayName": field("displayName"),
        "fullName": field("fullName"),
        "jobTitle": field("jobTitle"),
        "jobTitleEs": field("jobTitleEs"),
        "tagline": field("tagline"),
        "taglineEs": field("taglineEs"),
        "bio": field("bio"),
        "bioEs": field("bioEs"),
        "description": field("description"),
        "descriptionEs": field("descriptionEs"),
        "personId": field("personId"),
        "siteUrl": field("siteUrl"),
        "knowsAbout": str_list("knowsAbout"),
        "chipsEs": str_list("chipsEs"),
        "publications": [{"title": p["title"], "url": p["url"]} for p in pubs],
        "profiles": profiles,
        "sameAs": [profiles[k] for k in
                   ["github", "githubSecond", "linkedin", "orcid", "medium",
                    "substackAuthorProfile"]],
        "socialHrefs": [profiles[k] for k in
                        ["github", "linkedin", "orcid", "medium",
                         "substackPublication"]],
    }


try:
    ID = parse_identity(IDENTITY)
except ValueError as exc:
    fail(str(exc))

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright is not installed for this Python.", file=sys.stderr)
    print("Set it up once, then rerun:", file=sys.stderr)
    print("  python3 -m venv .venv", file=sys.stderr)
    print('  .venv/bin/pip install "playwright" "pyyaml==6.0.2"', file=sys.stderr)
    print("  .venv/bin/playwright install chromium", file=sys.stderr)
    print("  .venv/bin/python scripts/test-b3.py", file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------- checks
passed = 0
failures = []
skipped = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
    else:
        failures.append(f"{label}: {detail}" if detail else label)


def skip(label, reason):
    skipped.append(f"{label}: {reason}")


def norm_rgb(s):
    return re.sub(r"\s+", "", s or "")


MEASURE_JS = """() => {
  const q = s => document.querySelector(s);
  const qa = s => [...document.querySelectorAll(s)];
  const marker = a => { const m = a.querySelector('span[aria-hidden="true"]');
    return m ? m.textContent.trim() : null; };
  const link = a => a ? { href: a.getAttribute('href'),
    text: a.textContent.replace(/[↗→]/g, '').trim(),
    target: a.getAttribute('target'), rel: a.getAttribute('rel') || '',
    aria: a.getAttribute('aria-label') || '', marker: marker(a) } : null;
  return {
    dataTheme: document.documentElement.getAttribute('data-theme'),
    bodyBg: getComputedStyle(document.body).backgroundColor,
    docScrollW: document.documentElement.scrollWidth,
    winW: window.innerWidth,
    mainW: (() => { const m = q('main.main');
      return m ? Math.round(m.getBoundingClientRect().width) : null; })(),
    h1: qa('h1').map(e => e.textContent.trim()),
    eyebrow: q('.profile-eyebrow') ? q('.profile-eyebrow').textContent.trim() : null,
    tagline: q('.hero-tagline') ? q('.hero-tagline').textContent.trim() : null,
    bio: (() => { const b = q('.profile-panel .entry-content p');
      return b ? b.textContent.trim() : null; })(),
    chips: qa('.profile-chips li').map(e => e.textContent.trim()),
    pubs: qa('.pub h3 a').map(link),
    cta: link(q('.pub-cta')),
    ctaText: q('.pub-cta') ? q('.pub-cta').textContent.trim() : null,
    socials: qa('.profile-social a').map(a => ({ ...link(a),
      svgW: (() => { const s = a.querySelector('svg');
        return s ? Math.round(s.getBoundingClientRect().width) : null; })() })),
    postEntries: qa('.post-entry').length,
    ldjson: [...document.querySelectorAll('script[type="application/ld+json"]')].map(s => {
      try { return JSON.parse(s.textContent); }
      catch (e) { return { __parseError: String(e) }; } }),
  };
}"""


def check_homepage(pg, theme, width, lang, out_dir, results):
    url_path = "/My-AI-Journey/" if lang == "en" else "/My-AI-Journey/es/"
    pg.add_init_script(f"localStorage.setItem('pref-theme','{theme}');")
    resp = pg.goto(f"{BASE}{url_path}", wait_until="networkidle")
    key = f"{theme}-{width}-{lang}"
    check(f"{key} http", resp is not None and resp.status == 200,
          f"status={resp.status if resp else None}")
    pg.wait_for_timeout(300)
    m = pg.evaluate(MEASURE_JS)
    results[key] = m
    pg.screenshot(path=str(out_dir / f"b3-{key}.png"), full_page=True)

    # Theme: the real applied theme, not just the requested one.
    check(f"{key} data-theme", m["dataTheme"] == theme,
          f"got {m['dataTheme']!r}")
    check(f"{key} body bg", norm_rgb(m["bodyBg"]) == norm_rgb(THEME_BG[theme]),
          f"got {m['bodyBg']!r}, want {THEME_BG[theme]!r}")

    # Reflow at every width, including 320px.
    check(f"{key} no overflow", m["docScrollW"] <= m["winW"],
          f"scrollW={m['docScrollW']} winW={m['winW']}")
    if width in (1920, 1440):
        check(f"{key} home shell", m["mainW"] is not None and 1300 <= m["mainW"] <= 1450,
              f"mainW={m['mainW']}")

    # Identity: H1, role eyebrow, tagline, bio, chips.
    check(f"{key} h1", m["h1"] == [ID["displayName"]], f"got {m['h1']!r}")
    role = ID["jobTitleEs"] if lang == "es" else ID["jobTitle"]
    check(f"{key} eyebrow", m["eyebrow"] is not None and role in m["eyebrow"]
          and "Teradata" in m["eyebrow"], f"got {m['eyebrow']!r}")
    want_tag = ID["taglineEs"] if lang == "es" else ID["tagline"]
    check(f"{key} tagline", m["tagline"] == want_tag, f"got {m['tagline']!r}")
    check(f"{key} bio", m["bio"] is not None and BIO_MARK[lang] in m["bio"],
          f"bio missing {BIO_MARK[lang]!r}")
    want_chips = ID["chipsEs"] if lang == "es" else ID["knowsAbout"][:4]
    check(f"{key} chips", m["chips"] == want_chips, f"got {m['chips']!r}")

    # Publications: full titles and URLs, new-tab indication.
    check(f"{key} pub count", len(m["pubs"]) == 3, f"got {len(m['pubs'])}")
    for i, pub in enumerate(ID["publications"]):
        got = m["pubs"][i] if i < len(m["pubs"]) else {}
        check(f"{key} pub{i} title", got.get("text") == pub["title"],
              f"got {got.get('text')!r}")
        check(f"{key} pub{i} href", got.get("href") == pub["url"],
              f"got {got.get('href')!r}")
        check(f"{key} pub{i} target", got.get("target") == "_blank",
              f"got {got.get('target')!r}")
        check(f"{key} pub{i} rel", "noopener" in got.get("rel", ""),
              f"got {got.get('rel')!r}")
        check(f"{key} pub{i} aria", NEW_TAB[lang] in got.get("aria", "")
              and pub["title"] in got.get("aria", ""),
              f"got {got.get('aria')!r}")
        check(f"{key} pub{i} marker", got.get("marker") == "↗",
              f"got {got.get('marker')!r}")

    # Substack CTA.
    cta = m["cta"] or {}
    check(f"{key} cta href", cta.get("href") == ID["profiles"]["substackPublication"],
          f"got {cta.get('href')!r}")
    check(f"{key} cta target", cta.get("target") == "_blank", f"got {cta.get('target')!r}")
    check(f"{key} cta aria", NEW_TAB[lang] in cta.get("aria", ""),
          f"got {cta.get('aria')!r}")
    check(f"{key} cta marker", cta.get("marker") == "→", f"got {cta.get('marker')!r}")

    # Social links: same new-tab indication as publication links.
    check(f"{key} social count", len(m["socials"]) == 5, f"got {len(m['socials'])}")
    for i, want_href in enumerate(ID["socialHrefs"]):
        s = m["socials"][i] if i < len(m["socials"]) else {}
        check(f"{key} social{i} href", s.get("href") == want_href,
              f"got {s.get('href')!r}, want {want_href!r}")
        check(f"{key} social{i} target", s.get("target") == "_blank",
              f"got {s.get('target')!r}")
        check(f"{key} social{i} rel", "noopener" in s.get("rel", ""),
              f"got {s.get('rel')!r}")
        check(f"{key} social{i} aria", NEW_TAB[lang] in s.get("aria", ""),
              f"got {s.get('aria')!r}")
        check(f"{key} social{i} marker", s.get("marker") == "↗",
              f"got {s.get('marker')!r}")
        check(f"{key} social{i} svg", s.get("svgW") == 54, f"got {s.get('svgW')!r}")

    # Homepage carries no blog post list.
    check(f"{key} no post list", m["postEntries"] == 0,
          f"got {m['postEntries']}")

    # JSON-LD invariants.
    blocks = [b for b in m["ldjson"] if isinstance(b, dict)]
    check(f"{key} ld+json parses", all("__parseError" not in b for b in blocks),
          f"{[b for b in blocks if '__parseError' in b]}")
    persons = [b for b in blocks if b.get("@type") == "Person"]
    check(f"{key} person block", len(persons) == 1, f"got {len(persons)}")
    if persons:
        p = persons[0]
        check(f"{key} person name", p.get("name") == ID["fullName"],
              f"got {p.get('name')!r}")
        check(f"{key} person id", p.get("@id") == ID["personId"],
              f"got {p.get('@id')!r}")
        check(f"{key} person jobTitle", p.get("jobTitle") == ID["jobTitle"],
              f"got {p.get('jobTitle')!r}")
        check(f"{key} person sameAs", p.get("sameAs") == ID["sameAs"],
              f"got {p.get('sameAs')!r}")
        check(f"{key} person knowsAbout", p.get("knowsAbout") == ID["knowsAbout"],
              f"got {len(p.get('knowsAbout') or [])} items")
        want_desc = ID["descriptionEs"] if lang == "es" else ID["description"]
        check(f"{key} person desc", p.get("description") == want_desc,
              "description does not match language")
    orgs = [b for b in blocks if b.get("@type") == "Organization"]
    check(f"{key} org block", len(orgs) == 1, f"got {len(orgs)}")
    if orgs:
        check(f"{key} org sameAs",
              orgs[0].get("sameAs") == [ID["profiles"]["substackPublication"]],
              f"got {orgs[0].get('sameAs')!r}")


def fetch_base_inventory():
    """Historical post inventory from the PINNED base commit.

    Returns ({lang: [(slug, title), ...]}, source) where source is
    "api" when the slug list came from the GitHub API at ref=BASE_SHA,
    or "embedded" when the API was unreachable and the embedded
    versioned inventory was used. The titles always come from the
    embedded inventory (verbatim frontmatter at the pinned base).
    When neither source can provide the inventory, strict mode fails
    loudly (the release gate cannot run without a baseline) and local
    mode returns (None, None) so the caller records the base checks
    as skipped, explicitly, instead of passing silently.
    """
    embedded = {lang: dict(pairs) for lang, pairs in BASE_INVENTORY.items()}
    fetched = {}
    api_ok = True
    for lang in ("en", "es"):
        url = (f"{GITHUB_API_BASE}/repos/Ejaramillo1/My-AI-Journey/"
               f"contents/content/{lang}/posts?ref={BASE_SHA}")
        req = urllib.request.Request(url, headers={"User-Agent": "b3-test"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                entries = json.loads(r.read().decode("utf-8"))
        except (OSError, ValueError):
            api_ok = False
            break
        if not isinstance(entries, list):
            api_ok = False
            break
        fetched[lang] = sorted(e["name"] for e in entries if e.get("type") == "dir")
    if api_ok:
        out = {}
        for lang, slugs in fetched.items():
            pairs = []
            for slug in slugs:
                title = embedded[lang].get(slug)
                if title is None:
                    check(f"base-{lang} inventory",
                          False, f"slug {slug} from base {BASE_SHA[:8]} "
                          "has no embedded title; BASE_INVENTORY is stale")
                    continue
                pairs.append((slug, title))
            out[lang] = pairs
        return out, "api"
    if not NO_EMBEDDED_BASE:
        out = {lang: sorted(pairs) for lang, pairs in BASE_INVENTORY.items()}
        return out, "embedded"
    if STRICT:
        fail("base inventory unavailable in strict mode: GitHub API "
             f"unreachable ({GITHUB_API_BASE}) and embedded baseline "
             "disabled (B3_NO_EMBEDDED_BASE=1); the release gate needs "
             "a baseline to prove historical routes are preserved")
    return None, None


def check_posts(pg, lang, base_inv):
    path = "/My-AI-Journey/posts/" if lang == "en" else "/My-AI-Journey/es/posts/"
    resp = pg.goto(f"{BASE}{path}", wait_until="networkidle")
    check(f"posts-{lang} http", resp is not None and resp.status == 200,
          f"status={resp.status if resp else None}")
    n = pg.evaluate("() => [...document.querySelectorAll('.post-entry')].length")
    check(f"posts-{lang} entries", n == POST_COUNT[lang], f"got {n}")
    # Expected posts come from the source content, not a hardcoded list:
    # one directory per post slug under content/<lang>/posts/.
    content_dir = WORK / "content" / lang / "posts"
    slugs = sorted(d.name for d in content_dir.iterdir() if d.is_dir())
    prefix = ID["siteUrl"] + ("es/" if lang == "es" else "") + "posts/"
    want = sorted(f"{prefix}{s}/" for s in slugs)
    hrefs = pg.evaluate(
        "() => [...document.querySelectorAll('.post-entry a.entry-link')]"
        ".map(a => a.getAttribute('href'))")
    check(f"posts-{lang} links", sorted(hrefs) == want,
          f"got {sorted(hrefs)!r}, want {want!r}")

    # Base preservation: every historical post URL from the pinned base
    # must still resolve and render its intended content. Redirects
    # are NOT permitted for these URLs: a redirect means the URL
    # moved, which is a preservation failure, so the final URL must
    # equal the requested URL. Content identity is the expected title
    # (verbatim frontmatter at the pinned base) appearing in the page.
    if base_inv is None:
        skip(f"base-{lang} routes",
             "base inventory unavailable; historical preservation not checked")
        return
    listed = sorted(u[len(prefix):-1] for u in hrefs if u.startswith(prefix))
    missing = sorted(set(s for s, _ in base_inv) - set(listed))
    check(f"base-{lang} all listed", not missing, f"missing: {missing}")
    for slug, title in base_inv:
        sub = "es/" if lang == "es" else ""
        url = f"{BASE}/My-AI-Journey/{sub}posts/{slug}/"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "b3-test"})
            with urllib.request.urlopen(req, timeout=10) as r:
                body = r.read()
                final = r.geturl()
                status = r.status
        except OSError as exc:
            check(f"base-{lang} {slug} loads", False, str(exc))
            continue
        check(f"base-{lang} {slug} status 200", status == 200,
              f"status={status}")
        check(f"base-{lang} {slug} no redirect", final == url,
              f"redirected to {final}")
        text = html.unescape(body.decode("utf-8", "replace"))
        check(f"base-{lang} {slug} title", title in text,
              "detail page does not carry its expected title")
        # The minified detail page writes the article tag unquoted
        # (<article class=post-single>); the marker is the class name.
        check(f"base-{lang} {slug} renders post", b"post-single" in body,
              "detail page has no post-single article")


ABOUT_JS = """() => {
  const q = s => document.querySelector(s);
  const qa = s => [...document.querySelectorAll(s)];
  const marker = a => { const m = a.querySelector('span[aria-hidden="true"]');
    return m ? m.textContent.trim() : null; };
  const link = a => a ? { href: a.getAttribute('href'),
    text: a.textContent.replace(/[↗→]/g, '').trim(),
    target: a.getAttribute('target'), rel: a.getAttribute('rel') || '',
    aria: a.getAttribute('aria-label') || '', marker: marker(a) } : null;
  return {
    docScrollW: document.documentElement.scrollWidth,
    winW: window.innerWidth,
    shareCount: qa('.share-buttons').length,
    socials: qa('.profile-social a').map(a => ({ ...link(a),
      svgW: (() => { const s = a.querySelector('svg');
        return s ? Math.round(s.getBoundingClientRect().width) : null; })() })),
    ldjson: [...document.querySelectorAll('script[type="application/ld+json"]')].map(s => {
      try { return JSON.parse(s.textContent); }
      catch (e) { return { __parseError: String(e) }; } }),
  };
}"""


def check_about(pg, width, lang):
    """About page (issue #5): no share widget, five verified profile
    links, ProfilePage schema preserved. Blog post sharing unchanged."""
    key = f"about-{width}-{lang}"
    url_path = "/My-AI-Journey/about/" if lang == "en" else "/My-AI-Journey/es/about/"
    resp = pg.goto(f"{BASE}{url_path}", wait_until="networkidle")
    check(f"{key} http", resp is not None and resp.status == 200,
          f"status={resp.status if resp else None}")
    pg.wait_for_timeout(300)
    m = pg.evaluate(ABOUT_JS)

    # No share widget on About (disableShare: true).
    check(f"{key} no share buttons", m["shareCount"] == 0,
          f"got {m['shareCount']} .share-buttons")
    # No layout overflow.
    check(f"{key} no overflow", m["docScrollW"] <= m["winW"],
          f"scrollW={m['docScrollW']} winW={m['winW']}")

    # Five verified profile links, same new-tab indication as homepage.
    check(f"{key} social count", len(m["socials"]) == 5,
          f"got {len(m['socials'])}")
    for i, want_href in enumerate(ID["socialHrefs"]):
        s = m["socials"][i] if i < len(m["socials"]) else {}
        check(f"{key} social{i} href", s.get("href") == want_href,
              f"got {s.get('href')!r}, want {want_href!r}")
        check(f"{key} social{i} target", s.get("target") == "_blank",
              f"got {s.get('target')!r}")
        check(f"{key} social{i} rel", "noopener" in s.get("rel", ""),
              f"got {s.get('rel')!r}")
        check(f"{key} social{i} aria", NEW_TAB[lang] in s.get("aria", ""),
              f"got {s.get('aria')!r}")
        check(f"{key} social{i} marker", s.get("marker") == "↗",
              f"got {s.get('marker')!r}")
        check(f"{key} social{i} svg", s.get("svgW") == 54,
              f"got {s.get('svgW')!r}")

    # ProfilePage schema preserved (About emits a ProfilePage block
    # with the Person entity as mainEntity).
    blocks = [b for b in m["ldjson"] if isinstance(b, dict)]
    check(f"{key} ld+json parses", all("__parseError" not in b for b in blocks),
          f"{[b for b in blocks if '__parseError' in b]}")
    profiles = [b for b in blocks if b.get("@type") == "ProfilePage"]
    check(f"{key} profilepage block", len(profiles) == 1,
          f"got {len(profiles)}")
    if profiles:
        main = profiles[0].get("mainEntity") or {}
        check(f"{key} profilepage mainEntity", main.get("@type") == "Person",
              f"got {main.get('@type')!r}")

    # Blog post sharing unchanged: a post still renders share buttons.
    post_path = ("/My-AI-Journey/posts/architecture-layers/"
                 if lang == "en" else "/My-AI-Journey/es/posts/architecture-layers/")
    resp2 = pg.goto(f"{BASE}{post_path}", wait_until="networkidle")
    check(f"{key} post http", resp2 is not None and resp2.status == 200,
          f"status={resp2.status if resp2 else None}")
    pg.wait_for_timeout(300)
    n = pg.evaluate("() => document.querySelectorAll('.share-buttons').length")
    check(f"{key} post share buttons", n == 1, f"got {n}")


CERT_JS = """() => {
  const qa = s => [...document.querySelectorAll(s)];
  const link = a => a ? { href: a.getAttribute('href'),
    target: a.getAttribute('target'), rel: a.getAttribute('rel') || '',
    aria: a.getAttribute('aria-label') || '',
    role: a.getAttribute('role'),
    marker: (() => { const spans = [...a.querySelectorAll('span[aria-hidden="true"]')];
      return spans.some(s => s.textContent.trim() === '↗') ? '↗' : null; })() } : null;
  return {
    docScrollW: document.documentElement.scrollWidth,
    winW: window.innerWidth,
    tiles: qa('.cert-tile').map(link),
    items: qa('.cert-tile-item').length,
    gridIsUl: !!document.querySelector('ul.cert-grid'),
    countText: (() => { const c = document.querySelector('.cert-count');
      return c ? c.textContent.trim() : null; })(),
    menuLabel: (() => { const a = [...document.querySelectorAll('header nav a')].find(x => (x.getAttribute('href') || '').includes('certificates'));
      return a ? a.textContent.trim() : null; })(),
  };
}"""


def load_certificates():
    """Expected certificates from data/certificates.yaml (the single
    source of truth). Raises ValueError on a missing or malformed file,
    so a data change fails loudly instead of silently passing."""
    import yaml
    try:
        data = yaml.safe_load(CERTIFICATES.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"certificates.yaml: cannot read: {exc}")
    except yaml.YAMLError as exc:
        raise ValueError(f"certificates.yaml: invalid YAML: {exc}")
    if not isinstance(data, dict) or not isinstance(data.get("certificates"), list):
        raise ValueError("certificates.yaml: expected a mapping with a certificates list")
    return data["certificates"]


def check_certificates(pg, width, lang):
    """Certificates grid (issue #15 / REVIEW-059): approved tile count,
    correct PDF links, no CVs in source or generated output, keyboard
    focus, no overflow, localized menu label."""
    key = f"cert-{width}-{lang}"
    certs = load_certificates()
    # Source must not contain any CV entry (containment, REVIEW-059).
    check(f"{key} source no cv entries",
          all(c.get("kind") == "certificate" for c in certs),
          f"kinds={sorted({c.get('kind') for c in certs})}")
    check(f"{key} source tile count", len(certs) == 14,
          f"got {len(certs)}")
    url_path = ("/My-AI-Journey/certificates/" if lang == "en"
                else "/My-AI-Journey/es/certificates/")
    resp = pg.goto(f"{BASE}{url_path}", wait_until="networkidle")
    check(f"{key} http", resp is not None and resp.status == 200,
          f"status={resp.status if resp else None}")
    pg.wait_for_timeout(300)
    m = pg.evaluate(CERT_JS)

    # No layout overflow.
    check(f"{key} no overflow", m["docScrollW"] <= m["winW"],
          f"scrollW={m['docScrollW']} winW={m['winW']}")
    # Grid is a <ul> with <li> items; anchors keep their native link
    # role (no role="listitem" overriding it).
    check(f"{key} grid is ul", m["gridIsUl"], "grid is not a <ul>")
    check(f"{key} item count", m["items"] == len(certs),
          f"got {m['items']}")
    check(f"{key} tile count", len(m["tiles"]) == len(certs),
          f"got {len(m['tiles'])}")
    want_count = (f"{len(certs)} "
                  f"{'certificados' if lang == 'es' else 'certificates'}")
    check(f"{key} count text", m["countText"] == want_count,
          f"got {m['countText']!r}")
    # Menu label localized (REVIEW-059).
    want_label = "Certificados" if lang == "es" else "Certificates"
    check(f"{key} menu label", m["menuLabel"] == want_label,
          f"got {m['menuLabel']!r}")

    # Each tile: unique correct PDF href, new-tab indication, no CV.
    seen = set()
    for i, c in enumerate(certs):
        t = m["tiles"][i] if i < len(m["tiles"]) else {}
        want_href = f"/My-AI-Journey/certificates/{c['file']}"
        check(f"{key} tile{i} href", t.get("href") == want_href,
              f"got {t.get('href')!r}, want {want_href!r}")
        check(f"{key} tile{i} unique", t.get("href") not in seen,
              f"duplicate {t.get('href')!r}")
        seen.add(t.get("href"))
        check(f"{key} tile{i} no cv", "cv-" not in (t.get("href") or ""),
              f"got {t.get('href')!r}")
        check(f"{key} tile{i} target", t.get("target") == "_blank",
              f"got {t.get('target')!r}")
        check(f"{key} tile{i} rel", "noopener" in (t.get("rel") or ""),
              f"got {t.get('rel')!r}")
        check(f"{key} tile{i} aria", NEW_TAB[lang] in (t.get("aria") or ""),
              f"got {t.get('aria')!r}")
        check(f"{key} tile{i} marker", t.get("marker") == "↗",
              f"got {t.get('marker')!r}")
        check(f"{key} tile{i} link role", t.get("role") is None,
              f"got role={t.get('role')!r}")

    # Each PDF: HTTP 200, application/pdf, %PDF- signature.
    for i, c in enumerate(certs):
        url = f"{BASE}/My-AI-Journey/certificates/{c['file']}"
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                head = r.read(5)
                ctype = r.headers.get("Content-Type", "")
                check(f"{key} pdf{i} http", r.status == 200,
                      f"status={r.status}")
                check(f"{key} pdf{i} content-type",
                      "application/pdf" in ctype, f"got {ctype!r}")
                check(f"{key} pdf{i} signature", head == b"%PDF-",
                      f"got {head!r}")
        except Exception as e:
            check(f"{key} pdf{i} fetch", False,
                  f"{type(e).__name__}: {e}")

    # Excluded files must 404 in the generated output.
    for bad in ("cv-2023-eduardo-jaramillo.pdf",
                "cv-2024-eduardo-jaramillo.pdf"):
        url = f"{BASE}/My-AI-Journey/certificates/{bad}"
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                check(f"{key} excluded {bad} 404", False,
                      f"returned {r.status}, expected 404")
        except urllib.error.HTTPError as e:
            check(f"{key} excluded {bad} 404", e.code == 404,
                  f"got {e.code}")
        except Exception as e:
            check(f"{key} excluded {bad} 404", False,
                  f"{type(e).__name__}: {e}")

    # Keyboard focus: the first tile link can take focus.
    focused = pg.evaluate("""() => {
      const a = document.querySelector('.cert-tile');
      if (!a) return null;
      a.focus();
      return document.activeElement === a;
    }""")
    check(f"{key} keyboard focus", focused is True, f"got {focused!r}")


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def start_server(serve_dir):
    """In-process HTTP server on loopback only, port 0. The OS assigns
    a free port and the server keeps the bound socket, so there is no
    race between picking a port and binding it, and the build is never
    exposed on the network. The socket is bound in the constructor, so
    the server answers as soon as this returns. If the serving thread
    itself fails to start, the socket is closed before the error
    propagates, so no bound socket is left behind.
    """
    handler = functools.partial(QuietHandler, directory=str(serve_dir))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    try:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    except Exception:
        srv.server_close()
        raise
    return srv


def source_files():
    for name in ("content", "layouts", "data", "assets", "static",
                 "themes", "archetypes", "i18n"):
        d = WORK / name
        if d.is_dir():
            for p in d.rglob("*"):
                if p.is_file() and not any(part.startswith(".") for part in p.parts):
                    yield p
    for name in ("hugo.toml", "hugo.yaml", "hugo.json", "config.toml",
                 "config.yaml", "config.json"):
        p = WORK / name
        if p.is_file():
            yield p


def ensure_build(serve_root):
    """Produce the build that will be served, into serve_root.

    When a Hugo binary is available (HUGO_BIN, or hugo on PATH) the
    site is built into serve_root, a fresh empty directory inside the
    temporary serve tree, so no stale file from an earlier build can
    survive. When no Hugo binary is available, strict mode fails
    loudly (Hugo is required for a release decision) and local mode
    verifies public/ exists and is newer than every source file, then
    copies it into serve_root; that timestamp check is a heuristic,
    not release evidence.
    """
    hugo = os.environ.get("HUGO_BIN") or shutil.which("hugo")
    if hugo:
        try:
            r = subprocess.run([hugo, "--gc", "--minify",
                                "--destination", str(serve_root)],
                               cwd=WORK, capture_output=True, text=True)
        except OSError as exc:
            fail(f"HUGO_BIN={hugo} cannot run: {exc}")
        if r.returncode != 0:
            fail(f"hugo build failed: {r.stderr.strip()[-500:]}")
        return
    if STRICT:
        fail("Hugo is required in strict mode: no HUGO_BIN and no "
             "hugo on PATH; a timestamp-only fallback is not release "
             "evidence, so the release gate cannot run")
    if not (PUBLIC / "index.html").is_file():
        fail("public/ build missing and no hugo found; run "
             "`hugo --gc --minify` in the repo root, or set HUGO_BIN "
             "to a hugo binary")
    newest_public = max((p.stat().st_mtime for p in PUBLIC.rglob("*")
                         if p.is_file()), default=0)
    stale = [str(p) for p in source_files()
             if p.stat().st_mtime > newest_public]
    if stale:
        fail("public/ is stale (source files newer than the build): "
             + ", ".join(stale[:5])
             + "; run `hugo --gc --minify` in the repo root, or set "
             "HUGO_BIN to a hugo binary")
    shutil.copytree(PUBLIC, serve_root)


def main():
    out_env = os.environ.get("B3_TEST_OUT")
    out_dir = Path(out_env) if out_env else Path(tempfile.mkdtemp(prefix="b3-test-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"mode: {'strict' if STRICT else 'local'}")

    base, base_source = fetch_base_inventory()
    if base is not None:
        print(f"base inventory: {base_source} "
              f"(en {len(base['en'])}, es {len(base['es'])} posts, "
              f"base {BASE_SHA[:8]})")

    # TemporaryDirectory is the lifecycle guard: the build output and
    # the served copy are removed even if the build, the server start,
    # or any check fails. No symlink is used, so no platform
    # permission is needed.
    with tempfile.TemporaryDirectory(prefix="b3serve-") as serve_dir:
        root = Path(serve_dir) / "My-AI-Journey"
        ensure_build(root)
        if not (root / "index.html").is_file() or not (root / "es" / "index.html").is_file():
            fail("served build missing the EN or ES homepage after the build step")

        srv = start_server(serve_dir)
        global BASE
        BASE = f"http://127.0.0.1:{srv.server_address[1]}"
        try:
            # One probe so a server problem fails fast with a clear
            # message instead of surfacing as a page-load failure.
            with urllib.request.urlopen(f"{BASE}/My-AI-Journey/", timeout=5) as r:
                if r.status != 200:
                    fail(f"test server answered {r.status}, not 200")

            results = {}
            with sync_playwright() as p:
                browser = p.chromium.launch()
                for theme in ("dark", "light"):
                    for width in (1920, 1440, 390, 320):
                        for lang in ("en", "es"):
                            pg = browser.new_page(viewport={"width": width, "height": 1000})
                            try:
                                check_homepage(pg, theme, width, lang, out_dir, results)
                            finally:
                                pg.close()
                pg = browser.new_page(viewport={"width": 1440, "height": 1000})
                try:
                    check_posts(pg, "en", base["en"] if base else None)
                    check_posts(pg, "es", base["es"] if base else None)
                finally:
                    pg.close()
                # About (issue #5): no share widget, five profile links,
                # ProfilePage preserved; blog post sharing unchanged.
                # Light theme, desktop + narrow widths, both languages.
                for width in (1440, 390):
                    for lang in ("en", "es"):
                        pg = browser.new_page(viewport={"width": width, "height": 1000})
                        try:
                            check_about(pg, width, lang)
                        finally:
                            pg.close()
                # Certificates (issue #15 / REVIEW-059): approved tiles,
                # correct PDF links, no CVs, keyboard focus, no
                # overflow, localized menu label. Same widths/languages.
                for width in (1440, 390):
                    for lang in ("en", "es"):
                        pg = browser.new_page(viewport={"width": width, "height": 1000})
                        try:
                            check_certificates(pg, width, lang)
                        finally:
                            pg.close()
                browser.close()
            (out_dir / "measurements-b3.json").write_text(
                json.dumps(results, indent=1), encoding="utf-8")
        finally:
            srv.shutdown()
            srv.server_close()

    print(f"checks passed: {passed}")
    print(f"checks failed: {len(failures)}")
    print(f"checks skipped: {len(skipped)}")
    if failures:
        print("FAILURES:")
        for f in failures:
            print(f"  - {f}")
    if skipped:
        print("SKIPPED:")
        for s in skipped:
            print(f"  - {s}")
    print(f"evidence: {out_dir}")
    if STRICT and skipped:
        print("STRICT: skipped checks are not allowed for a release decision")
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
