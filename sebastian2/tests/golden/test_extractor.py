"""Fase 2 H2 (D32): el extractor de hechos con Haiku 4.5 de verdad, 10 casos del plan §3 H2. [API]

Cada caso se lanza UNA vez. Se acepta un atributo con otro nombre si se resuelve por alias o por
descripción al canónico esperado: el test lo comprueba con el catálogo (la misma escalera que el
servicio, con embeddings de OpenAI sobre un Qdrant en memoria), no con el string.

Se lanza con: pytest -m golden tests/golden/test_extractor.py -s
"""
import re
from datetime import date

import pytest

from core.memoria.ajustes import umbrales
from core.memoria.catalogo import Catalogo
from core.memoria.embedder import OpenAIEmbedder
from core.memoria.extractor import MODELO_EXTRACTOR, Extractor
from core.memoria.repositorio import RepositorioMemoria
from core.memoria.servicio import ServicioMemoria
from scripts.memoria.crear_colecciones import crear_colecciones
from tests.golden.uso import USO

USER = "golden_extractor_user"
PRESION = ("presion_neumaticos", "Presión de inflado de los neumáticos de un vehículo")


@pytest.fixture(scope="module")
def entorno(test_db, config_de_goldens):
    """Catálogo real de sebastian_test (semillas) + un atributo de presión que solo existe en este módulo."""
    import anthropic
    from qdrant_client import QdrantClient

    repo = RepositorioMemoria(test_db)
    cur = test_db.cursor()
    cur.execute("DELETE FROM mem_atributo_alias WHERE atributo_id IN"
                " (SELECT id FROM mem_atributos WHERE nombre = %s)", (PRESION[0],))
    cur.execute("DELETE FROM mem_atributos WHERE nombre = %s", (PRESION[0],))
    test_db.commit()
    repo.crear_atributo(PRESION[0], PRESION[1], tipos_entidad="vehiculo", estado="activo")

    qdrant = QdrantClient(":memory:")
    crear_colecciones(qdrant, "extractor_golden")
    embedder = OpenAIEmbedder(config_de_goldens["openai_apikey"])
    catalogo = Catalogo(repo, embedder, qdrant, "extractor_golden")
    catalogo.indexar_atributos()
    extractor = Extractor(anthropic.Anthropic(api_key=config_de_goldens["anthropic_apikey"]),
                          on_usage=USO.registrar)
    servicio = ServicioMemoria(repo, catalogo, extractor, embedder, qdrant, "extractor_golden", umbrales({}))
    yield servicio, extractor, repo
    USO.registrar_embeddings(embedder.tokens)
    cur.execute("DELETE FROM mem_atributo_alias WHERE atributo_id IN"
                " (SELECT id FROM mem_atributos WHERE nombre = %s)", (PRESION[0],))
    cur.execute("DELETE FROM mem_atributos WHERE nombre = %s", (PRESION[0],))
    cur.execute("DELETE FROM mem_entidad_alias WHERE entidad_id IN"
                " (SELECT id FROM mem_entidades WHERE user_id = %s)", (USER,))
    cur.execute("DELETE FROM mem_entidades WHERE user_id = %s", (USER,))
    test_db.commit()


def _extraer(entorno, frase):
    servicio, extractor, repo = entorno
    catalogo = servicio.texto_catalogo(USER)
    hechos = extractor.extraer(frase, catalogo, date.today())
    print(f"\n{frase!r} →")
    for h in hechos:
        print("   ", h)
    return hechos


def _resuelve_a(entorno, hecho, canonico):
    """¿El atributo del hecho es el canónico por alias exacto o por descripción (D35)?"""
    servicio, _, repo = entorno
    res = servicio._resolver_atributo(hecho)
    esperado = repo.atributos_por_alias(canonico)[0]["id"]
    return res.accion == "reutilizar" and res.id == esperado


def _entidades(hechos):
    return {h["entidad"].lower() for h in hechos}


