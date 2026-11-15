"""Fase 2 H3 (plan §3 H3.4): escenarios con estado de la memoria nueva, de punta a punta. [API]

Usan el `Orchestrator` real (planner Haiku, extractor Haiku 4.5, síntesis de Alfred) contra `sebastian_test`
y las colecciones de test, y comprueban **la BD**, no solo la tool. Cada escenario empieza con la memoria del
usuario de goldens vacía (fixture `escenario_runner`). E8 usa su propio vault en un directorio temporal: el
vault real no se toca en ningún escenario.

Los criterios sobre el texto de Alfred son redes, no pruebas de corrección: el informe pega las respuestas
(`RESULTADOS` se imprime al final de la pasada, ver `_imprimir_escenarios` en conftest.py).

Se lanza con:  pytest -m golden tests/golden/test_escenarios_memoria.py -s
"""
import pytest

from core.memoria.normalizar import normalizar
from core.memoria.repositorio import RepositorioMemoria
from tests.golden.conftest import GOLDEN_USER_ID
from tests.golden.memoria_base import USUARIO_B, decisiones, fuentes, hechos

RESULTADOS = []   # {id, titulo, turnos: [(frase, tools, texto)], bd: [líneas]}; los imprime el conftest

PACO = "Mi cuñado Paco es alérgico a los frutos secos"
PREGUNTA_PACO = "¿Qué alergias tiene Paco?"
PRESION_1 = "La presión de las ruedas del coche es 2,30 bares"
PRESION_2 = "Me equivoqué: es 2,4 bares"


def _correr(runner, frases, **kw):
    """Los turnos de un escenario, en orden. Devuelve [(frase, tools, texto)]."""
    turnos = []
    for frase in frases:
        tools, respuesta = runner(frase, **kw)
        turnos.append((frase, tools, respuesta.get("text", "") if isinstance(respuesta, dict) else str(respuesta)))
    return turnos


def _registrar(ident, titulo, turnos, db=()):
    RESULTADOS.append({"id": ident, "titulo": titulo, "turnos": turnos, "bd": list(db)})


def _bd(filas):
    return [f"mem_hechos #{f['id']} · {f['entidad']} · {f['atributo']} · {f['valor']!r} · "
            f"{'vigente' if f['valid_to'] is None else 'cerrado'}"
            f"{' · sustituido por #%s' % f['superseded_by'] if f['superseded_by'] else ''}"
            f" · fuente #{f['fuente_id']}" for f in filas]


def _bd_fuentes(filas):
    return [f"mem_fuentes #{f['id']} · texto={f['texto']!r} · mensaje={f['mensaje']!r} · "
            f"{'purgada' if f['purgada_at'] else 'con texto'}" for f in filas]


def _tipos_de_decision(db, user=GOLDEN_USER_ID):
    return [d["tipo"] for d in decisiones(db, user)]


# --- E1 · E2 · E3 · E4 · E5: la vida de un hecho -------------------------------------------------------

@pytest.mark.golden
def test_E1_guardar_y_consultar(escenario_runner, test_db):
    turnos = _correr(escenario_runner, [PACO, PREGUNTA_PACO])
    vigentes = hechos(test_db, GOLDEN_USER_ID, entidad="Paco", atributo="alergia", vigentes=True)
    _registrar("E1", "Guardar y consultar: Paco y los frutos secos", turnos, _bd(hechos(test_db, GOLDEN_USER_ID)))

    assert len(vigentes) == 1, f"se esperaba 1 hecho vigente (Paco, alergia): {_bd(vigentes)}"
    assert "frutos secos" in vigentes[0]["valor"].lower()
    assert "frutos secos" in turnos[1][2].lower(), "la respuesta no menciona «frutos secos»"


def _presion(runner, frases):
    return _correr(runner, frases)


def _hechos_del_coche(db):
    filas = hechos(db, GOLDEN_USER_ID, entidad="coche")
    return [f for f in filas if f["valid_to"] is None], [f for f in filas if f["valid_to"] is not None]


