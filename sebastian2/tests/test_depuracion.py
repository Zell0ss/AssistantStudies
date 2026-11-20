"""Fase 4, H1g (D72): modo depuración temporal, `/debug`. Traza con contenido, local, 0600, de 24 h, fuera de loguru y de LogCentral.
Clientes, bot y reloj falsos: sin red ni API. Datos inventados."""
import json
import os
import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from bot.handlers import setup_handlers
from core import depuracion
from core.memoria.extractor import Extractor
from tests.test_memoria_servicio import USER, entorno, _hecho  # noqa: F401  (`entorno` es una fixture)
from tests.test_orchestrator import db, _make_text_response, _make_tool_use_response  # noqa: F401  (`db` es una fixture)

HORA = datetime(2026, 11, 20, 15, 0, 0)
PROPIETARIO = "111"
OTRO_USUARIO = "222"
MARCA = "ZZDEBUG"


@pytest.fixture(autouse=True)
def aislado(tmp_path, monkeypatch):
    """Directorio de trazas propio, reloj que se mueve a mano y estado vacío; sin índice de memoria en el orquestador."""
    reloj = {"t": HORA}
    monkeypatch.setattr(depuracion, "_directorio", lambda: tmp_path / "debug")
    monkeypatch.setattr(depuracion, "_ahora", lambda: reloj["t"])
    depuracion._ACTIVAS.clear()
    with patch("core.orchestrator.indice_memoria", return_value=""):
        yield SimpleNamespace(reloj=reloj, carpeta=tmp_path / "debug", tmp=tmp_path)
    depuracion._ACTIVAS.clear()


# --- el comando -------------------------------------------------------------------------------------------------

class BotFalso:
    def __init__(self):
        self.manejadores, self.respuestas = [], []

    def message_handler(self, commands=None, func=None, content_types=None):
        def decorador(f):
            self.manejadores.append((commands, content_types, f))
            return f
        return decorador

    def reply_to(self, message, texto, **kw):
        self.respuestas.append(texto)

    def send_message(self, *a, **kw):
        self.respuestas.append(a[1] if len(a) > 1 else kw.get("text"))

    def send_document(self, *a, **kw):
        pass

    def comando(self, nombre):
        return next(f for comandos, _, f in self.manejadores if comandos and nombre in comandos)

    def texto(self):
        return next(f for comandos, tipos, f in self.manejadores if not comandos and tipos == ["text"])


def _bot():
    bot = BotFalso()
    setup_handlers(bot, {"memoria": {"propietario_vault": PROPIETARIO}, "authorized_ids": [int(PROPIETARIO), int(OTRO_USUARIO)]})
    return bot


def _mensaje(texto, chat=PROPIETARIO):
    return SimpleNamespace(chat=SimpleNamespace(id=int(chat), username="usuario_prueba"), text=texto)


def test_d72_1_otro_usuario_no_activa_nada_y_contesta_no_disponible(aislado):
    bot = _bot()
    with patch("core.depuracion.logger") as log_dep, patch("bot.handlers.logger") as log_bot:
        for texto in ("/debug", "/debug 30", "/debug off"):
            bot.comando("debug")(_mensaje(texto, chat=OTRO_USUARIO))
    assert bot.respuestas == ["Este comando no está disponible"] * 3
    assert depuracion._ACTIVAS == {} and not aislado.carpeta.exists()
    assert not log_dep.mock_calls and not log_bot.mock_calls            # ni el log dice por qué


