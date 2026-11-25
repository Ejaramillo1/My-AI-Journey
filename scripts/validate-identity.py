#!/usr/bin/env python3
"""Validate the Person JSON-LD emitted by the My AI Journey Hugo build.

Usage (from the repository root, after building)::

    hugo --minify --gc
    python3 scripts/validate-identity.py public/

Exit code 0 means every check passed. Any failure prints which page and
which field mismatched and exits non-zero.

What it checks, on every built page that should carry the Person entity
(EN + ES homepages, EN + ES About pages, and every EN + ES post page):

* exactly one ``Person`` JSON-LD block per page;
* the Person ``@id``, ``name``, ``alternateName``, ``sameAs`` and
  ``knowsAbout`` are identical on all pages and equal to the values in
  ``data/identity.yaml``;
* no ``Person`` ``sameAs`` array on any page contains a publication URL
  (the My AI Journey Substack publication or the Teradata Labs Medium
  publication).

Note on scope: PaperMod's built-in ``Organization`` block on the homepage
also carries a ``sameAs`` list, built from the site's ``socialIcons``. That
block describes the *site/publication* ("My AI Journey"), not the person, so
the publication URL legitimately appears there; this test deliberately
checks the ``Person`` block only. Changing the Organization block is
out of scope for this test.

Expected values are read from ``data/identity.yaml`` at run time (looked up
as the ``data`` directory next to the given ``public/`` directory, i.e. the
repository root), so the test stays correct when a profile URL changes: edit
the data file and the test follows it. Only the Python standard library is
used. The YAML reader below is deliberately minimal: it parses just the
top-level scalars, the two string lists, and the flat ``profiles:`` mapping
that this test needs, and ignores everything else in the file.

Limitations: this checks the *generated* Person block only. It does not
validate PaperMod's built-in ``BlogPosting``/``WebPage`` blocks, and it does
not replace the Google Rich Results Test or the Schema.org validator for the
live page (see the PR description).
"""

import json
import re
import sys
from pathlib import Path

# Pages that must exist and carry exactly one Person block.
REQUIRED_PAGES = [
    "index.html",
    "es/index.html",
    "about/index.html",
    "es/about/index.html",
]

# Keys this test reads from data/identity.yaml.
SCALAR_KEYS = ("personId", "fullName")
# File key -> Person JSON-LD field. (The file spells it "alternateNames";
# the JSON-LD field is the singular "alternateName".)
LIST_KEYS = {"alternateNames": "alternateName", "knowsAbout": "knowsAbout"}
PROFILE_KEYS = (
    "github",
    "linkedin",
    "orcid",
    "medium",
    "substackAuthorProfile",
)
# sameAs is built from these profile fields, in this order.
SAMEAS_FIELDS = ("github", "linkedin", "orcid", "medium", "substackAuthorProfile")
# Publication URLs: identity-adjacent, but must never appear in sameAs.
PUBLICATION_FIELDS = ("substackPublication", "mediumPublication")

SCRIPT_RE = re.compile(r"<script[^>]*ld\+json[^>]*>(.*?)</script>", re.S)


def _unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def read_identity(path):
    """Minimal reader for the subset of data/identity.yaml this test needs.

    Returns a dict with personId, fullName, alternateName, knowsAbout and
    a profiles dict. Raises ValueError on anything unexpected.
    """
    identity = {"profiles": {}}
    section = None  # current top-level key being read
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip())
        line = raw_line.strip()
        if indent == 0:
            key, sep, value = line.partition(":")
            if not sep:
                raise ValueError(f"cannot parse line in {path}: {raw_line!r}")
            key = key.strip()
            section = key
            if key in SCALAR_KEYS:
                identity[key] = _unquote(value)
            elif key in LIST_KEYS:
                identity[LIST_KEYS[key]] = []
            elif key == "profiles":
                continue
            else:
                section = None  # anything else is out of scope for this test
        elif indent == 2 and section in LIST_KEYS:
            if not line.startswith("- "):
                raise ValueError(f"cannot parse list item in {path}: {raw_line!r}")
            identity[LIST_KEYS[section]].append(_unquote(line[2:]))
        elif indent == 2 and section == "profiles":
            key, sep, value = line.partition(":")
            if not sep:
                raise ValueError(f"cannot parse line in {path}: {raw_line!r}")
            identity["profiles"][key.strip()] = _unquote(value)
        # Deeper indentation (nested records) is ignored.
    missing = [k for k in list(SCALAR_KEYS) + list(LIST_KEYS.values())
               if k not in identity]
    missing += [k for k in PROFILE_KEYS + PUBLICATION_FIELDS
                if k not in identity["profiles"]]
    if missing:
        raise ValueError(f"missing keys in {path}: {', '.join(missing)}")
    return identity


