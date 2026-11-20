"""H3 (fase 2, plan §2.3 y §3 H3.5): `ServicioMemoria.consultar` (la tool `search_memory`), con embedder falso,
Qdrant en memoria y `sebastian_test`. Cubre D33 (por usuario), D37 (el vault gana y avisa) y que la entidad
y el atributo se resuelven **solo por alias exacto**."""
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.memoria.ajustes import umbrales
from core.memoria.catalogo import Catalogo
from core.memoria.repositorio import RepositorioMemoria
from core.memoria.servicio import ServicioMemoria
from db.connection import close_connection, get_connection
from scripts.memoria.crear_colecciones import crear_colecciones
from tests.fakes_memoria import EmbedderFalso, qdrant_en_memoria

USER = "test_mem_consulta_a"
OTRO = "test_mem_consulta_b"
BASE = "con_test"


def _limpiar(conn):
    cur = conn.cursor()
    u = (USER, OTRO)
    cur.execute("DELETE FROM mem_decisiones WHERE user_id IN (%s, %s)", u)
    cur.execute("UPDATE mem_hechos SET superseded_by = NULL WHERE user_id IN (%s, %s)", u)
    cur.execute("DELETE FROM mem_hechos WHERE user_id IN (%s, %s)", u)
    cur.execute("DELETE FROM mem_entidad_alias WHERE entidad_id IN"
                " (SELECT id FROM mem_entidades WHERE user_id IN (%s, %s))", u)
    cur.execute("DELETE FROM mem_entidades WHERE user_id IN (%s, %s)", u)
    cur.execute("DELETE FROM mem_atributo_alias WHERE atributo_id IN"
                " (SELECT id FROM mem_atributos WHERE nombre LIKE %s)", (f"%_{BASE}",))
    cur.execute("DELETE FROM mem_atributos WHERE nombre LIKE %s", (f"%_{BASE}",))
    conn.commit()


class _Extractor:
    def extraer(self, texto, catalogo, hoy):   # pragma: no cover - consultar no lo usa
        raise AssertionError("consultar no llama al extractor")


@pytest.fixture
def entorno(tmp_path):
    conn = get_connection()
    _limpiar(conn)
    repo = RepositorioMemoria(conn)
    cliente = qdrant_en_memoria()
    crear_colecciones(cliente, BASE)
    embedder = EmbedderFalso()
    catalogo = Catalogo(repo, embedder, cliente, BASE)
    catalogo.indexar_atributos()

    def servicio(vault=None, propietario=USER):
        return ServicioMemoria(repo, catalogo, _Extractor(), embedder, cliente, BASE, umbrales({}),
                               hoy=lambda: date(2026, 10, 16),
                               vault_path=str(vault) if vault else None, propietario_vault=propietario)

    def hecho(user, entidad, tipo, atributo, valor, *, indexar=False):
        """Siembra un hecho directamente en SQL (y, si se pide, la entidad en el catalogo)."""
        e = repo.entidades_por_alias(user, entidad)
        eid = e[0]["id"] if e else repo.crear_entidad(user, entidad, tipo, estado="activo")
        if indexar:
            catalogo.indexar_entidad(repo.entidad(eid))
        aid = repo.atributos_por_alias(atributo)[0]["id"]
        return repo.anadir_hecho(user, eid, aid, valor)

    yield SimpleNamespace(repo=repo, cliente=cliente, catalogo=catalogo, embedder=embedder,
                          servicio=servicio, hecho=hecho, tmp=tmp_path)
    _limpiar(conn)
    close_connection()


def _vault(tmp, **campos):
    carpeta = tmp / "30-projects" / "proyecto-prueba"
    carpeta.mkdir(parents=True)
    frontmatter = "\n".join(f"{k}: {v}" for k, v in {"contrato": 2, **campos}.items())
    (carpeta / "proyecto.md").write_text(f"---\n{frontmatter}\n---\n", encoding="utf-8")
    return tmp / "30-projects"


# --- hechos: entidad y atributo por alias exacto ----------------------------------------------

def test_la_salida_tiene_las_claves_del_contrato(entorno):
    salida = entorno.servicio().consultar(USER, "lo que sea")
    assert set(salida) == {"hechos", "historial", "notas", "vault", "conflictos"}
    assert salida == {"hechos": [], "historial": [], "notas": [], "vault": None, "conflictos": []}


