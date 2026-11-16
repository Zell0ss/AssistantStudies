"""H4 (plan §3-H4, H3-revision cuarta §16): `deploy/comprobar_fase3.sh` es de SOLO LECTURA y la sección «Fase 3» de
`PASOS-CON-SUDO.md` está en el orden del plan. Sin API ni BD: pruebas estáticas (y que el script es bash válido)."""
import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "deploy" / "comprobar_fase3.sh"
PASOS = RAIZ / "deploy" / "PASOS-CON-SUDO.md"


def _sin_comentarios():
    return "\n".join(l for l in SCRIPT.read_text().splitlines() if not l.lstrip().startswith("#"))


def test_el_script_existe_y_es_bash_valido():
    assert SCRIPT.exists()
    assert subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True).returncode == 0


def test_es_de_solo_lectura_no_usa_sudo_ni_escribe():
    codigo = _sin_comentarios()
    assert "sudo " not in codigo
    for verbo in (r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bDROP\b", r"\bALTER\b", r"\bCREATE\b", r"\bTRUNCATE\b",
                  r"-X\s+(PUT|POST|DELETE|PATCH)", r"systemctl\s+(start|stop|restart|enable|disable)", r"\brm\s", r"\bmv\s"):
        assert not re.search(verbo, codigo, re.I), verbo
    assert "--data" not in codigo and "-d '" not in codigo                      # ningún curl con cuerpo


def test_no_manda_nada_por_telegram_ni_llama_a_una_api_de_pago():
    codigo = _sin_comentarios().lower()
    for prohibido in ("send_message", "telebot", "api.telegram", "anthropic", "openai", "enviar_avisos", "registrar_aviso"):
        assert prohibido not in codigo, prohibido


def test_no_imprime_el_texto_de_los_compromisos_salvo_con_mostrar():
    """D52: las cuentas sí, el texto no. La consulta de la tabla no selecciona `texto`."""
    codigo = _sin_comentarios()
    assert "SELECT texto" not in codigo and "c.texto" not in codigo
    assert 'MOSTRAR' in codigo and '== "1"' in codigo


def test_comprueba_la_migracion_el_arranque_la_prueba_seca_y_los_errores():
    codigo = SCRIPT.read_text()
    for pieza in ("compromisos", "aviso_para", "013_compromisos.sql", "SEBASTIAN_DB_NAME=sebastian_db", "Escribiendo en BD",
                  "Planificador arrancado", "avisos cada minuto", "armar_resumen", "logcentral query"):
        assert pieza in codigo, pieza


def test_los_pasos_con_sudo_tienen_la_seccion_de_la_fase_3_en_el_orden_del_plan():
    t = PASOS.read_text()
    assert "## Fase 3" in t
    fase3 = t[t.index("## Fase 3"):]
    orden = ["comprobar_fase2.sh", "mysqldump", "013_compromisos.sql", "--ff-only", "systemctl restart", "comprobar_fase3.sh",
             "Prueba real por Telegram", "git reset --hard"]
    posiciones = [fase3.index(p) for p in orden]
    assert posiciones == sorted(posiciones), dict(zip(orden, posiciones))
    assert "DROP TABLE compromisos" in fase3 and "sin preguntar" in fase3         # H3-revision §16: la vuelta atrás no la ejecuta
    assert "antes del 10/12" in fase3 and "01:00" in fase3                        # plazo e indicador de D48
