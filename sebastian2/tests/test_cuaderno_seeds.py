# tests/test_cuaderno_seeds.py
"""Seed gathering for Sprint 4 (El cuaderno). Best-effort: any failure degrades to
None, the despertar never crashes for a missing seed. La memoria sale de MariaDB (sebastian_test); el
vault, de un directorio temporal — no real network calls."""
from unittest.mock import MagicMock, patch

import pytest

from core.memoria.repositorio import RepositorioMemoria
from db.connection import close_connection, get_connection
from scripts.cuaderno.seeds import get_random_memory, get_random_note_title

USER = "test_cuaderno_semilla_a"
OTRO = "test_cuaderno_semilla_b"


def _limpiar(c):
    cur = c.cursor()
    u = (USER, OTRO)
    cur.execute("DELETE FROM mem_decisiones WHERE user_id IN (%s, %s)", u)
    cur.execute("UPDATE mem_hechos SET superseded_by = NULL WHERE user_id IN (%s, %s)", u)
    cur.execute("DELETE FROM mem_hechos WHERE user_id IN (%s, %s)", u)
    cur.execute("DELETE FROM mem_fuentes WHERE user_id IN (%s, %s)", u)
    cur.execute("DELETE FROM mem_entidad_alias WHERE entidad_id IN (SELECT id FROM mem_entidades WHERE user_id IN (%s, %s))", u)
    cur.execute("DELETE FROM mem_entidades WHERE user_id IN (%s, %s)", u)
    c.commit()


class TestGetRandomMemory:
    """H4 (plan §3 H4.2): `get_random_memory` saca un hecho vigente al azar del propietario del vault desde MariaDB
    («entidad · atributo: valor»). Contra `sebastian_test`; sin Qdrant."""

    @pytest.fixture
    def conn(self):
        c = get_connection()
        _limpiar(c)
        yield c
        _limpiar(c)
        close_connection()

    def test_cuaderno_semilla_desde_mariadb(self, conn):
        repo = RepositorioMemoria(conn)
        paco = repo.crear_entidad(USER, "Paco", "persona", estado="activo")
        repo.anadir_hecho(USER, paco, repo.atributos_por_alias("alergia")[0]["id"], "frutos secos")

        assert get_random_memory(conn, USER) == "Paco · alergia: frutos secos"

    def test_elige_entre_varios_hechos_y_solo_vigentes(self, conn):
        repo = RepositorioMemoria(conn)
        yo = repo.entidad_usuario(USER)
        alergia = repo.atributos_por_alias("alergia")[0]["id"]
        repo.anadir_hecho(USER, yo, alergia, "polen")
        olvidado = repo.anadir_hecho(USER, yo, alergia, "marisco")
        repo.retirar_y_purgar(USER, olvidado)                                  # D42: cerrado y con el valor en ''

        vistos = {get_random_memory(conn, USER) for _ in range(30)}
        assert vistos == {"yo · alergia: polen"}                                 # nunca el olvidado, ni uno vacío

    def test_cuaderno_sin_hechos_no_falla(self, conn):
        assert get_random_memory(conn, USER) is None                           # sin hechos: se despierta sin esta semilla
        RepositorioMemoria(conn).entidad_usuario(USER)                         # solo la entidad «yo», sin hechos
        assert get_random_memory(conn, USER) is None

    def test_solo_los_hechos_del_propietario(self, conn):
        repo = RepositorioMemoria(conn)
        marisol = repo.crear_entidad(OTRO, "Marisol", "persona", estado="activo")
        repo.anadir_hecho(OTRO, marisol, repo.atributos_por_alias("alergia")[0]["id"], "polen")
        assert get_random_memory(conn, USER) is None

    def test_un_fallo_de_la_bd_devuelve_none_sin_romper(self):
        db = MagicMock()
        db.cursor.side_effect = RuntimeError("MariaDB is down")
        assert get_random_memory(db, USER) is None

    def test_el_aviso_de_un_fallo_no_lleva_valores(self, conn):
        repo = RepositorioMemoria(conn)
        paco = repo.crear_entidad(USER, "Paco", "persona", estado="activo")
        repo.anadir_hecho(USER, paco, repo.atributos_por_alias("alergia")[0]["id"], "valor-secreto-555")
        with patch("scripts.cuaderno.seeds.random.choice", side_effect=RuntimeError("fallo valor-secreto-555")), \
             patch("scripts.cuaderno.seeds.logger") as log:
            assert get_random_memory(conn, USER) is None
        assert "valor-secreto-555" not in " ".join(str(c) for c in log.mock_calls)


class TestGetRandomNoteTitle:
    def test_returns_path_relative_to_vault_of_an_existing_md_file(self, tmp_path):
        wiki = tmp_path / "20-wiki"
        wiki.mkdir()
        (wiki / "RLHF.md").write_text("contenido que nunca debe leerse")

        result = get_random_note_title(tmp_path)
        assert result == "20-wiki/RLHF.md"

    def test_looks_recursively_in_subfolders(self, tmp_path):
        sub = tmp_path / "20-wiki" / "sub"
        sub.mkdir(parents=True)
        (sub / "nota.md").write_text("x")

        result = get_random_note_title(tmp_path)
        assert result == "20-wiki/sub/nota.md"

    def test_no_wiki_folder_returns_none_not_raise(self, tmp_path):
        result = get_random_note_title(tmp_path)
        assert result is None
