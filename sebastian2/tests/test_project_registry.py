# tests/test_project_registry.py
import pytest

from modules.project_registry import known_project_slugs, is_known_project, slugify

FAKE_PROJECTS_MD = """\
# Projects

## Project Index
Some index text, not a real project.

## Sebastian 2.0 — Personal Assistant Telegram Bot
Content here.

## scroogebot / TioGilitoBot — Paper Trading Bot
Content here.

## claude-lite — Cliente web personal para Claude
Content here.

## Fantasy Novel
Content here.

## obsidian_wiki_processor — LLM-Powered Personal Wiki Pipeline
Content here.

## saxhero — Sax Practice App
Content here.

## Development Standards
Not a real project either.
"""


@pytest.fixture
def vault_dir(tmp_path):
    (tmp_path / "PROJECTS.md").write_text(FAKE_PROJECTS_MD, encoding="utf-8")
    return tmp_path


def test_known_project_slugs_excludes_meta_headings(vault_dir):
    slugs = known_project_slugs(str(vault_dir))
    assert "project-index" not in slugs
    assert "development-standards" not in slugs


def test_known_project_slugs_extracts_first_alias(vault_dir):
    slugs = known_project_slugs(str(vault_dir))
    assert "sebastian-2.0" in slugs
    assert "scroogebot" in slugs
    assert "claude-lite" in slugs


def test_known_project_slugs_normalizes_spaces_and_underscores(vault_dir):
    slugs = known_project_slugs(str(vault_dir))
    assert "fantasy-novel" in slugs
    assert "obsidian-wiki-processor" in slugs
    assert "saxhero" in slugs


def test_is_known_project_exact_match():
    assert is_known_project("saxhero", {"saxhero", "scroogebot"})


def test_is_known_project_substring_match():
    assert is_known_project("sebastian", {"sebastian-2.0"})


def test_is_known_project_case_insensitive():
    assert is_known_project("SaxHero", {"saxhero"})


def test_is_known_project_rejects_unknown():
    assert not is_known_project("proyecto-inventado-xyz", {"saxhero", "scroogebot"})


def test_is_known_project_rejects_empty():
    assert not is_known_project("", {"saxhero"})
    assert not is_known_project(None, {"saxhero"})


def test_slugify_normalizes_whitespace_and_underscores():
    assert slugify("Fantasy Novel") == "fantasy-novel"
    assert slugify("obsidian_wiki_processor") == "obsidian-wiki-processor"
    assert slugify("  Saxhero  ") == "saxhero"