def test_d72_2_debug_activa_off_apaga_y_los_valores_raros_dan_el_uso(aislado):
    bot = _bot()
    debug = bot.comando("debug")
    debug(_mensaje("/debug 30"))
    assert depuracion._ACTIVAS == {PROPIETARIO: HORA + timedelta(minutes=30)}
    assert bot.respuestas[-1] == f"Depuración activa hasta las 15:30. Traza en {aislado.carpeta}/debug-{PROPIETARIO}-20261120.jsonl"
    debug(_mensaje("/debug off"))
    assert depuracion._ACTIVAS == {} and bot.respuestas[-1] == "Depuración apagada"

    debug(_mensaje("/debug"))                                           # por defecto, 30
    assert depuracion._ACTIVAS[PROPIETARIO] == HORA + timedelta(minutes=30)
    debug(_mensaje("/debug 500"))                                       # como mucho, 120
    assert depuracion._ACTIVAS[PROPIETARIO] == HORA + timedelta(minutes=120)
    assert bot.respuestas[-1].startswith("Depuración activa hasta las 17:00")
    debug(_mensaje("/debug OFF"))
    assert depuracion._ACTIVAS == {}

    for malo in ("/debug abc", "/debug 0", "/debug -5", "/debug 2.5", "/debug 10 20"):
        antes = len(bot.respuestas)
        debug(_mensaje(malo))
        assert depuracion._ACTIVAS == {} and len(bot.respuestas) == antes + 1, malo
        assert bot.respuestas[-1].startswith("Uso: /debug [minutos]") and "/debug off" in bot.respuestas[-1], malo


def test_d72_2b_debug_sale_en_la_ayuda_y_a_logcentral_solo_va_el_aviso(aislado):
    bot = _bot()
    bot.comando("ayuda")(_mensaje("/ayuda"))
    assert "/debug" in bot.respuestas[-1]
    with patch("core.depuracion.logger") as log:
        bot.comando("debug")(_mensaje("/debug 45"))
        bot.comando("debug")(_mensaje("/debug off"))
    assert [c.args[0] for c in log.info.call_args_list] == [
        f"Depuración activada | user={PROPIETARIO} | minutos=45", f"Depuración desactivada (off) | user={PROPIETARIO}"]


# --- caducidad ----------------------------------------------------------------------------------------------------

def test_d72_3_al_caducar_activa_da_false_y_caducó_se_escribe_una_sola_vez(aislado):
    depuracion.activar(PROPIETARIO, 30)
    aislado.reloj["t"] = HORA + timedelta(minutes=29)
    assert depuracion.activa(PROPIETARIO) is True
    aislado.reloj["t"] = HORA + timedelta(minutes=31)
    with patch("core.depuracion.logger") as log:
        assert depuracion.activa(PROPIETARIO) is False
        assert depuracion.activa(PROPIETARIO) is False
        depuracion.traza(PROPIETARIO, "t1", "mensaje", {"texto": MARCA})
    assert [c.args[0] for c in log.info.call_args_list] == [f"Depuración desactivada (caducó) | user={PROPIETARIO}"]
    assert not any(aislado.carpeta.glob("debug-*"))                      # caducada: no se escribe nada


# --- un turno completo ----------------------------------------------------------------------------------------------

class AnthropicDelExtractor:
    """Cliente falso del extractor: devuelve `hechos` en el `bloque.input` de la tool forzada."""

    def __init__(self, hechos):
        self.messages = SimpleNamespace(create=lambda **kw: SimpleNamespace(
            content=[SimpleNamespace(type="tool_use", name="registrar_hechos", input={"hechos": hechos})],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1), stop_reason="tool_use"))


def _turno(entorno, db, user=USER, mensaje=f"Recuerda que mi color favorito es el verde {MARCA}"):
    """planner → mark_as_memorable → extractor → planner cierra → Alfred. Ejecutor y servicio reales, clientes falsos."""
    from core.orchestrator import Orchestrator
    cruda = _hecho(entidad="yo", tipo_entidad="persona", atributo="preferencia", valor=f"verde {MARCA}", cardinalidad="varios")
    servicio, _ = entorno.servicio([])
    servicio._extractor = Extractor(AnthropicDelExtractor([cruda]))
    with patch("core.orchestrator.Anthropic") as anthropic:
        cliente = anthropic.return_value
        cliente.messages.create.side_effect = [
            _make_tool_use_response("mark_as_memorable", "t1", {"texto": f"Mi color favorito es el verde {MARCA}"}),
            _make_text_response("ya está"), _make_text_response("Anotado, señor.")]
        orch = Orchestrator(db, user, config={"anthropic_apikey": "sk-falsa"})
        orch._executor._servicio_memoria = lambda: servicio
        resultado = orch.handle(mensaje)
    return resultado, orch, servicio


