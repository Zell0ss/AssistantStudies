"""H2 (fase 2, plan §3 H2.3): ServicioMemoria.guardar con extractor y embedder falsos, contra sebastian_test."""
import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from core.memoria.ajustes import umbrales
from core.memoria.catalogo import Catalogo
from core.memoria.repositorio import RepositorioMemoria
from core.memoria.servicio import ServicioMemoria
from db.connection import close_connection, get_connection
from scripts.memoria.crear_colecciones import crear_colecciones
from tests.fakes_memoria import EmbedderFalso, qdrant_en_memoria

USER = "test_mem_servicio_a"
OTRO = "test_mem_servicio_b"
SUFIJO = "_svc_test"


def _hecho(**kw):
    base = {"entidad": "Paco", "tipo_entidad": "persona", "atributo": "alergia", "tipo_valor": "texto",
            "cardinalidad": "varios", "valor": "frutos secos", "operacion": "afirmar",
            "descripcion_atributo": "", "ejemplos": []}
    return {**base, **kw}


class ExtractorFalso:
    def __init__(self, hechos=None, error=None):
        self.hechos, self.error, self.llamadas = hechos or [], error, []

    def extraer(self, texto, catalogo, hoy):
        self.llamadas.append((texto, catalogo, hoy))
        if self.error:
            raise self.error
        return self.hechos


def _limpiar(conn):
    cur = conn.cursor()
    usuarios = (USER, OTRO)
    cur.execute("DELETE FROM mem_decisiones WHERE user_id IN (%s, %s)", usuarios)
    cur.execute("UPDATE mem_hechos SET superseded_by = NULL WHERE user_id IN (%s, %s)", usuarios)
    cur.execute("DELETE FROM mem_hechos WHERE user_id IN (%s, %s)", usuarios)
    cur.execute("DELETE FROM mem_entidad_alias WHERE entidad_id IN"
                " (SELECT id FROM mem_entidades WHERE user_id IN (%s, %s))", usuarios)
    cur.execute("DELETE FROM mem_entidades WHERE user_id IN (%s, %s)", usuarios)
    cur.execute("DELETE FROM mem_atributo_alias WHERE atributo_id IN"
                " (SELECT id FROM mem_atributos WHERE nombre LIKE %s)", (f"%{SUFIJO}",))
    cur.execute("DELETE FROM mem_atributos WHERE nombre LIKE %s", (f"%{SUFIJO}",))
    conn.commit()


@pytest.fixture
def entorno():
    conn = get_connection()
    _limpiar(conn)
    repo = RepositorioMemoria(conn)
    cliente = qdrant_en_memoria()
    crear_colecciones(cliente, "svc_test")
    embedder = EmbedderFalso()
    catalogo = Catalogo(repo, embedder, cliente, "svc_test")
    catalogo.indexar_atributos()

    def servicio(hechos=None, error=None):
        extractor = ExtractorFalso(hechos, error)
        return ServicioMemoria(repo, catalogo, extractor, embedder, cliente, "svc_test", umbrales({}),
                               hoy=lambda: date(2026, 10, 16)), extractor

    yield SimpleNamespaceLike(repo=repo, cliente=cliente, catalogo=catalogo, servicio=servicio)
    _limpiar(conn)
    close_connection()


class SimpleNamespaceLike:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _tipos(repo):
    return [d["tipo"] for d in repo.decisiones(USER)]


# --- contrato de salida (§2.2) ---------------------------------------------------------------

def test_guardar_devuelve_contrato(entorno):
    servicio, _ = entorno.servicio([_hecho()])
    salida = servicio.guardar(USER, "Mi cuñado Paco es alérgico a los frutos secos")

    assert salida["success"] is True and isinstance(salida["result"], str)
    data = salida["data"]
    assert set(data) == {"guardados", "nuevos_pendientes", "notas", "sin_cambio"}
    assert set(data["nuevos_pendientes"]) == {"entidades", "atributos"}
    assert data["guardados"] == [{"entidad": "Paco", "atributo": "alergia", "valor": "frutos secos",
                                  "operacion": "afirmar", "sustituye": None}]
    assert data["nuevos_pendientes"]["entidades"] == ["Paco"]   # entidad nueva: queda pending
    assert data["nuevos_pendientes"]["atributos"] == []         # `alergia` ya existe
    paco = entorno.repo.entidades_por_alias(USER, "paco")[0]
    assert paco["estado"] == "pending" and paco["origen"] == "conversacion"


