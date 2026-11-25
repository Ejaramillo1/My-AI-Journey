"""B3 integrated visual test: serve the Hugo build and check the homepage
at 1920/1440/390, dark + light, EN + ES. Prints measurements and saves
screenshots to work-side-space/b3-test/."""
import json, subprocess, sys, time, os
from pathlib import Path

WORK = Path('/home/hatch/workspace/my-ai-journey-central-identity/work-d4')
OUT = Path('/home/hatch/workspace/my-ai-journey-central-identity/work-side-space/b3-test')
OUT.mkdir(parents=True, exist_ok=True)

# Serve public/ under the /My-AI-Journey/ subpath (matches baseURL).
SERVE = Path('/tmp/b3serve')
SERVE.mkdir(parents=True, exist_ok=True)
link = SERVE / 'My-AI-Journey'
if link.is_symlink() or link.exists():
    link.unlink()
link.symlink_to(WORK / 'public')
srv = subprocess.Popen([sys.executable, '-m', 'http.server', '8123', '--directory', str(SERVE)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.5)

from playwright.sync_api import sync_playwright

MEASURE_JS = """() => {
  const q = s => document.querySelector(s);
  const qa = s => [...document.querySelectorAll(s)];
  const main = q('main.main');
  const hub = q('.home-hub');
  const panel = q('.profile-panel');
  const pubcol = q('.pub-col');
  const socials = qa('.profile-social a svg');
  const r = el => el ? el.getBoundingClientRect() : null;
  const mr = r(main), hr = r(hub), pr = r(panel), cr = r(pubcol);
  return {
    docScrollW: document.documentElement.scrollWidth,
    winW: window.innerWidth,
    mainW: mr ? Math.round(mr.width) : null,
    hubW: hr ? Math.round(hr.width) : null,
    panelW: pr ? Math.round(pr.width) : null,
    pubcolW: cr ? Math.round(cr.width) : null,
    panelH: pr ? Math.round(pr.height) : null,
    h1: qa('h1').map(e => e.textContent.trim()),
    h1count: qa('h1').length,
    pubs: qa('.pub').length,
    pubTitles: qa('.pub h3 a').map(a => a.textContent.trim().slice(0, 40)),
    pubTargets: qa('.pub h3 a').map(a => a.getAttribute('target')),
    pubRels: qa('.pub h3 a').map(a => a.getAttribute('rel')),
    socialSvg: socials.map(s => Math.round(s.getBoundingClientRect().width)),
    socialHrefs: qa('.profile-social a').map(a => a.getAttribute('href')),
    cta: q('.pub-cta') ? q('.pub-cta').textContent.trim() : null,
    ctaHref: q('.pub-cta') ? q('.pub-cta').getAttribute('href') : null,
    bioCPL: (() => { const b = q('.profile-panel .entry-content p'); if (!b) return null;
      const cs = getComputedStyle(b); const fs = parseFloat(cs.fontSize);
      return Math.round(b.getBoundingClientRect().width / (fs * 0.5)); })(),
    heroBg: getComputedStyle(q('.profile-panel')).backgroundImage.slice(0, 120),
    postEntries: qa('.post-entry').length,
    linksBlank: qa('a[target="_blank"]').map(a => a.getAttribute('href')),
  };
}"""

results = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path='/home/hatch/.cache/ms-playwright/chromium-1254/chrome-linux64/chrome')
    for theme in ('dark', 'light'):
        for width, name in ((1920, '1920'), (1440, '1440'), (390, '390')):
            for lang, url in (('en', '/My-AI-Journey/'), ('es', '/My-AI-Journey/es/')):
                pg = b.new_page(viewport={'width': width, 'height': 1000})
                if theme == 'light':
                    pg.add_init_script("localStorage.setItem('pref-theme','light');")
                pg.goto(f'http://127.0.0.1:8123{url}', wait_until='networkidle')
                pg.wait_for_timeout(400)
                m = pg.evaluate(MEASURE_JS)
                key = f'{theme}-{name}-{lang}'
                results[key] = m
                pg.screenshot(path=str(OUT / f'b3-{key}.png'), full_page=True)
                pg.close()
    b.close()
srv.terminate()

for k, m in results.items():
    overflow = 'OVERFLOW!' if m['docScrollW'] > m['winW'] else 'ok'
    print(f"{k}: main={m['mainW']} panel={m['panelW']} pubcol={m['pubcolW']} "
          f"h1={m['h1count']} pubs={m['pubs']} socialSvg={m['socialSvg']} "
          f"scrollW={m['docScrollW']} vs win={m['winW']} {overflow} bioCPL~{m['bioCPL']}")
print('--- EN dark 1440 detail:')
print(json.dumps(results['dark-1440-en'], indent=1)[:1800])
Path(OUT / 'measurements-b3.json').write_text(json.dumps(results, indent=1))
print('saved', OUT / 'measurements-b3.json')