def test_entidad_y_atributo_devuelven_los_vigentes(entorno):
    entorno.hecho(USER, "Paco", "persona", "alergia", "frutos secos")
    entorno.hecho(USER, "Paco", "persona", "parentesco", "cuñado")
    salida = entorno.servicio().consultar(USER, "¿qué alergias tiene Paco?", entidad="Paco", atributo="alergias")

    assert [(h["entidad"], h["atributo"], h["valor"]) for h in salida["hechos"]] == [
        ("Paco", "alergia", "frutos secos")]
    assert salida["hechos"][0]["desde"] == date.today().isoformat()


def test_solo_entidad_devuelve_todos_sus_hechos_vigentes(entorno):
    entorno.hecho(USER, "Paco", "persona", "alergia", "frutos secos")
    entorno.hecho(USER, "Paco", "persona", "parentesco", "cuñado")
    entorno.hecho(USER, "Ana", "persona", "alergia", "polen")
    salida = entorno.servicio().consultar(USER, "Paco", entidad="paco")
    assert sorted(h["atributo"] for h in salida["hechos"]) == ["alergia", "parentesco"]


def test_solo_atributo_devuelve_ese_atributo_de_todas_las_entidades(entorno):
    entorno.hecho(USER, "Paco", "persona", "alergia", "frutos secos")
    entorno.hecho(USER, "Ana", "persona", "alergia", "polen")
    entorno.hecho(USER, "Ana", "persona", "parentesco", "hermana")
    salida = entorno.servicio().consultar(USER, "alergias", atributo="alergia")
    assert sorted((h["entidad"], h["valor"]) for h in salida["hechos"]) == [("Ana", "polen"), ("Paco", "frutos secos")]


def test_yo_se_resuelve_a_la_entidad_del_usuario(entorno):
    yo = entorno.repo.entidad_usuario(USER, "Josem")
    entorno.repo.anadir_hecho(USER, yo, entorno.repo.atributos_por_alias("alergia")[0]["id"], "polen")
    assert [h["valor"] for h in entorno.servicio().consultar(USER, "mis alergias", entidad="yo")["hechos"]] == ["polen"]


def test_search_memory_no_resuelve_por_semantica(entorno):
    """La entidad solo se resuelve por alias exacto: «paco persona» comparte todas las palabras con el texto
    indexado de Paco («Paco: persona», puntuacion 1,0) y aun asi no es un alias suyo."""
    entorno.hecho(USER, "Paco", "persona", "alergia", "frutos secos", indexar=True)
    buscar = entorno.catalogo.buscar_entidades(USER, "paco persona")
    assert buscar and buscar[0]["score"] > 0.99          # la semantica SI lo encontraria...

    salida = entorno.servicio().consultar(USER, "x", entidad="paco persona")
    assert salida["hechos"] == []                         # ...y consultar no la usa


def test_un_atributo_o_una_entidad_pedidos_y_no_resueltos_no_amplian_la_consulta(entorno):
    entorno.hecho(USER, "Paco", "persona", "alergia", "frutos secos")
    servicio = entorno.servicio()
    # H1f (D71, R14) cambia este esperado: con la entidad resuelta y el atributo no, ya no se contesta «nada», se devuelven los
    # hechos vigentes de la entidad (con la señal `atributo_no_resuelto`). Lo demás sigue igual: no se amplía a «todo».
    con_atributo_inventado = servicio.consultar(USER, "x", entidad="Paco", atributo="inventado")
    assert [h["valor"] for h in con_atributo_inventado["hechos"]] == ["frutos secos"]
    assert con_atributo_inventado["atributo_no_resuelto"] is True
    assert servicio.consultar(USER, "x", entidad="Nadie")["hechos"] == []
    assert servicio.consultar(USER, "x", entidad="Nadie", atributo="alergia")["hechos"] == []
    assert servicio.consultar(USER, "x", atributo="inventado")["hechos"] == []


def test_no_devuelve_hechos_de_otro_usuario(entorno):
    entorno.hecho(OTRO, "Paco", "persona", "alergia", "marisco")
    salida = entorno.servicio().consultar(USER, "alergias de Paco", entidad="Paco", atributo="alergia")
    assert salida["hechos"] == [] and salida["notas"] == []


