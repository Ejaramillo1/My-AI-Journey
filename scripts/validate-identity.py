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
* the Person ``description`` matches the page language: the EN description
  on English pages, ``descriptionEs`` on Spanish pages;
* no ``Person`` ``sameAs`` array on any page contains a publication URL
  (the My AI Journey Substack publication or the Teradata Labs Medium
  publication);
* every real post page emits exactly one ``BlogPosting`` block whose
  author links to the Person entity: ``author`` is exactly
  ``{"@type": "Person", "@id": <personId>}``. All real posts are
  owner-authored, so this check is deliberately owner-only; guest and
  multi-author shapes are covered by the fixture check below, not by
  demanding the owner link for every conceivable author. About and home
  pages emit no ``BlogPosting`` block at all (a missing block used to
  pass vacuously — the counts are now asserted, not just looped over);
* EN + ES About pages emit exactly one ``ProfilePage`` block whose
  ``mainEntity`` is ``{"@type": "Person", "@id": <personId>}`` and whose
  ``@id``/``url`` are the page's canonical permalink; no other page
  emits a ``ProfilePage`` block, and About pages emit no ``BlogPosting``;
* EN + ES homepages emit exactly one ``Organization`` block whose
  ``sameAs`` is exactly the My AI Journey Substack publication URL —
  the publication itself under another address, not personal profiles
  (``sameAs`` asserts the same entity, not its founder/author) and no
  ``mailto:``; no other page emits an ``Organization`` block.

Fixture check (authorship contract)::

    scripts/check-fixtures.sh

builds the test-only content under ``scripts/fixtures/content/`` (three
posts: owner-authored, guest-authored, multi-author) and runs this script
in fixture mode::

    python3 scripts/validate-identity.py --fixtures <fixture public/>
        [--identity data/identity.yaml]

Fixture mode checks that the template's author branches produce the
intended shapes: owner -> the Person ``@id`` link, guest -> a plain
Person with a name, multi-author -> a list of plain Person names. The
fixture build goes to a throwaway directory and is never published.

Expected values are read from ``data/identity.yaml`` at run time (looked up
as the ``data`` directory next to the given ``public/`` directory, i.e. the
repository root, or from ``--identity``), so the test stays correct when a
profile URL changes: edit the data file and the test follows it. Only the
Python standard library is used. The YAML reader below is deliberately
minimal: it parses just the top-level scalars, the two string lists, and
the flat ``profiles:`` mapping that this test needs, and ignores everything
else in the file.

Each page's JSON-LD is parsed exactly once; all per-type checks reuse
that one parse.