def test_yo_se_resuelve_a_la_entidad_del_usuario_sin_pending(entorno):
    servicio, _ = entorno.servicio([_hecho(entidad="yo", atributo="cumpleanos", cardinalidad="uno",
                                           valor="--03-12", tipo_valor="fecha")])
    salida = servicio.guardar(USER, "Mi cumpleaños es el 12 de marzo")
    assert salida["data"]["nuevos_pendientes"] == {"entidades": [], "atributos": []}
    yo = entorno.repo.entidad_usuario(USER)
    [h] = entorno.repo.hechos_vigentes(USER, yo, entorno.repo.atributos_por_alias("cumpleanos")[0]["id"])
    assert h["valor"] == "--03-12"


def test_atributo_nuevo_queda_pending_y_se_informa(entorno):
    servicio, _ = entorno.servicio([_hecho(
        entidad="saxhero", tipo_entidad="proyecto", atributo=f"publicacion{SUFIJO}", cardinalidad="uno",
        valor="no publicar en GitHub de momento", descripcion_atributo="Dónde y cómo se publica un proyecto")])
    salida = servicio.guardar(USER, "He decidido no publicar saxhero en GitHub de momento")

    assert salida["data"]["nuevos_pendientes"]["atributos"] == [f"publicacion{SUFIJO}"]
    [attr] = entorno.repo.atributos_por_alias(f"publicacion{SUFIJO}")
    assert attr["estado"] == "pending" and attr["fuente"] == "conversacion"
    assert attr["tipos_entidad"] == "proyecto" and attr["cardinalidad"] == "uno"
    # ya esta en el catalogo semantico: una frase parecida lo encuentra
    assert entorno.catalogo.buscar_atributos("Dónde y cómo se publica un proyecto")[0]["id"] == attr["id"]


def test_cada_decision_queda_en_log(entorno):
    servicio, _ = entorno.servicio([_hecho()])
    servicio.guardar(USER, "x")
    assert _tipos(entorno.repo) == ["crear_entidad", "reutilizar_atributo", "anadir"]

    servicio.guardar(USER, "x")   # el mismo hecho otra vez
    assert _tipos(entorno.repo)[3:] == ["reutilizar_entidad", "reutilizar_atributo", "sin_cambio"]
    anadir = entorno.repo.decisiones(USER)[2]
    assert anadir["hecho_id"] is not None and anadir["senales"]["regla"] == "varios_anade"


def test_decisiones_no_llevan_valor_ni_texto(entorno):
    servicio, _ = entorno.servicio([_hecho(valor="valor-secreto-123")])
    servicio.guardar(USER, "texto-secreto-456")
    volcado = json.dumps(entorno.repo.decisiones(USER), default=str)
    assert "valor-secreto-123" not in volcado and "texto-secreto-456" not in volcado


# --- correcciones y retiradas ------------------------------------------------------------------

def _dos_turnos(entorno, primero, segundo):
    servicio, extractor = entorno.servicio([primero])
    servicio.guardar(USER, "uno")
    extractor.hechos = [segundo]
    return servicio.guardar(USER, "dos")


def _domicilio(**kw):
    base = {"entidad": "yo", "atributo": f"domicilio{SUFIJO}", "cardinalidad": "uno", "valor": "Gijón",
            "descripcion_atributo": "Ciudad donde vive una persona"}
    return _hecho(**{**base, **kw})


def test_correccion_fuerte_sustituye_y_cuenta_lo_anterior(entorno):
    salida = _dos_turnos(entorno, _domicilio(), _domicilio(valor="Oviedo", operacion="corregir"))

    [g] = salida["data"]["guardados"]
    assert g["operacion"] == "corregir" and g["valor"] == "Oviedo"
    assert g["sustituye"]["valor"] == "Gijón" and g["sustituye"]["desde"] == date.today().isoformat()
    yo = entorno.repo.entidad_usuario(USER)
    attr = entorno.repo.atributos_por_alias(f"domicilio{SUFIJO}")[0]["id"]
    assert [h["valor"] for h in entorno.repo.hechos_vigentes(USER, yo, attr)] == ["Oviedo"]
    assert len(entorno.repo.hechos_historial(USER, yo, attr)) == 2   # el viejo sigue, cerrado


