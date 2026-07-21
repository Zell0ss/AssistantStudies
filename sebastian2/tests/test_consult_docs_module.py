# tests/test_consult_docs_module.py
import pytest

from modules.consult_docs import ConsultDocsModule

PROJECTS_MD = """\
# Projects

## Project Index
Index text.

## glasspannel — Server Control Panel
Puerto: 8420 (backend), 5173 (frontend dev).
Estado: en producción, estable.

## agora — Chat IA con tertulianos
Estado: prototipo inicial, sin desplegar.

## Development Standards
Not a real project.
"""

STACK_MD = """\
# Stack

## Red Tailscale
seb01 corre en la red tailscale interna.
"""


@pytest.fixture
def vault_dir(tmp_path):
    (tmp_path / "PROJECTS.md").write_text(PROJECTS_MD, encoding="utf-8")
    (tmp_path / "STACK.md").write_text(STACK_MD, encoding="utf-8")
    sebastian_dir = tmp_path / "sebastian"
    sebastian_dir.mkdir()
    (sebastian_dir / "backlog.md").write_text("- [ ] revisar fuzzy match\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def docs_module(vault_dir):
    return ConsultDocsModule(str(vault_dir))


def test_consult_finds_project_section(docs_module):
    result = docs_module.consult("glasspannel", "puerto")
    assert result["status"] == "found"
    assert any("8420" in r["content"] for r in result["results"])


def test_consult_result_includes_source_heading(docs_module):
    result = docs_module.consult("glasspannel", "puerto")
    assert any("glasspannel" in r["source"] for r in result["results"])


def test_consult_matches_by_alias_substring(docs_module):
    """'ágora' style partial input should still match the 'agora' section via slug matching."""
    result = docs_module.consult("agora", "estado")
    assert result["status"] == "found"
    assert any("prototipo" in r["content"] for r in result["results"])


def test_consult_includes_project_backlog_when_present(docs_module):
    result = docs_module.consult("sebastian", "fuzzy match")
    assert result["status"] == "found"
    assert any("fuzzy match" in r["content"] for r in result["results"])


def test_consult_falls_back_to_grep_when_no_section_matches(docs_module):
    result = docs_module.consult("proyecto-sin-seccion", "tailscale")
    assert result["status"] == "found"
    assert any("tailscale" in r["content"].lower() for r in result["results"])


def test_consult_returns_not_found_when_nothing_matches(docs_module):
    result = docs_module.consult("proyecto-sin-seccion", "palabra-que-no-existe-en-ningun-lado")
    assert result["status"] == "not_found"


class TestPathTraversalConfinement:
    """The one delicate surface of this sprint: consult_docs reads files off disk based
    on a `project` string that ultimately comes from user text via the LLM planner.
    These tests plant a real secret file OUTSIDE vault_docs_path and prove it cannot
    be reached, rather than just asserting "no error" (which would pass vacuously)."""

    @pytest.fixture
    def vault_with_escapable_secret(self, tmp_path):
        """Vault dir sits inside a parent that also holds a sibling 'secret' dir —
        a `project` value that walks up and back down (`../secret`) would reach it
        if confinement didn't hold."""
        vault = tmp_path / "30-projects"
        vault.mkdir()
        (vault / "PROJECTS.md").write_text("## glasspannel — Server\nnada relevante\n", encoding="utf-8")

        secret_dir = tmp_path / "secret"
        secret_dir.mkdir()
        (secret_dir / "backlog.md").write_text("TOP-SECRET-MARKER-YOU-SHOULD-NEVER-SEE-THIS", encoding="utf-8")

        return vault

    def test_resolve_path_returns_none_for_escaping_project(self, vault_with_escapable_secret):
        """White-box: the guard itself must refuse to resolve a path that walks outside vault_docs_path."""
        module = ConsultDocsModule(str(vault_with_escapable_secret))
        resolved = module._resolve_path("../secret", "backlog.md")
        assert resolved is None

    def test_consult_does_not_leak_sibling_secret_via_backlog_lookup(self, vault_with_escapable_secret):
        """Black-box: consult() with project='../secret' must not surface the secret file's content."""
        module = ConsultDocsModule(str(vault_with_escapable_secret))
        result = module.consult("../secret", "cualquier cosa")
        all_content = " ".join(r["content"] for r in result.get("results", []))
        assert "TOP-SECRET-MARKER-YOU-SHOULD-NEVER-SEE-THIS" not in all_content

    def test_consult_does_not_leak_via_deep_traversal_to_etc_passwd(self, vault_with_escapable_secret):
        """Same guard, absolute-path-style payload an LLM might plausibly emit."""
        module = ConsultDocsModule(str(vault_with_escapable_secret))
        result = module.consult("../../../../../../../../etc/passwd", "root")
        assert result["status"] in ("found", "not_found")
        if result["status"] == "found":
            assert all("root:" not in r["content"] for r in result["results"])
