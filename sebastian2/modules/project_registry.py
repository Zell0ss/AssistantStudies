# modules/project_registry.py
"""
Deterministic project-name validation against PROJECTS.md `## ` headings.

Used by tasks_create (reject unknown projects) and consult_docs (resolve a
project name to its PROJECTS.md section). No DB access — pure vault parsing.
"""
import os
import re

_META_HEADINGS = {"project index", "development standards"}
_ALIAS_SPLIT = re.compile(r"\s+—\s+|\s+/\s+")
_WHITESPACE = re.compile(r"[\s_]+")


def slugify(text):
    """Normalize a heading/alias into a comparable slug: lowercase, spaces/underscores -> hyphens."""
    return _WHITESPACE.sub("-", text.strip().lower())


def slug_matches(a, b):
    """True if normalized slugs `a` and `b` refer to the same project (exact or substring match)."""
    return a == b or a in b or b in a


def project_headings(vault_docs_path):
    """Yield (heading_text, alias_slug) for each real project `## ` section in PROJECTS.md."""
    projects_md = os.path.join(vault_docs_path, "PROJECTS.md")
    with open(projects_md, encoding="utf-8") as f:
        text = f.read()

    for line in text.splitlines():
        if not line.startswith("## "):
            continue
        heading = line[3:].strip()
        if heading.lower() in _META_HEADINGS:
            continue
        alias = _ALIAS_SPLIT.split(heading, maxsplit=1)[0]
        slug = slugify(alias)
        if slug:
            yield heading, slug


def known_project_slugs(vault_docs_path):
    """Return the set of known project slugs, derived from PROJECTS.md `## ` headings."""
    return {slug for _, slug in project_headings(vault_docs_path)}


def is_known_project(project, known_slugs):
    """True if `project` matches (or substring-matches) a known slug."""
    if not project:
        return False
    candidate = slugify(project)
    return any(slug_matches(candidate, slugify(slug)) for slug in known_slugs)