@pytest.mark.golden
def test_01_alergia_de_paco(entorno):
    # H3-revision R10 (cambio del arquitecto, §2.5 3-ii): «contiene el hecho esperado». La frase también dice que Paco
    # es cuñado, y un segundo hecho (parentesco) es correcto; con `[h] = ...` el caso fallaba en 2 de 3 pasadas.
    hechos = _extraer(entorno, "Mi cuñado Paco es alérgico a los frutos secos")
    h = next((x for x in hechos if x["entidad"].lower() == "paco" and "frutos secos" in x["valor"].lower()), None)
    assert h is not None, hechos
    assert h["entidad"].lower() == "paco" and h["tipo_entidad"] == "persona"
    assert _resuelve_a(entorno, h, "alergia")
    assert "frutos secos" in h["valor"].lower() and h["operacion"] == "afirmar"


@pytest.mark.golden
def test_02_correccion_de_la_presion(entorno):
    # H3-revision R10 (cambio del arquitecto, §2.5 3-ii): la frase nombra el coche. Sin él, el modelo ponía la presión
    # en `yo` o en `<UNKNOWN>` en 2 de 3 pasadas, igual con el prompt de antes de R4 (A/B de H3).
    [h] = _extraer(entorno, "Me equivoqué, la presión de las ruedas del coche es 2,4 bares")
    assert "coche" in h["entidad"].lower() or h["tipo_entidad"] == "vehiculo"
    assert _resuelve_a(entorno, h, PRESION[0])
    assert "2,4" in h["valor"] and h["operacion"] == "corregir"


@pytest.mark.golden
def test_03_olvida_las_camisetas_uv(entorno):
    hechos = _extraer(entorno, "Olvida lo de las camisetas UV")
    assert len(hechos) >= 1 and all(h["operacion"] == "retirar" for h in hechos)
    assert "camiseta" in (hechos[0]["entidad"] + hechos[0]["atributo"] + hechos[0]["valor"]).lower()


@pytest.mark.golden
def test_04_decision_sobre_saxhero(entorno):
    hechos = _extraer(entorno, "He decidido no publicar saxhero en GitHub de momento")
    assert len(hechos) >= 1
    h = hechos[0]
    assert h["entidad"].lower() == "saxhero" and h["tipo_entidad"] == "proyecto"
    # H2-revision R4: una decisión que puede cambiar no va a `nota`; cualquier otro atributo, de cardinalidad `uno`
    assert h["operacion"] == "afirmar" and h["atributo"] != "nota" and h["cardinalidad"] == "uno"


@pytest.mark.golden
def test_05_mi_cumpleanos(entorno):
    [h] = _extraer(entorno, "Mi cumpleaños es el 12 de marzo")
    assert h["entidad"].lower() == "yo"
    assert _resuelve_a(entorno, h, "cumpleanos")
    assert re.fullmatch(r"(\d{4}|-)-03-12", h["valor"]), h["valor"]   # --03-12 o AAAA-03-12


@pytest.mark.golden
def test_06_charla_no_es_memoria(entorno):
    assert _extraer(entorno, "Qué tal estás") == []


@pytest.mark.golden
def test_07_hambre_no_es_memoria(entorno):
    assert _extraer(entorno, "Tengo hambre") == []


@pytest.mark.golden
def test_08_paco_y_ana_son_hermanos(entorno):
    hechos = _extraer(entorno, "Paco y Ana son hermanos")
    assert len(hechos) == 2
    assert _entidades(hechos) == {"paco", "ana"}
    assert all(_resuelve_a(entorno, h, "parentesco") or "herman" in h["atributo"].lower()
               or "parent" in h["atributo"].lower() for h in hechos)


@pytest.mark.golden
def test_09_ya_no_vivo_en_gijon(entorno):
    hechos = _extraer(entorno, "Ya no vivo en Gijón, ahora en Oviedo")
    corregidos = [h for h in hechos if h["operacion"] == "corregir"]
    assert corregidos, "tenía que ser una corrección"
    assert corregidos[0]["entidad"].lower() == "yo" and "oviedo" in corregidos[0]["valor"].lower()


@pytest.mark.golden
def test_10_talla_de_camisa(entorno):
    [h] = _extraer(entorno, "Recuerda que mi talla de camisa es la M")
    assert h["entidad"].lower() == "yo" and "talla" in h["atributo"].lower()
    assert h["valor"].strip().upper().rstrip(".") in {"M", "LA M"} and h["operacion"] == "afirmar"