def _lineas(aislado, user=USER):
    fichero = aislado.carpeta / f"debug-{user}-20261120.jsonl"
    return [json.loads(l) for l in fichero.read_text(encoding="utf-8").splitlines()] if fichero.exists() else []


def test_d72_4_con_la_traza_activa_un_turno_completo_deja_todas_las_etapas_y_la_marca_solo_en_el_fichero(entorno, db, aislado, capfd):
    depuracion.activar(USER, 30)
    with patch("core.depuracion.logger") as log_dep, patch("core.orchestrator.logger") as log_orq, \
            patch("core.tool_executor.logger") as log_ex, patch("core.memoria.servicio.logger") as log_srv, \
            patch("core.memoria.extractor.logger") as log_ext, patch("core.memoria.repositorio.logger") as log_repo:
        resultado, _, _ = _turno(entorno, db)
    assert resultado["text"] == "Anotado, señor."

    lineas = _lineas(aislado)
    # el extractor corre dentro de la tool: su línea va antes que la del resultado de la tool
    assert [l["etapa"] for l in lineas] == ["mensaje", "planner", "extractor", "tool", "planner", "alfred"]
    por_etapa = {l["etapa"]: l for l in lineas}
    assert len({l["turno"] for l in lineas}) == 1 and lineas[0]["turno"]                       # un solo id de turno
    assert all(set(l) == {"ts", "turno", "etapa", "datos"} for l in lineas)
    assert por_etapa["mensaje"]["datos"] == {"texto": f"Recuerda que mi color favorito es el verde {MARCA}"}
    primero = next(l for l in lineas if l["etapa"] == "planner")["datos"]
    assert primero["stop_reason"] == "tool_use"
    assert primero["tools"] == [{"name": "mark_as_memorable", "input": {"texto": f"Mi color favorito es el verde {MARCA}"}}]
    extractor = por_etapa["extractor"]["datos"]
    assert extractor["texto"] == f"Mi color favorito es el verde {MARCA}" and extractor["catalogo_chars"] > 0
    assert extractor["bloque_input"]["hechos"][0]["valor"] == f"verde {MARCA}"                  # el `bloque.input` crudo
    assert "tool" in por_etapa and por_etapa["tool"]["datos"]["tool"] == "mark_as_memorable"
    alfred = por_etapa["alfred"]["datos"]
    assert MARCA in alfred["tool_results_summary"] and "mark_as_memorable" in alfred["tool_results_summary"]
    assert alfred["stop_reason"] == "end_turn" and alfred["texto"] == "Anotado, señor." and alfred["nota_planner"] == ""
    fichero = aislado.carpeta / f"debug-{USER}-20261120.jsonl"
    assert MARCA in fichero.read_text(encoding="utf-8")                                          # la marca SÍ está en el fichero

    # ...y en ningún otro sitio: ni en los loggers del código ni en loguru/stderr
    llamadas = [str(c) for log in (log_dep, log_orq, log_ex, log_srv, log_ext, log_repo) for c in log.mock_calls]
    assert llamadas and not any(MARCA in l for l in llamadas)
    fuera = capfd.readouterr()
    assert MARCA not in fuera.out and MARCA not in fuera.err


def test_d72_4b_la_consulta_de_memoria_traza_parametros_y_salida(entorno, db, aislado):
    from core.orchestrator import Orchestrator
    depuracion.activar(USER, 30)
    servicio, _ = entorno.servicio([])
    with patch("core.orchestrator.Anthropic") as anthropic:
        anthropic.return_value.messages.create.side_effect = [
            _make_tool_use_response("search_memory", "t1", {"query": f"color {MARCA}", "entidad": "yo", "atributo": "color"}),
            _make_text_response("ya"), _make_text_response("No me consta, señor.")]
        orch = Orchestrator(db, USER, config={"anthropic_apikey": "sk-falsa"})
        orch._executor._servicio_memoria = lambda: servicio
        orch.handle("¿Cuál es mi color favorito?")
    consulta = next(l for l in _lineas(aislado) if l["etapa"] == "memoria_consulta")["datos"]
    assert consulta["parametros"] == {"query": f"color {MARCA}", "entidad": "yo", "atributo": "color", "historial": False}
    assert set(consulta["salida"]) >= {"hechos", "historial", "notas", "vault", "conflictos"}


