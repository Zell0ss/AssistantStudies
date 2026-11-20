"""Fase 4, H1-revision R3: `deploy/comprobar_fase4.sh` es de SOLO LECTURA y la sección «Fase 4» de `PASOS-CON-SUDO.md` está en el
orden del plan, con los pasos de `sudo` en una sola línea. Sin API ni BD: pruebas estáticas (y que el script es bash válido)."""
import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "deploy" / "comprobar_fase4.sh"
PASOS = RAIZ / "deploy" / "PASOS-CON-SUDO.md"


def _sin_comentarios():
    return "\n".join(l for l in SCRIPT.read_text().splitlines() if not l.lstrip().startswith("#"))


def _fase4():
    t = PASOS.read_text()
    return t[t.index("## Fase 4"):]


def test_el_script_existe_y_es_bash_valido():
    assert SCRIPT.exists()
    assert subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True).returncode == 0


def test_es_de_solo_lectura_no_usa_sudo_ni_escribe():
    codigo = _sin_comentarios()
    assert "sudo " not in codigo
    for verbo in (r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bDROP\b", r"\bALTER\b", r"\bCREATE\b", r"\bTRUNCATE\b",
                  r"-X\s+(PUT|POST|DELETE|PATCH)", r"systemctl\s+(start|stop|restart|enable|disable)", r"\brm\s", r"\bmv\s"):
        assert not re.search(verbo, codigo, re.I), verbo
    assert "--data" not in codigo and "-d '" not in codigo


def test_no_manda_nada_por_telegram_ni_llama_a_ninguna_api():
    codigo = _sin_comentarios().lower()
    for prohibido in ("send_message", "telebot", "api.telegram", "anthropic", "openai", "wallapop", "pasada_vigilancias", "requests"):
        assert prohibido not in codigo, prohibido


def test_no_imprime_consultas_reglas_ni_titulos_d42():
    sqls = re.findall(r'cur\.execute\("([^"]*)"', _sin_comentarios())
    assert sqls
    for sql in sqls:
        for columna in ("reglas", "nombre", "titulo", "descripcion", "filtros"):
            assert not re.search(rf"\b{columna}\b", sql, re.I), (columna, sql)
        assert not re.search(r"(?<!JSON_LENGTH\()\bconsultas\b", sql), sql         # de las consultas solo cuántas hay
    assert any("JSON_LENGTH(consultas)" in sql for sql in sqls)


def test_comprueba_las_tablas_la_vigilancia_el_planificador_y_los_errores():
    codigo = SCRIPT.read_text()
    for pieza in ("vigilancias", "vigilancia_vistos", "014_vigilancias.sql", "SEBASTIAN_DB_NAME=sebastian_db", "Escribiendo en BD",
                  "Planificador arrancado", "vigilancias cada 15 min", "activa", "hora=", "Vigilancia id=", "logcentral query",
                  "Todo bien."):
        assert pieza in codigo, pieza


def test_la_linea_de_arranque_del_planificador_dice_lo_que_el_script_busca():
    fuente = (RAIZ / "bot" / "scheduler.py").read_text()
    assert "avisos cada minuto, vigilancias cada 15 min" in fuente              # `comprobar_fase3.sh` sigue encontrando «avisos cada minuto»


def test_los_pasos_con_sudo_tienen_la_seccion_de_la_fase_4_en_el_orden_del_plan():
    fase4 = _fase4()
    orden = ["comprobar_fase3.sh", "rev-parse HEAD", "mysqldump", "014_vigilancias.sql", "--ff-only", "scripts.vigilancias.cargar",
             "systemctl restart", "comprobar_fase4.sh", "La primera ronda", "git reset --hard"]
    posiciones = [fase4.index(p) for p in orden]
    assert posiciones == sorted(posiciones), dict(zip(orden, posiciones))
    assert "SEBASTIAN_DB_NAME=sebastian_db" in fase4 and "Escribiendo en BD: sebastian_db" in fase4
    assert "DROP TABLE vigilancias" in fase4 and "sin preguntar" in fase4


def test_los_pasos_con_sudo_van_en_una_sola_linea_con_and_y_sin_comentarios():
    """Al pegar varias líneas, `sudo` se come la siguiente como contraseña (le pasó a Josem en la fase 3)."""
    fase4 = _fase4()
    bloques = re.findall(r"```bash\n(.*?)```", fase4, re.S)
    assert bloques
    for bloque in bloques:
        lineas = [l for l in bloque.splitlines() if l.strip()]
        if any("sudo" in l for l in lineas):
            assert len(lineas) == 1, f"un bloque con sudo tiene que ser una sola línea: {bloque!r}"
            assert "#" not in lineas[0], f"sin comentarios dentro de la línea: {lineas[0]!r}"
            if lineas[0].count("sudo") > 1:
                assert "&&" in lineas[0]
    con_sudo = [b for b in bloques if "sudo" in b]
    assert len(con_sudo) >= 4                                                    # copia+migración, reinicio, vuelta atrás (parar y arrancar) y pausar
    assert any("mysqldump" in b and "014_vigilancias.sql" in b and b.count("&&") >= 3 for b in con_sudo)


def test_lo_que_hay_que_apuntar_va_en_un_bloque_aparte_antes_de_los_pasos_con_sudo():
    fase4 = _fase4()
    paso0 = fase4[fase4.index("### Paso 0"):fase4.index("### Paso 1")]
    bloques = re.findall(r"```bash\n(.*?)```", paso0, re.S)
    assert bloques and all("sudo" not in b for b in bloques)
    assert "rev-parse HEAD" in paso0 and "id de Telegram" in paso0