@pytest.mark.golden
def test_E2_correccion_sustituye(escenario_runner, test_db):
    turnos = _presion(escenario_runner, [PRESION_1, PRESION_2])
    vigentes, cerrados = _hechos_del_coche(test_db)
    _registrar("E2", "Corrección: 2,30 → 2,4 bares", turnos, _bd(vigentes + cerrados))

    assert len(vigentes) == 1 and len(cerrados) == 1, f"vigentes={_bd(vigentes)} cerrados={_bd(cerrados)}"
    assert "2,4" in vigentes[0]["valor"]
    assert cerrados[0]["superseded_by"] == vigentes[0]["id"], "el primero debe quedar sustituido por el segundo"
    assert "sustituir" in _tipos_de_decision(test_db)


@pytest.mark.golden
def test_E3_pregunta_por_lo_anterior(escenario_runner, test_db):
    turnos = _presion(escenario_runner, [PRESION_1, PRESION_2, "¿Qué presión te dije antes?"])
    vigentes, cerrados = _hechos_del_coche(test_db)
    _registrar("E3", "Lo que valía antes: historial", turnos, _bd(vigentes + cerrados))

    texto = turnos[2][2]
    assert "2,3" in texto, f"la respuesta no menciona 2,3 (o 2,30): {texto!r}"


@pytest.mark.golden
def test_E4_varios_valores(escenario_runner, test_db):
    turnos = _correr(escenario_runner, [PACO, PREGUNTA_PACO, "Paco también es alérgico al marisco"])
    vigentes = hechos(test_db, GOLDEN_USER_ID, entidad="Paco", atributo="alergia", vigentes=True)
    _registrar("E4", "Dos alergias vigentes a la vez", turnos, _bd(hechos(test_db, GOLDEN_USER_ID)))

    assert sorted(v["valor"].lower() for v in vigentes) == ["frutos secos", "marisco"], _bd(vigentes)


@pytest.mark.golden
def test_E5_olvidar_uno_de_varios(escenario_runner, test_db):
    turnos = _correr(escenario_runner, [PACO, PREGUNTA_PACO, "Paco también es alérgico al marisco",
                                        "Olvida lo del marisco de Paco"])
    filas = hechos(test_db, GOLDEN_USER_ID, entidad="Paco", atributo="alergia")
    todas = fuentes(test_db, GOLDEN_USER_ID)
    _registrar("E5", "Olvidar el marisco, no los frutos secos (D42: se borra el texto)", turnos,
               _bd(hechos(test_db, GOLDEN_USER_ID)) + _bd_fuentes(todas))

    # D42: lo retirado queda cerrado, sin sustituto y con el valor en '' (ya no se puede buscar por «marisco»).
    cerrados = [f for f in filas if f["valid_to"] is not None]
    secos = [f for f in filas if f["valid_to"] is None]
    assert len(cerrados) == 1 and cerrados[0]["superseded_by"] is None and cerrados[0]["valor"] == "", _bd(filas)
    assert len(secos) == 1 and "frutos secos" in secos[0]["valor"].lower(), "los frutos secos tienen que seguir vigentes"
    # y la fuente de «frutos secos» conserva su texto (le queda un hecho vigente); la del marisco, solo si no le queda ninguno.
    fuente_secos = next(f for f in todas if f["id"] == secos[0]["fuente_id"])
    assert fuente_secos["texto"] and fuente_secos["purgada_at"] is None, _bd_fuentes(todas)
    fuente_marisco = next(f for f in todas if f["id"] == cerrados[0]["fuente_id"])
    quedan_vigentes = [h for h in hechos(test_db, GOLDEN_USER_ID, vigentes=True) if h["fuente_id"] == fuente_marisco["id"]]
    assert (fuente_marisco["texto"] is None) == (not quedan_vigentes), _bd_fuentes(todas)


# --- E6: atributo nuevo y D16 --------------------------------------------------------------------------

@pytest.mark.golden
def test_E6_atributo_nuevo_pending_y_se_informa(escenario_runner, test_db):
    turnos = _correr(escenario_runner, ["He decidido no publicar saxhero en GitHub"])
    creadas = [d for d in decisiones(test_db, GOLDEN_USER_ID) if d["tipo"] == "crear_atributo"]
    atributo = None
    if creadas:
        atributo = RepositorioMemoria(test_db).atributo(int(creadas[0]["detalle"].split("atributo=")[1].split()[0]))
    _registrar("E6", "Decisión sobre un proyecto: atributo nuevo, pending, y Alfred lo dice (D16)", turnos,
               _bd(hechos(test_db, GOLDEN_USER_ID)) + [f"decisiones: {_tipos_de_decision(test_db)}",
                                                       f"atributo creado: {atributo['nombre'] if atributo else None}"
                                                       f" ({atributo['estado'] if atributo else '-'})"])

    assert atributo is not None, f"no hubo `crear_atributo`: {_tipos_de_decision(test_db)}"
    assert atributo["estado"] == "pending"
    # Sin tildes ni signos, como los alias: el atributo es `publicacion` y Alfred escribe «*publicación*».
    texto = normalizar(turnos[0][2])
    nombre = normalizar(atributo["nombre"].replace("_", " "))
    assert nombre in texto or "nuevo" in texto or "nueva" in texto, f"Alfred no menciona lo nuevo (D16): {texto!r}"