def test_d72_4c_el_resultado_de_una_tool_se_recorta_a_4000_con_marca(aislado, db):
    from core.orchestrator import Orchestrator
    depuracion.activar(USER, 30)
    with patch("core.orchestrator.Anthropic") as anthropic:
        anthropic.return_value.messages.create.side_effect = [
            _make_tool_use_response("inventory_list", "t1", {}), _make_text_response("ya"), _make_text_response("Hecho.")]
        orch = Orchestrator(db, USER, config={"anthropic_apikey": "sk-falsa"})
        orch._executor.execute = MagicMock(return_value={"x": "y" * 6000})
        orch.handle("¿qué hay?")
    tool = next(l for l in _lineas(aislado) if l["etapa"] == "tool")["datos"]
    assert tool["resultado"].startswith('{"x": "yyy') and "…[recortado: " in tool["resultado"]
    assert len(tool["resultado"]) < 4000 + 60
    assert depuracion.recortar("corto") == "corto" and depuracion.recortar("a" * 4000) == "a" * 4000
    assert depuracion.recortar("a" * 4001).endswith("…[recortado: 1 caracteres más]")


def test_d72_5_sin_la_traza_activa_no_se_crea_ningun_fichero_y_el_turno_sale_igual(entorno, db, aislado):
    resultado, orch, servicio = _turno(entorno, db)
    assert resultado["text"] == "Anotado, señor."
    assert not aislado.carpeta.exists() and orch._executor.turno_debug is None
    assert depuracion._ACTIVAS == {}


def test_d72_5b_sin_traza_la_memoria_se_llama_exactamente_como_antes(db, aislado):
    from core.tool_executor import ToolExecutor
    ejecutor = ToolExecutor(db, "99999", config={})
    servicio = MagicMock()
    ejecutor._servicio_memoria = lambda: servicio
    ejecutor.execute("mark_as_memorable", {"texto": "x"})
    servicio.guardar.assert_called_once_with("99999", "x", mensaje=None)               # sin `turno`
    ejecutor.turno_debug = "abc123"
    ejecutor.execute("search_memory", {"query": "q"})
    assert servicio.consultar.call_args.kwargs["turno"] == "abc123"


def test_d72_6_solo_el_usuario_activado_otro_usuario_no_escribe_nada(entorno, db, aislado):
    depuracion.activar(OTRO_USUARIO, 30)                    # activa para otro; el turno es de USER
    resultado, orch, _ = _turno(entorno, db)
    assert resultado["text"] == "Anotado, señor." and orch._executor.turno_debug is None
    assert not any(aislado.carpeta.glob("debug-*"))


# --- el fichero ------------------------------------------------------------------------------------------------------

def test_d72_7_el_directorio_es_0700_y_el_fichero_0600_aunque_el_umask_sea_0(aislado):
    antes = os.umask(0)                                     # sin umask que quite permisos: el modo lo pone el código
    try:
        depuracion.activar(PROPIETARIO, 30)
        depuracion.traza(PROPIETARIO, "t1", "mensaje", {"texto": MARCA})
    finally:
        os.umask(antes)
    assert (aislado.carpeta.stat().st_mode & 0o777) == 0o700
    (fichero,) = aislado.carpeta.glob("debug-*.jsonl")
    assert (fichero.stat().st_mode & 0o777) == 0o600
    assert json.loads(fichero.read_text(encoding="utf-8")) == {
        "ts": "2026-11-20T15:00:00.000", "turno": "t1", "etapa": "mensaje", "datos": {"texto": MARCA}}