# --- historial ---------------------------------------------------------------------------------

def _presion(entorno):
    eid = entorno.repo.crear_entidad(USER, "coche", "vehiculo", estado="activo")
    aid = entorno.repo.crear_atributo(f"presion_{BASE}", "Presión de las ruedas", cardinalidad="uno")
    viejo = entorno.repo.anadir_hecho(USER, eid, aid, "2,30 bar")
    entorno.repo.sustituir_hecho(USER, viejo, eid, aid, "2,4 bar")
    return "coche", f"presion_{BASE}"


def test_sin_historial_solo_el_vigente(entorno):
    entidad, atributo = _presion(entorno)
    salida = entorno.servicio().consultar(USER, "presion", entidad=entidad, atributo=atributo)
    assert [h["valor"] for h in salida["hechos"]] == ["2,4 bar"] and salida["historial"] == []


def test_con_historial_trae_los_cerrados_y_quien_los_sustituyo(entorno):
    entidad, atributo = _presion(entorno)
    salida = entorno.servicio().consultar(USER, "presion", entidad=entidad, atributo=atributo, historial=True)
    assert [h["valor"] for h in salida["hechos"]] == ["2,4 bar"]
    [antes] = salida["historial"]
    assert antes["valor"] == "2,30 bar" and antes["sustituido_por"] == "2,4 bar"
    assert antes["desde"] == date.today().isoformat() and antes["hasta"] == date.today().isoformat()


def test_un_hecho_retirado_sale_en_el_historial_sin_sustituto(entorno):
    hid = entorno.hecho(USER, "Paco", "persona", "alergia", "marisco")
    entorno.repo.retirar_hecho(hid)
    salida = entorno.servicio().consultar(USER, "x", entidad="Paco", atributo="alergia", historial=True)
    assert salida["hechos"] == []
    assert [(h["valor"], h["sustituido_por"]) for h in salida["historial"]] == [("marisco", None)]


# --- notas ---------------------------------------------------------------------------------------

def _con_nota(entorno, user, texto, entidad="yo"):
    """Una nota tal como la deja `guardar`: hecho con atributo `nota` + punto en <base>_notas."""
    from qdrant_client.models import PointStruct
    yo = entorno.repo.entidad_usuario(user)
    hid = entorno.repo.anadir_hecho(user, yo, entorno.repo.atributos_por_alias("nota")[0]["id"], texto)
    entorno.cliente.upsert(collection_name=f"{BASE}_notas", points=[PointStruct(
        id=hid, vector=entorno.embedder.embed([texto])[0], payload={"hecho_id": hid, "user_id": user})])
    return hid


def test_las_notas_se_buscan_por_similitud_y_son_del_usuario(entorno):
    _con_nota(entorno, USER, "Uso camisetas UV para bañarme en verano")
    _con_nota(entorno, OTRO, "Uso camisetas UV para bañarme en verano")
    salida = entorno.servicio().consultar(USER, "camisetas UV para bañarme")
    assert [n["texto"] for n in salida["notas"]] == ["Uso camisetas UV para bañarme en verano"]


def test_una_nota_poco_parecida_no_sale(entorno):
    _con_nota(entorno, USER, "Uso camisetas UV para bañarme en verano")
    assert entorno.servicio().consultar(USER, "presion de las ruedas")["notas"] == []


def test_una_nota_cerrada_no_sale(entorno):
    hid = _con_nota(entorno, USER, "Uso camisetas UV para bañarme en verano")
    entorno.repo.retirar_hecho(hid)
    assert entorno.servicio().consultar(USER, "camisetas UV para bañarme")["notas"] == []


def test_como_mucho_tres_notas(entorno):
    for i in range(5):
        _con_nota(entorno, USER, f"Uso camisetas UV para bañarme en verano numero{i}")
    assert len(entorno.servicio().consultar(USER, "camisetas UV para bañarme en verano")["notas"]) == 3


def test_si_falla_el_embedder_los_hechos_siguen_y_las_notas_no(entorno):
    entorno.hecho(USER, "Paco", "persona", "alergia", "frutos secos")
    servicio = entorno.servicio()
    servicio._embedder = MagicMock(embed=MagicMock(side_effect=RuntimeError("openai caido")))
    salida = servicio.consultar(USER, "alergias", entidad="Paco", atributo="alergia")
    assert [h["valor"] for h in salida["hechos"]] == ["frutos secos"] and salida["notas"] == []