# --- E7: aislamiento entre usuarios (D33) --------------------------------------------------------------

@pytest.mark.golden
def test_E7_otro_usuario_no_ve_lo_mio(escenario_runner, test_db):
    turnos = _correr(escenario_runner, ["Mi coche es rojo"])
    turnos_b = _correr(escenario_runner, ["¿De qué color es mi coche?"], user_id=USUARIO_B)
    _registrar("E7", "El usuario B no recibe lo del usuario A", turnos + turnos_b,
               [f"A: {_bd(hechos(test_db, GOLDEN_USER_ID))}", f"B: {_bd(hechos(test_db, USUARIO_B))}"])

    assert hechos(test_db, GOLDEN_USER_ID, vigentes=True), "el usuario A debería tener su hecho"
    assert hechos(test_db, USUARIO_B) == []
    assert "rojo" not in turnos_b[0][2].lower(), f"B recibió el dato de A: {turnos_b[0][2]!r}"


# --- E8: el vault gana y avisa (D37) -------------------------------------------------------------------

@pytest.mark.golden
def test_E8_el_vault_gana_y_avisa(escenario_runner, test_db, config_de_goldens, tmp_path):
    carpeta = tmp_path / "30-projects" / "proyecto-prueba"
    carpeta.mkdir(parents=True)
    (carpeta / "proyecto.md").write_text(
        "---\ncontrato: 2\nnombre: proyecto-prueba\nhost: seb01\nruta: /tmp/proyecto-prueba\nestado: stable\n---\n",
        encoding="utf-8")
    config = {**config_de_goldens, "vault_docs_path": str(tmp_path / "30-projects"),
              "memoria": {**(config_de_goldens.get("memoria") or {}), "propietario_vault": GOLDEN_USER_ID}}

    turnos = _correr(escenario_runner, ["proyecto-prueba está pausado", "¿En qué estado está proyecto-prueba?"],
                     config=config)
    _registrar("E8", "El vault de prueba dice stable; la conversación, pausado", turnos,
               _bd(hechos(test_db, GOLDEN_USER_ID)))

    texto = turnos[1][2].lower()
    assert "stable" in texto, f"no da el valor del vault: {texto!r}"
    assert any(p in texto for p in ("pausado", "coincid", "vault", "distint", "difier", "contrad")), (
        f"no avisa de que lo dicho no coincide con el vault: {texto!r}")


# --- E9 (H2-revision §2.3, R3): retirar una nota -------------------------------------------------------

@pytest.mark.golden
def test_E9_retirar_una_nota_por_similitud(escenario_runner, test_db):
    turnos = _correr(escenario_runner, ["Uso camisetas UV para bañarme", "Olvida lo de las camisetas UV"])
    todos = hechos(test_db, GOLDEN_USER_ID)
    reglas = [d["senales"].get("regla") for d in decisiones(test_db, GOLDEN_USER_ID) if d["tipo"] == "retirar"]
    _registrar("E9", "Retirar «camisetas UV»: la nota queda cerrada", turnos,
               _bd(todos) + _bd_fuentes(fuentes(test_db, GOLDEN_USER_ID)) + [f"reglas de retirar: {reglas}"])

    # D42: lo retirado conserva la fila pero no su valor, así que no se busca por «camiseta» sino por lo que queda vigente.
    assert todos, "no se guardó nada sobre las camisetas"
    vigentes = [h for h in todos if h["valid_to"] is None and "camiseta" in h["valor"].lower()]
    assert not vigentes, f"queda algo vigente: {_bd(vigentes)}"
    assert reglas, "no se retiró nada: ningún `retirar` en mem_decisiones"