def test_d72_7b_un_directorio_que_ya_existia_con_otro_modo_se_deja_en_0700(aislado):
    aislado.carpeta.mkdir(mode=0o755)
    os.chmod(aislado.carpeta, 0o755)
    depuracion.activar(PROPIETARIO, 30)
    assert (aislado.carpeta.stat().st_mode & 0o777) == 0o700


def _vieja(carpeta, nombre, horas):
    carpeta.mkdir(mode=0o700, exist_ok=True)
    fichero = carpeta / nombre
    fichero.write_text("{}\n")
    hace = time.time() - horas * 3600
    os.utime(fichero, (hace, hace))
    return fichero


def test_d72_8_la_limpieza_borra_lo_de_mas_de_24_h_y_deja_lo_reciente(aislado):
    vieja = _vieja(aislado.carpeta, "debug-111-20261119.jsonl", 25)
    reciente = _vieja(aislado.carpeta, "debug-111-20261120.jsonl", 1)
    ajeno = _vieja(aislado.carpeta, "otra-cosa.txt", 48)                  # no es una traza: no se toca
    with patch("core.depuracion.logger") as log:
        assert depuracion.limpiar() == 1
    assert not vieja.exists() and reciente.exists() and ajeno.exists()
    assert [c.args[0] for c in log.info.call_args_list] == ["Depuración: limpieza | borrados=1"]     # sin rutas
    assert depuracion.limpiar() == 0 and depuracion.limpiar.__name__ == "limpiar"


def test_d72_8b_la_limpieza_corre_al_activar_y_al_arrancar(aislado):
    vieja = _vieja(aislado.carpeta, "debug-111-20261110.jsonl", 30)
    depuracion.activar(PROPIETARIO, 30)
    assert not vieja.exists()
    otra = _vieja(aislado.carpeta, "debug-111-20261111.jsonl", 30)
    _bot()                                                                # `setup_handlers` limpia al arrancar
    assert not otra.exists()


def test_d72_8c_sin_directorio_la_limpieza_no_hace_nada_ni_lanza(aislado):
    assert depuracion.limpiar() == 0 and not aislado.carpeta.exists()


# --- fallos -----------------------------------------------------------------------------------------------------------

def test_d72_9_un_fallo_al_escribir_no_rompe_el_turno_y_deja_un_warning_sin_contenido(entorno, db, aislado):
    (aislado.tmp / "debug").write_text("soy un fichero, no un directorio")    # el directorio de trazas no se puede crear
    depuracion._ACTIVAS[USER] = HORA + timedelta(minutes=30)
    with patch("core.depuracion.logger") as log:
        resultado, _, _ = _turno(entorno, db)
    assert resultado["text"] == "Anotado, señor."                              # el turno sale igual
    avisos = [c.args[0] for c in log.warning.call_args_list]
    assert avisos and all(a.startswith("Depuración: no se pudo escribir la traza | user=") and "| error=" in a for a in avisos)
    assert not any(MARCA in a for a in avisos)


def test_d72_9b_si_activar_falla_el_comando_lo_dice_y_no_queda_activa(aislado):
    (aislado.tmp / "debug").write_text("soy un fichero")
    bot = _bot()
    bot.comando("debug")(_mensaje("/debug 30"))
    assert bot.respuestas[-1] == "No he podido activar la depuración" and depuracion._ACTIVAS == {}


# --- H1h, R21: handle_text no loguea el texto -------------------------------------------------------------------------

def _enviar_texto(bot, texto, respuesta):
    mensaje = _mensaje(texto)
    with patch("bot.handlers.try_resolve_pending", return_value=False), patch("bot.handlers.get_connection"), \
            patch("bot.handlers.UserSettingsModule") as ajustes, patch("bot.handlers.Orchestrator") as orquestador:
        ajustes.return_value.get_sprite_skin.return_value = "default"
        orquestador.return_value.handle.return_value = {"text": respuesta, "images": []}
        bot.texto()(mensaje)