# --- vault (D37) -----------------------------------------------------------------------------------

def test_vault_gana_y_avisa(entorno):
    vault = _vault(entorno.tmp, estado="stable")
    entorno.hecho(USER, "proyecto-prueba", "proyecto", "estado", "pausado")
    salida = entorno.servicio(vault).consultar(USER, "¿en qué estado está proyecto-prueba?",
                                               entidad="proyecto-prueba", atributo="estado")

    assert salida["vault"] == {"proyecto": "proyecto-prueba", "campos": {"estado": "stable"}}
    assert [h["valor"] for h in salida["hechos"]] == ["pausado"]        # lo dicho sigue visible...
    [c] = salida["conflictos"]                                          # ...pero marcado: gana el vault
    assert (c["entidad"], c["atributo"], c["vault"], c["conversacion"], c["gana"]) == (
        "proyecto-prueba", "estado", "stable", "pausado", "vault")


def test_si_coinciden_no_hay_conflicto(entorno):
    vault = _vault(entorno.tmp, estado="stable")
    entorno.hecho(USER, "proyecto-prueba", "proyecto", "estado", "Stable")
    salida = entorno.servicio(vault).consultar(USER, "estado", entidad="proyecto-prueba", atributo="estado")
    assert salida["vault"]["campos"] == {"estado": "stable"} and salida["conflictos"] == []


def test_el_vault_responde_aunque_la_entidad_no_este_en_la_memoria(entorno):
    vault = _vault(entorno.tmp, estado="stable", host="seb01")
    salida = entorno.servicio(vault).consultar(USER, "x", entidad="proyecto-prueba")
    assert salida["hechos"] == [] and salida["conflictos"] == []
    assert salida["vault"] == {"proyecto": "proyecto-prueba", "campos": {"estado": "stable", "host": "seb01"}}


def test_con_atributo_solo_va_ese_campo_del_vault(entorno):
    vault = _vault(entorno.tmp, estado="stable", host="seb01")
    salida = entorno.servicio(vault).consultar(USER, "x", entidad="proyecto-prueba", atributo="host")
    assert salida["vault"]["campos"] == {"host": "seb01"}


def test_un_atributo_que_no_es_del_contrato_no_trae_vault(entorno):
    vault = _vault(entorno.tmp, estado="stable")
    assert entorno.servicio(vault).consultar(USER, "x", entidad="proyecto-prueba", atributo="alergia")["vault"] is None


def test_el_vault_solo_es_del_propietario(entorno):
    vault = _vault(entorno.tmp, estado="stable")
    entorno.hecho(OTRO, "proyecto-prueba", "proyecto", "estado", "pausado")
    salida = entorno.servicio(vault, propietario=USER).consultar(OTRO, "x", entidad="proyecto-prueba",
                                                                 atributo="estado")
    assert salida["vault"] is None and salida["conflictos"] == []
    assert [h["valor"] for h in salida["hechos"]] == ["pausado"]


def test_sin_vault_configurado_no_hay_vault(entorno):
    entorno.hecho(USER, "proyecto-prueba", "proyecto", "estado", "pausado")
    assert entorno.servicio(None).consultar(USER, "x", entidad="proyecto-prueba")["vault"] is None


# --- privacidad ---------------------------------------------------------------------------------------

def test_el_log_de_consultar_no_lleva_valores_ni_consulta(entorno):
    entorno.hecho(USER, "Paco", "persona", "alergia", "valor-secreto-123")
    _con_nota(entorno, USER, "nota-secreta-456")
    servicio = entorno.servicio()
    with patch("core.memoria.servicio.logger") as log_servicio, patch("core.memoria.repositorio.logger") as log_repo:
        servicio.consultar(USER, "consulta-secreta-789", entidad="Paco", atributo="alergia")
    llamadas = [str(c) for log in (log_servicio, log_repo) for c in log.mock_calls]
    assert llamadas, "tiene que dejar alguna traza"
    for secreto in ("valor-secreto-123", "nota-secreta-456", "consulta-secreta-789"):
        assert not any(secreto in l for l in llamadas), secreto