def test_resolucion_debil_guarda_nota_y_no_sustituye(entorno):
    entorno.repo.crear_entidad(USER, "coche", "vehiculo", estado="activo")
    coche = _hecho(entidad="coche", tipo_entidad="vehiculo", atributo=f"presion{SUFIJO}", cardinalidad="uno",
                   valor="2,2 bar", descripcion_atributo="Presión de las ruedas")
    # mismo alias de entidad pero el extractor la da por «persona»: tipo distinto -> resolucion debil
    corregido = {**coche, "tipo_entidad": "persona", "valor": "2,4 bar", "operacion": "corregir"}
    salida = _dos_turnos(entorno, coche, corregido)

    assert salida["data"]["guardados"] == [] and salida["data"]["notas"] == ["dos"]
    ent = entorno.repo.entidades_por_alias(USER, "coche")[0]["id"]
    attr = entorno.repo.atributos_por_alias(f"presion{SUFIJO}")[0]["id"]
    assert [h["valor"] for h in entorno.repo.hechos_vigentes(USER, ent, attr)] == ["2,2 bar"]   # intacto
    assert "nota" in _tipos(entorno.repo)
    # la nota se embebe en <base>_notas con {hecho_id, user_id} y SIN el texto
    puntos, _ = entorno.cliente.scroll("svc_test_notas", limit=10, with_payload=True)
    assert len(puntos) == 1
    assert set(puntos[0].payload) == {"hecho_id", "user_id"} and puntos[0].payload["user_id"] == USER


def test_retirar_fuerte_cierra_el_vigente(entorno):
    salida = _dos_turnos(entorno, _domicilio(), _domicilio(valor="", operacion="retirar"))
    [g] = salida["data"]["guardados"]
    assert g["operacion"] == "retirar" and g["valor"] == "Gijón"
    yo = entorno.repo.entidad_usuario(USER)
    attr = entorno.repo.atributos_por_alias(f"domicilio{SUFIJO}")[0]["id"]
    assert entorno.repo.hechos_vigentes(USER, yo, attr) == []
    assert len(entorno.repo.hechos_historial(USER, yo, attr)) == 1   # nada se borra


def test_retirar_algo_que_no_existe_no_crea_nada_y_avisa(entorno):
    servicio, _ = entorno.servicio([_hecho(entidad="camisetas UV", tipo_entidad="objeto",
                                           atributo=f"inventado{SUFIJO}", valor="", operacion="retirar")])
    salida = servicio.guardar(USER, "Olvida lo de las camisetas UV")

    assert salida["success"] is True and salida["data"]["guardados"] == []
    assert any("no he encontrado" in s.lower() for s in salida["data"]["sin_cambio"])
    assert entorno.repo.listar_entidades(USER) == [] or all(e["es_usuario"] for e in entorno.repo.listar_entidades(USER))
    assert entorno.repo.atributos_por_alias(f"inventado{SUFIJO}") == []   # no crea atributos para olvidar


# --- retirar una nota de texto libre (H2-revision §2.3, R3) -----------------------------------------
#
# Una «nota» es cualquier hecho con atributo `nota`, sea cual sea el camino por el que llego (el extractor
# la usa para lo que no encaja en otro atributo; la resolucion debil tambien). Todas se embeben en
# <base>_notas con {hecho_id, user_id}; si no, retirar por similitud no las encontraria.

def _nota(valor, entidad="yo", tipo="persona"):
    return _hecho(entidad=entidad, tipo_entidad=tipo, atributo="nota", cardinalidad="varios", valor=valor)


def _olvida(valor="camisetas UV"):
    # Caso 3 del extractor: «Olvida lo de las camisetas UV» -> entidad inexistente «camisetas UV», atributo `nota`.
    return _hecho(entidad="camisetas UV", tipo_entidad="objeto", atributo="nota", cardinalidad="varios",
                  valor=valor, operacion="retirar")


def _notas_vigentes(entorno, user=USER):
    yo = entorno.repo.entidad_usuario(user)
    nota = entorno.repo.atributos_por_alias("nota")[0]["id"]
    return [h["valor"] for h in entorno.repo.hechos_vigentes(user, yo, nota)]