Limitations: this checks the *generated* structured-data blocks only. It
does not replace the Google Rich Results Test or the Schema.org validator
for the live page (see the PR description).
"""

import argparse
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

# Homepages (must carry the Organization block) and About pages (must
# carry the ProfilePage block).
HOME_PAGES = ("index.html", "es/index.html")
ABOUT_PAGES = ("about/index.html", "es/about/index.html")

# Fixture posts (scripts/fixtures/content/) and the author shape each
# must produce. Built only by scripts/check-fixtures.sh, never published.
FIXTURE_PAGES = {
    "posts/fixture-owner/index.html": "owner",
    "posts/fixture-guest/index.html": "guest",
    "posts/fixture-multi/index.html": "multi",
}
FIXTURE_GUEST_NAME = "Guest Author"
FIXTURE_MULTI_NAMES = ("Guest Author One", "Guest Author Two")

# Keys this test reads from data/identity.yaml.
SCALAR_KEYS = ("personId", "fullName", "description", "descriptionEs",
               "siteUrl")
# File key -> Person JSON-LD field. (The file spells it "alternateNames";
# the JSON-LD field is the singular "alternateName".)
LIST_KEYS = {"alternateNames": "alternateName", "knowsAbout": "knowsAbout"}
PROFILE_KEYS = (
    "github",
    "githubSecond",
    "linkedin",
    "orcid",
    "medium",
    "substackAuthorProfile",
)
# sameAs is built from these profile fields, in this order.
SAMEAS_FIELDS = ("github", "githubSecond", "linkedin", "orcid", "medium", "substackAuthorProfile")
# The Organization block (the site/publication) carries only the
# publication itself under another address: the My AI Journey Substack
# publication URL. Personal profiles describe the person, not the
# publication, and the mailto: contact is not a profile URL.
ORG_SAMEAS_FIELDS = ("substackPublication",)
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


def jsonld_blocks(html):
    """Return every parsed JSON-LD block (dict) found in the HTML."""
    blocks = []
    for match in SCRIPT_RE.finditer(html):
        try:
            obj = json.loads(match.group(1))
        except json.JSONDecodeError as exc:
            raise ValueError(f"unparsable JSON-LD block: {exc}") from exc
        if isinstance(obj, dict):
            blocks.append(obj)
    return blocks


def author_problem(author, person_id):
    """Return why a BlogPosting ``author`` value violates the intended
    authorship contract, or None if it complies.

    Contract (the template's branches in
    layouts/_partials/templates/schema_json.html):
    * single owner (author string == the full name): exactly
      ``{"@type": "Person", "@id": <personId>}``;
    * single guest (any other author string): exactly
      ``{"@type": "Person", "name": <string>}``;
    * multi-author (a list): a list of plain ``{"@type": "Person",
      "name": <string>}`` entries.
    """
    owner_link = {"@type": "Person", "@id": person_id}
    if author == owner_link:
        return None
    if isinstance(author, dict):
        if set(author) == {"@type", "name"} and author.get("@type") == "Person" \
                and isinstance(author.get("name"), str):
            return None
        return (f"author object is neither the owner @id link nor a guest "
                f"name: {author!r}")
    if isinstance(author, list):
        for entry in author:
            if not (isinstance(entry, dict) and set(entry) == {"@type", "name"}
                    and entry.get("@type") == "Person"
                    and isinstance(entry.get("name"), str)):
                return (f"multi-author entry is not a plain Person name: "
                        f"{entry!r}")
        return None
    return f"author has an unexpected shape: {author!r}"


def parse_page_blocks(html):
    """Parse a page's JSON-LD exactly once and split it by @type.

    Returns (persons, postings, profiles, orgs). Raises ValueError if a
    block is unparsable.
    """
    blocks = jsonld_blocks(html)
    return (
        [b for b in blocks if b.get("@type") == "Person"],
        [b for b in blocks if b.get("@type") == "BlogPosting"],
        [b for b in blocks if b.get("@type") == "ProfilePage"],
        [b for b in blocks if b.get("@type") == "Organization"],
    )


def expected_person(identity):
    return {
        "@id": identity["personId"],
        "name": identity["fullName"],
        "alternateName": identity["alternateName"],
        "sameAs": [identity["profiles"][f] for f in SAMEAS_FIELDS],
        "knowsAbout": identity["knowsAbout"],
    }


def collect_pages(public_dir):
    """Home + About pages (required) plus every built post page."""
    pages = [public_dir / rel for rel in REQUIRED_PAGES]
    posts = sorted(public_dir.glob("posts/*/index.html"))
    posts += sorted(public_dir.glob("es/posts/*/index.html"))
    return pages, posts


def validate_main(public_dir, identity, failures):
    """Validate the real site build. Returns the number of pages checked."""
    expected = expected_person(identity)
    forbidden = [identity["profiles"][f] for f in PUBLICATION_FIELDS]
    # The author link every real BlogPosting must use, and the mainEntity
    # every ProfilePage must carry: a reference to the Person entity,
    # not a name.
    author_link = {"@type": "Person", "@id": identity["personId"]}
    org_sameas = [identity["profiles"][f] for f in ORG_SAMEAS_FIELDS]

    required, posts = collect_pages(public_dir)
    for page in required:
        if not page.is_file():
            failures.append(f"{page}: required page is missing from the build")
    pages = [p for p in required if p.is_file()] + [p for p in posts if p.is_file()]
    post_labels = {str(p.relative_to(public_dir)) for p in posts}
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
            persons, postings, profiles, orgs = parse_page_blocks(html)
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
        # The description follows the page language, not the site default.
        want_desc = (identity["descriptionEs"] if label.startswith("es/")
                     else identity["description"])
        if person.get("description") != want_desc:
            failures.append(
                f"{label}: Person description mismatch: got "
                f"{person.get('description')!r}, want {want_desc!r}")
        # BlogPosting: real posts emit exactly one, with the owner author
        # link; every other page emits none (asserted counts, so a
        # missing block can no longer pass vacuously).
        if label in post_labels:
            if len(postings) != 1:
                failures.append(
                    f"{label}: expected exactly 1 BlogPosting block, "
                    f"found {len(postings)}")
            elif postings[0].get("author") != author_link:
                failures.append(
                    f"{label}: BlogPosting author is not the Person @id "
                    f"link: got {postings[0].get('author')!r}, "
                    f"want {author_link!r}")
        elif postings:
            failures.append(
                f"{label}: unexpected BlogPosting block on a non-post page "
                f"(found {len(postings)})")
        # ProfilePage appears only on About pages, with the Person as
        # mainEntity (a reference, not a duplicated entity) and the page
        # itself identified by @id/url (its canonical permalink).
        if label in ABOUT_PAGES:
            if len(profiles) != 1:
                failures.append(
                    f"{label}: expected exactly 1 ProfilePage block, "
                    f"found {len(profiles)}")
            else:
                profile = profiles[0]
                if profile.get("mainEntity") != author_link:
                    failures.append(
                        f"{label}: ProfilePage mainEntity is not the Person "
                        f"@id link: got {profile.get('mainEntity')!r}, "
                        f"want {author_link!r}")
                want_url = identity["siteUrl"] + (
                    "es/about/" if label.startswith("es/") else "about/")
                if profile.get("@id") != want_url:
                    failures.append(
                        f"{label}: ProfilePage @id mismatch: got "
                        f"{profile.get('@id')!r}, want {want_url!r}")
                if profile.get("url") != want_url:
                    failures.append(
                        f"{label}: ProfilePage url mismatch: got "
                        f"{profile.get('url')!r}, want {want_url!r}")
        elif profiles:
            failures.append(
                f"{label}: unexpected ProfilePage block on a non-About page")
        # The Organization block (the site/publication) appears only on
        # homepages, with sameAs holding only the publication itself
        # (Substack publication URL); personal profiles and mailto: do
        # not belong here because sameAs asserts the same entity.
        if label in HOME_PAGES:
            if len(orgs) != 1:
                failures.append(
                    f"{label}: expected exactly 1 Organization block, "
                    f"found {len(orgs)}")
            elif orgs[0].get("sameAs") != org_sameas:
                failures.append(
                    f"{label}: Organization sameAs mismatch: got "
                    f"{orgs[0].get('sameAs')!r}, want {org_sameas!r}")
        elif orgs:
            failures.append(
                f"{label}: unexpected Organization block on a non-home page")
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
    return len(pages), len(required), len(posts)


def validate_fixtures(public_dir, identity, failures):
    """Validate the fixture build: the three authorship shapes."""
    person_id = identity["personId"]
    author_link = {"@type": "Person", "@id": person_id}
    want_authors = {
        "owner": author_link,
        "guest": {"@type": "Person", "name": FIXTURE_GUEST_NAME},
        "multi": [{"@type": "Person", "name": n}
                  for n in FIXTURE_MULTI_NAMES],
    }
    checked = 0
    for rel, kind in FIXTURE_PAGES.items():
        page = public_dir / rel
        if not page.is_file():
            failures.append(f"{rel}: fixture page is missing from the build")
            continue
        try:
            html = page.read_text(encoding="utf-8")
        except OSError as exc:
            failures.append(f"{rel}: cannot read page: {exc}")
            continue
        try:
            blocks = jsonld_blocks(html)
        except ValueError as exc:
            failures.append(f"{rel}: {exc}")
            continue
        checked += 1
        persons = [b for b in blocks if b.get("@type") == "Person"]
        if len(persons) != 1:
            failures.append(
                f"{rel}: expected exactly 1 Person block, "
                f"found {len(persons)}")
        postings = [b for b in blocks if b.get("@type") == "BlogPosting"]
        if len(postings) != 1:
            failures.append(
                f"{rel}: expected exactly 1 BlogPosting block, "
                f"found {len(postings)}")
            continue
        author = postings[0].get("author")
        problem = author_problem(author, person_id)
        if problem is not None:
            failures.append(f"{rel}: {problem}")
        if author != want_authors[kind]:
            failures.append(
                f"{rel}: BlogPosting author mismatch for the {kind} case: "
                f"got {author!r}, want {want_authors[kind]!r}")
        if [b for b in blocks if b.get("@type") == "ProfilePage"]:
            failures.append(f"{rel}: unexpected ProfilePage block on a post")
        if [b for b in blocks if b.get("@type") == "Organization"]:
            failures.append(f"{rel}: unexpected Organization block on a post")
    return checked


def main(argv):
    parser = argparse.ArgumentParser(
        description="Validate the Person JSON-LD of a My AI Journey build.")
    parser.add_argument("public_dir", type=Path,
                        help="built public/ directory to check")
    parser.add_argument("--fixtures", action="store_true",
                        help="check the fixture build instead (see "
                             "scripts/check-fixtures.sh)")
    parser.add_argument("--identity", type=Path, default=None,
                        help="path to data/identity.yaml (default: "
                             "<public_dir>/../data/identity.yaml)")
    args = parser.parse_args(argv)
    public_dir = args.public_dir
    if not public_dir.is_dir():
        print(f"error: not a directory: {public_dir}", file=sys.stderr)
        return 2
    identity_path = args.identity or (public_dir.parent / "data"
                                      / "identity.yaml")
    if not identity_path.is_file():
        print(f"error: cannot find {identity_path} (expected repo root next "
              f"to {public_dir})", file=sys.stderr)
        return 2
    try:
        identity = read_identity(identity_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    failures = []
    if args.fixtures:
        checked = validate_fixtures(public_dir, identity, failures)
        if failures:
            print(f"FAIL: {len(failures)} problem(s) in {public_dir}")
            for failure in failures:
                print(f"  - {failure}")
            return 1
        print(f"PASS: authorship fixtures OK on {checked} pages "
              f"(owner -> Person @id link, guest -> Person name, "
              f"multi-author -> list of Person names).")
        return 0

    n_pages, n_required, n_posts = validate_main(public_dir, identity,
                                                 failures)
    if failures:
        print(f"FAIL: {len(failures)} problem(s) in {public_dir}")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"PASS: Person @id {identity['personId']} identical on {n_pages} "
          f"pages ({n_required} required + {n_posts} posts); "
          f"sameAs has {len(expected_person(identity)['sameAs'])} author profiles, "
          f"no publication URLs; descriptions localized per language; "
          f"BlogPosting authors link to #person (exactly one per post, none "
          f"elsewhere); ProfilePage on About pages only, with the page "
          f"permalink as @id/url; Organization sameAs is the Substack "
          f"publication URL only.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
