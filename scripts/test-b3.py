"""B3 integrated test: serve the Hugo build and assert the homepage.

Portable: no machine-specific paths, no fixed port, no pinned browser
binary. The server directory and the port are temporary; the browser is
Playwright's default Chromium. Expected values are read from
data/identity.yaml (the single source of truth), so the test checks that
the rendered page matches the data, not a hardcoded copy of it.

Checks, per theme (dark/light) x viewport (1920/1440/390/320) x language
(EN/ES): H1, eyebrow role, tagline, bio, chips, the 3 publications
(full titles and URLs, new-tab target/rel/aria-label/marker), the
Substack CTA, the 5 social links (same new-tab indication), the actual
theme (data-theme attribute plus computed body background), and no
horizontal overflow (320px reflow included). JSON-LD invariants are
checked on every homepage load: Person (name, @id, jobTitle, knowsAbout,
6 sameAs in order) and Organization (sameAs is the Substack publication
only, no personal profiles). Post routes are checked separately:
  /posts/ and /es/posts/ return 200 with 6 / 5 entries, and the
homepage carries no post list.

Usage, from the repo root (work-d4):
    python3 scripts/test-b3.py
Requires Playwright (pip install playwright; playwright install
chromium). If Playwright is missing the script prints setup steps and
exits 2. The site must already be built (public/ must exist); run
`hugo --gc --minify` first. Screenshots and measurements go to a
temporary directory, printed at the end; set B3_TEST_OUT to keep them
in a fixed place. Exit code 0 only if every check passes; 1 otherwise.
The server is stopped and the temporary serve directory removed even
on failure.
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

WORK = Path(__file__).resolve().parents[1]
IDENTITY = WORK / "data" / "identity.yaml"
PUBLIC = WORK / "public"

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
def parse_identity(path):
    """Minimal YAML reader for the flat identity.yaml structure.

    Only the fields this test asserts are parsed; the file is a flat
    mapping plus a few simple lists, so regexes on lines are enough.
    Raises ValueError if any expected field is missing.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    def field(name):
        for ln in lines:
            m = re.match(rf"^{name}: \"(.*)\"$", ln)
            if m:
                return m.group(1)
            m = re.match(rf"^{name}: (.+)$", ln)
            if m:
                return m.group(1).strip()
        raise ValueError(f"identity.yaml: missing field {name}")

    def str_list(name):
        out, in_block = [], False
        for ln in lines:
            if re.match(rf"^{name}:$", ln):
                in_block = True
                continue
            if in_block:
                m = re.match(r"^  - (.+)$", ln)
                if m:
                    out.append(m.group(1).strip())
                    continue
                if ln.strip() and not ln.startswith(" "):
                    break
        if not out:
            raise ValueError(f"identity.yaml: missing list {name}")
        return out

    pubs, cur = [], None
    in_pubs = False
    for ln in lines:
        if ln.startswith("publications:"):
            in_pubs = True
            continue
        if in_pubs:
            m = re.match(r'^  - title: "(.*)"$', ln)
            if m:
                cur = {"title": m.group(1)}
                pubs.append(cur)
                continue
            m = re.match(r"^    url: (\S+)$", ln)
            if m and cur is not None:
                cur["url"] = m.group(1)
                continue
            if ln.strip() and not ln.startswith(" "):
                break
    if len(pubs) != 3 or any("url" not in p for p in pubs):
        raise ValueError("identity.yaml: expected 3 publications with urls")

    profiles = {}
    in_profiles = False
    for ln in lines:
        if ln.startswith("profiles:"):
            in_profiles = True
            continue
        if in_profiles:
            m = re.match(r"^  (github|githubSecond|linkedin|orcid|medium|substackAuthorProfile|substackPublication): (\S+)$", ln)
            if m:
                profiles[m.group(1)] = m.group(2)
                continue
            if ln.strip() and not ln.startswith(" "):
                break
    need = ["github", "githubSecond", "linkedin", "orcid", "medium",
            "substackAuthorProfile", "substackPublication"]
    if any(k not in profiles for k in need):
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
        "publications": pubs,
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
except (OSError, ValueError) as exc:
    fail(str(exc))

if not (PUBLIC / "index.html").is_file() or not (PUBLIC / "es" / "index.html").is_file():
    fail("public/ build missing; run `hugo --gc --minify` in work-d4 first")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright is not installed for this Python.", file=sys.stderr)
    print("Set it up once, then rerun:", file=sys.stderr)
    print("  python3 -m venv ~/workspace/my-ai-journey-central-identity/work-side-space/pw-venv", file=sys.stderr)
    print("  ~/workspace/my-ai-journey-central-identity/work-side-space/pw-venv/bin/pip install playwright", file=sys.stderr)
    print("  ~/workspace/my-ai-journey-central-identity/work-side-space/pw-venv/bin/playwright install chromium", file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------- checks
passed = 0
failures = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
    else:
        failures.append(f"{label}: {detail}" if detail else label)


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


def check_posts(pg, lang):
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


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    out_env = os.environ.get("B3_TEST_OUT")
    out_dir = Path(out_env) if out_env else Path(tempfile.mkdtemp(prefix="b3-test-"))
    out_dir.mkdir(parents=True, exist_ok=True)

    serve_dir = Path(tempfile.mkdtemp(prefix="b3serve-"))
    link = serve_dir / "My-AI-Journey"
    link.symlink_to(PUBLIC, target_is_directory=True)
    port = free_port()
    srv = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port),
         "--directory", str(serve_dir)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    global BASE
    BASE = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            try:
                with urllib.request.urlopen(f"{BASE}/My-AI-Journey/", timeout=2) as r:
                    if r.status == 200:
                        break
            except OSError:
                time.sleep(0.2)
        else:
            fail("test server did not answer")

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
                check_posts(pg, "en")
                check_posts(pg, "es")
            finally:
                pg.close()
            browser.close()
        (out_dir / "measurements-b3.json").write_text(
            json.dumps(results, indent=1), encoding="utf-8")
    finally:
        srv.terminate()
        try:
            srv.wait(timeout=5)
        except subprocess.TimeoutExpired:
            srv.kill()
        shutil.rmtree(serve_dir, ignore_errors=True)

    print(f"checks passed: {passed}")
    print(f"checks failed: {len(failures)}")
    if failures:
        print("FAILURES:")
        for f in failures:
            print(f"  - {f}")
    print(f"evidence: {out_dir}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