def test_un_hecho_con_atributo_nota_se_embebe_en_notas(entorno):
    servicio, _ = entorno.servicio([_nota("Uso camisetas UV")])
    servicio.guardar(USER, "Uso camisetas UV")

    assert _notas_vigentes(entorno) == ["Uso camisetas UV"]
    puntos, _ = entorno.cliente.scroll("svc_test_notas", limit=10, with_payload=True)
    assert len(puntos) == 1 and set(puntos[0].payload) == {"hecho_id", "user_id"}
    assert puntos[0].payload["user_id"] == USER


def test_retirar_nota_por_similitud(entorno):
    entorno.servicio([_nota("Uso camisetas UV"), _nota("Me gusta el cine mudo")])[0].guardar(USER, "dos notas")
    servicio, _ = entorno.servicio([_olvida()])

    salida = servicio.guardar(USER, "Olvida lo de las camisetas UV")

    [g] = salida["data"]["guardados"]
    assert g["operacion"] == "retirar" and g["atributo"] == "nota" and g["valor"] == "Uso camisetas UV"
    assert salida["data"]["sin_cambio"] == []
    assert _notas_vigentes(entorno) == ["Me gusta el cine mudo"]          # solo se cierra la que encaja
    yo = entorno.repo.entidad_usuario(USER)
    nota = entorno.repo.atributos_por_alias("nota")[0]["id"]
    cerrada = [h for h in entorno.repo.hechos_historial(USER, yo, nota) if h["valid_to"] is not None]
    assert len(cerrada) == 1 and cerrada[0]["superseded_by"] is None       # retirar no sustituye
    retiros = [d for d in entorno.repo.decisiones(USER) if d["tipo"] == "retirar"]
    assert len(retiros) == 1 and retiros[0]["senales"]["regla"] == "retirar_nota"
    assert retiros[0]["hecho_id"] == cerrada[0]["id"]


def test_retirar_nota_debil_no_toca(entorno):
    entorno.servicio([_nota("Uso camisetas UV")])[0].guardar(USER, "una nota")
    servicio, _ = entorno.servicio([_olvida("bicicleta roja")])

    salida = servicio.guardar(USER, "Olvida lo de la bicicleta roja")

    assert salida["data"]["guardados"] == []
    assert any("no he encontrado" in s.lower() for s in salida["data"]["sin_cambio"])
    assert _notas_vigentes(entorno) == ["Uso camisetas UV"]
    assert "retirar" not in _tipos(entorno.repo)


def test_retirar_nota_ya_cerrada_no_cuenta(entorno):
    entorno.servicio([_nota("Uso camisetas UV")])[0].guardar(USER, "una nota")
    entorno.servicio([_olvida()])[0].guardar(USER, "Olvida lo de las camisetas UV")
    assert _notas_vigentes(entorno) == []

    salida = entorno.servicio([_olvida()])[0].guardar(USER, "Olvida lo de las camisetas UV")

    assert salida["data"]["guardados"] == []                               # su punto sigue en Qdrant, pero cerrada
    assert any("no he encontrado" in s.lower() for s in salida["data"]["sin_cambio"])


def test_retirar_nota_nunca_cierra_mas_de_una_por_turno(entorno):
    entorno.servicio([_nota("Uso camisetas UV"), _nota("Uso camisetas UV de manga larga")])[0].guardar(USER, "dos")
    servicio, _ = entorno.servicio([_olvida("camisetas UV"), _olvida("camisetas UV manga larga")])

    salida = servicio.guardar(USER, "Olvida lo de las camisetas UV y las de manga larga")

    assert len(salida["data"]["guardados"]) == 1
    assert len(salida["data"]["sin_cambio"]) == 1
    assert len(_notas_vigentes(entorno)) == 1


def test_retirar_nota_no_toca_las_de_otro_usuario(entorno):
    entorno.servicio([_nota("Uso camisetas UV")])[0].guardar(OTRO, "nota ajena")
    servicio, _ = entorno.servicio([_olvida()])

    salida = servicio.guardar(USER, "Olvida lo de las camisetas UV")

    assert salida["data"]["guardados"] == []
    assert _notas_vigentes(entorno, OTRO) == ["Uso camisetas UV"]