def person_blocks(html):
    """Return the parsed JSON-LD blocks of @type Person found in the HTML."""
    persons = []
    for match in SCRIPT_RE.finditer(html):
        try:
            obj = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise ValueError(f"unparsable JSON-LD block: {exc}") from exc
        if isinstance(obj, dict) and obj.get("@type") == "Person":
            persons.append(obj)
    return persons


def collect_pages(public_dir):
    """Home + About pages (required) plus every built post page."""
    pages = [public_dir / rel for rel in REQUIRED_PAGES]
    posts = sorted(public_dir.glob("posts/*/index.html"))
    posts += sorted(public_dir.glob("es/posts/*/index.html"))
    return pages, posts


def main(argv):
    if len(argv) != 2:
        print("usage: validate-identity.py <built public/ directory>", file=sys.stderr)
        return 2
    public_dir = Path(argv[1])
    if not public_dir.is_dir():
        print(f"error: not a directory: {public_dir}", file=sys.stderr)
        return 2
    identity_path = public_dir.parent / "data" / "identity.yaml"
    if not identity_path.is_file():
        print(f"error: cannot find {identity_path} (expected repo root next "
              f"to {public_dir})", file=sys.stderr)
        return 2
    try:
        identity = read_identity(identity_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    expected = {
        "@id": identity["personId"],
        "name": identity["fullName"],
        "alternateName": identity["alternateName"],
        "sameAs": [identity["profiles"][f] for f in SAMEAS_FIELDS],
        "knowsAbout": identity["knowsAbout"],
    }
    forbidden = [identity["profiles"][f] for f in PUBLICATION_FIELDS]

    failures = []
    required, posts = collect_pages(public_dir)
    for page in required:
        if not page.is_file():
            failures.append(f"{page}: required page is missing from the build")
    pages = [p for p in required if p.is_file()] + [p for p in posts if p.is_file()]
    en_posts = sorted(public_dir.glob("posts/*/index.html"))
    es_posts = sorted(public_dir.glob("es/posts/*/index.html"))
    if not en_posts:
        failures.append("no post pages found under posts/")
    if not es_posts:
        failures.append("no post pages found under es/posts/")

    reference = None
    for page in pages:
        label = str(page.relative_to(public_dir))
        try:
            html = page.read_text(encoding="utf-8")
        except OSError as exc:
            failures.append(f"{label}: cannot read page: {exc}")
            continue
        try:
            persons = person_blocks(html)
        except ValueError as exc:
            failures.append(f"{label}: {exc}")
            continue
        if len(persons) != 1:
            failures.append(
                f"{label}: expected exactly 1 Person block, "
                f"found {len(persons)}")
            continue
        person = persons[0]
        for field, want in expected.items():
            got = person.get(field)
            if got != want:
                failures.append(
                    f"{label}: Person {field} mismatch: got {got!r}, "
                    f"want {want!r}")
        if reference is None:
            reference = {f: person.get(f) for f in expected}
        else:
            for field in expected:
                if person.get(field) != reference[field]:
                    failures.append(
                        f"{label}: Person {field} differs from the "
                        f"first page checked: got {person.get(field)!r}, "
                        f"want {reference[field]!r}")
        person_sameas = person.get("sameAs") or []
        for url in forbidden:
            if url in person_sameas:
                failures.append(
                    f"{label}: publication URL {url} appears inside "
                    f"Person sameAs")

    if failures:
        print(f"FAIL: {len(failures)} problem(s) in {public_dir}")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"PASS: Person @id {expected['@id']} identical on {len(pages)} "
          f"pages ({len(required)} required + {len(posts)} posts); "
          f"sameAs has {len(expected['sameAs'])} author profiles, "
          f"no publication URLs.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