def test_h1h_r21_el_texto_del_usuario_y_la_respuesta_no_salen_en_ningun_log(aislado, capfd):
    bot = _bot()
    with patch("bot.handlers.logger") as log:
        _enviar_texto(bot, f"Hola, mi clave es {MARCA}", f"Su clave es {MARCA}, señor")
    assert bot.respuestas == [f"Su clave es {MARCA}, señor"]                              # el usuario sí la recibe
    llamadas = [str(c) for c in log.mock_calls]
    assert llamadas and not any(MARCA in l for l in llamadas)
    assert [c.args[0] for c in log.info.call_args_list][:1] == [f"Processing text from usuario_prueba | chars={len(f'Hola, mi clave es {MARCA}')}"]
    assert [c.args[0] for c in log.debug.call_args_list] == [f"Orchestrator response | chars={len(f'Su clave es {MARCA}, señor')}"]
    # y con el logger de verdad, nada en stdout/stderr
    _enviar_texto(_bot(), f"Hola {MARCA}", f"Respuesta {MARCA}")
    fuera = capfd.readouterr()
    assert MARCA not in fuera.out and MARCA not in fuera.err


# --- H1h, R22: «24 h» quiere decir 24 h --------------------------------------------------------------------------------

def test_h1h_r22_el_planificador_limpia_las_trazas_cada_hora(aislado):
    from apscheduler.schedulers.background import BackgroundScheduler
    from bot.scheduler import _registrar_jobs
    s = BackgroundScheduler()
    _registrar_jobs(s, MagicMock(), {"authorized_ids": [111], "calendar": {"daily_reminder_time": "08:30"}})
    job = {j.id: j for j in s.get_jobs()}["limpiar_depuracion"]
    assert job.trigger.interval.total_seconds() == 3600 and job.max_instances == 1 and job.coalesce is True
    assert job.func is depuracion.limpiar
    vieja = _vieja(aislado.carpeta, "debug-111-20261110.jsonl", 30)
    reciente = _vieja(aislado.carpeta, "debug-111-20261120.jsonl", 1)
    job.func()                                                                  # lo que haría la tarea al dispararse
    assert not vieja.exists() and reciente.exists()


def test_h1h_r22_al_apagar_se_limpia(aislado):
    depuracion.activar(PROPIETARIO, 30)
    vieja = _vieja(aislado.carpeta, "debug-111-20261110.jsonl", 30)
    assert depuracion.apagar(PROPIETARIO) is True
    assert not vieja.exists()


def test_h1h_r22_al_caducar_se_limpia_una_sola_vez_con_reloj_falso(aislado):
    depuracion.activar(PROPIETARIO, 30)
    vieja = _vieja(aislado.carpeta, "debug-111-20261110.jsonl", 30)
    aislado.reloj["t"] = HORA + timedelta(minutes=29)
    assert depuracion.activa(PROPIETARIO) is True and vieja.exists()               # antes de caducar, no se limpia
    aislado.reloj["t"] = HORA + timedelta(minutes=31)
    with patch.object(depuracion, "limpiar", wraps=depuracion.limpiar) as limpiar:
        assert depuracion.activa(PROPIETARIO) is False
        assert depuracion.activa(PROPIETARIO) is False
    assert limpiar.call_count == 1 and not vieja.exists()                          # una vez, al caducar


def test_d72_la_traza_de_un_hecho_cuya_extraccion_falla_lo_dice_sin_romper(entorno, aislado):
    depuracion.activar(USER, 30)
    servicio, extractor = entorno.servicio([], error=RuntimeError(f"api caida {MARCA}"))
    with patch("core.memoria.servicio.logger") as log:
        salida = servicio.guardar(USER, f"texto {MARCA}", turno="t9")
    assert salida["success"] is False
    (linea,) = _lineas(aislado)
    assert linea["etapa"] == "extractor" and linea["datos"]["error"] == "RuntimeError" and MARCA in linea["datos"]["texto"]
    assert not any(MARCA in str(c) for c in log.mock_calls)