def test_retirar_con_entidad_y_atributo_fuertes_no_busca_en_notas(entorno):
    """R3 solo se dispara cuando la entidad o el atributo no se resuelven con fuerza: un `retirar` de
    («yo», alergia), ambos por alias exacto, que no encuentra ese valor sigue avisando y no toca las notas,
    aunque una nota coincidiera al 100 %."""
    entorno.servicio([_nota("alergia al polen")])[0].guardar(USER, "una nota")
    fuerte = _hecho(entidad="yo", atributo="alergia", valor="alergia al polen", operacion="retirar")
    salida = entorno.servicio([fuerte])[0].guardar(USER, "Ya no soy alérgico al polen")

    assert salida["data"]["guardados"] == []
    assert any("no he encontrado" in s.lower() for s in salida["data"]["sin_cambio"])
    assert _notas_vigentes(entorno) == ["alergia al polen"]


def test_parentesco_varios_no_sustituye(entorno):
    """H2-revision §2.1: una persona puede tener varias relaciones; la segunda no sustituye a la primera."""
    parentesco = lambda valor: _hecho(entidad="Paco", atributo="parentesco", cardinalidad="uno", valor=valor)
    _dos_turnos(entorno, parentesco("hermano de Ana"), parentesco("cuñado mío"))

    paco = entorno.repo.entidades_por_alias(USER, "paco")[0]["id"]
    attr = entorno.repo.atributos_por_alias("parentesco")[0]
    assert attr["cardinalidad"] == "varios"
    assert sorted(h["valor"] for h in entorno.repo.hechos_vigentes(USER, paco, attr["id"])) == [
        "cuñado mío", "hermano de Ana"]


# --- degradacion ------------------------------------------------------------------------------

def test_sin_hechos_no_escribe_y_lo_dice(entorno):
    servicio, _ = entorno.servicio([])
    salida = servicio.guardar(USER, "Qué tal estás")
    assert salida["success"] is True and salida["data"]["guardados"] == []
    assert entorno.repo.decisiones(USER) == []


def test_fallo_del_extractor_no_rompe_el_turno(entorno):
    servicio, _ = entorno.servicio(error=RuntimeError("api caida"))
    salida = servicio.guardar(USER, "algo")
    assert salida["success"] is False and salida["data"] == {}
    assert entorno.repo.decisiones(USER) == []


def test_fallo_del_embedder_degrada_pero_guarda(entorno):
    servicio, _ = entorno.servicio([_hecho()])
    servicio._catalogo._embedder = MagicMock(embed=MagicMock(side_effect=RuntimeError("openai caido")))
    salida = servicio.guardar(USER, "x")
    # sin semantica, la entidad (alias exacto o nueva) y el atributo (alias exacto) se resuelven igual
    assert salida["success"] is True and len(salida["data"]["guardados"]) == 1


# --- privacidad -------------------------------------------------------------------------------

def test_log_no_lleva_valores(entorno):
    servicio, _ = entorno.servicio([_hecho(valor="valor-secreto-123", entidad="entidad-secreta-789")])
    with patch("core.memoria.servicio.logger") as log_servicio, \
         patch("core.memoria.repositorio.logger") as log_repo, \
         patch("core.memoria.catalogo.logger", create=True) as log_catalogo:
        servicio.guardar(USER, "texto-secreto-456")
    llamadas = [str(c) for log in (log_servicio, log_repo, log_catalogo) for c in log.mock_calls]
    assert llamadas, "el servicio tiene que dejar alguna traza"
    for secreto in ("valor-secreto-123", "texto-secreto-456", "entidad-secreta-789"):
        assert not any(secreto in l for l in llamadas), secreto


# --- catalogo para el extractor ----------------------------------------------------------------

def test_texto_catalogo_lleva_semillas_y_entidades_propias_pero_no_ajenas(entorno):
    entorno.repo.crear_entidad(USER, "Paco", "persona")
    entorno.repo.crear_entidad(OTRO, "Marisol", "persona")
    servicio, _ = entorno.servicio([])
    texto = servicio.texto_catalogo(USER)
    assert "Paco" in texto and "Marisol" not in texto
    assert "alergia" in texto and "Sustancia o alimento" in texto   # atributo con su descripcion
    assert "alergias" in texto                                      # y sus alias
