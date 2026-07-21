# modules/consult_docs.py
"""
Consult_docs module - read-only narrative doc lookups over the Obsidian vault.

No DB access, no per-user state: this is a pure filesystem reader, confined
strictly to vault_docs_path (rejects any path escape / traversal attempt).
"""
import os
import re

from logcentral_client import get_logger
from modules.project_registry import slugify, slug_matches

logger = get_logger("sebastian")

_SECTION_HEADING = re.compile(r"^## (.+)$", re.MULTILINE)
_ALIAS_SPLIT = re.compile(r"\s+—\s+|\s+/\s+")
_MAX_SECTION_CHARS = 2000
_FALLBACK_FILES = ("PROJECTS.md", "STACK.md")


class ConsultDocsModule:

    def __init__(self, vault_docs_path):
        self._vault_docs_path = os.path.realpath(vault_docs_path)

    def _resolve_path(self, *parts):
        """Resolve a path under vault_docs_path; returns None if it would escape (path traversal)."""
        candidate = os.path.realpath(os.path.join(self._vault_docs_path, *parts))
        if candidate != self._vault_docs_path and not candidate.startswith(self._vault_docs_path + os.sep):
            logger.warning(f"consult_docs: rejected path escape attempt: {parts}")
            return None
        return candidate

    def _read(self, *parts):
        path = self._resolve_path(*parts)
        if path is None or not os.path.isfile(path):
            return None
        with open(path, encoding="utf-8") as f:
            return f.read()

    def _find_section(self, text, project):
        """Return (heading, body) for the first `## ` section whose alias matches `project`."""
        candidate = slugify(project)
        headings = list(_SECTION_HEADING.finditer(text))
        for i, m in enumerate(headings):
            heading = m.group(1).strip()
            alias = _ALIAS_SPLIT.split(heading, maxsplit=1)[0]
            slug = slugify(alias)
            if slug_matches(candidate, slug):
                start = m.end()
                end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
                return heading, text[start:end].strip()
        return None, None

    def consult(self, project, query):
        """
        Look up documentation for `project` related to `query`.

        Returns:
            {'status': 'found', 'results': [{'source': str, 'content': str}, ...]}
            | {'status': 'not_found'}
        """
        results = []

        projects_md = self._read("PROJECTS.md")
        if projects_md:
            heading, body = self._find_section(projects_md, project)
            if body:
                results.append({
                    "source": f"PROJECTS.md ## {heading}",
                    "content": body[:_MAX_SECTION_CHARS],
                })

        backlog = self._read(project, "backlog.md")
        if backlog and backlog.strip():
            results.append({
                "source": f"{project}/backlog.md",
                "content": backlog.strip()[:_MAX_SECTION_CHARS],
            })

        if not results:
            results.extend(self._grep_fallback(query))

        if not results:
            return {"status": "not_found"}
        return {"status": "found", "results": results}

    def _grep_fallback(self, query):
        """Case-insensitive line grep over PROJECTS.md/STACK.md, used when no section matches."""
        matches = []
        needle = query.lower()
        for fname in _FALLBACK_FILES:
            text = self._read(fname)
            if not text:
                continue
            for line in text.splitlines():
                if needle in line.lower():
                    matches.append({"source": fname, "content": line.strip()})
        return matches
