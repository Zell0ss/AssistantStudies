"""H4 (plan H3.4, H3-revision §5.4): `deploy/comprobar_fase2.sh` es de SOLO LECTURA y comprueba lo que la fase deja desplegado.
Sin API ni BD: pruebas estáticas del script (y que es bash válido)."""
import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / "deploy" / "comprobar_fase2.sh"
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


def test_comprueba_las_tablas_de_la_memoria_incluida_mem_fuentes_y_la_columna_fuente_id():
    codigo = SCRIPT.read_text()
    for tabla in ("mem_entidades", "mem_entidad_alias", "mem_atributos", "mem_atributo_alias", "mem_hechos",
                  "mem_decisiones", "mem_fuentes"):
        assert tabla in codigo, tabla
    assert "fuente_id" in codigo                                                # H3-revision §5.4


def test_comprueba_lo_migrado_las_colecciones_y_que_la_antigua_sigue():
    codigo = SCRIPT.read_text()
    assert "migracion" in codigo and "presion_neumaticos" in codigo
    for coleccion in ("sebastian_memory_catalogo", "sebastian_memory_notas"):
        assert coleccion in codigo, coleccion
    assert "sebastian_memory" in codigo and "no se borra" in codigo.lower()     # la colección de Sprint 3 es archivo (D18)


def test_comprueba_las_unidades_el_log_de_arranque_y_que_no_hay_errores():
    codigo = SCRIPT.read_text()
    for pieza in ("SEBASTIAN_DB_NAME=sebastian_db", "SEBASTIAN_MEMORY_COLLECTION=sebastian_memory", "Escribiendo en BD",
                  "logcentral query"):
        assert pieza in codigo, pieza
    assert "modules/memory.py" in codigo                                         # el código viejo ya no está desplegado


def test_los_pasos_con_sudo_tienen_la_seccion_de_la_fase_2_en_el_orden_del_plan():
    t = PASOS.read_text()
    assert "## Fase 2" in t
    fase2 = t[t.index("## Fase 2"):]
    orden = ["mysqldump", "010_memoria.sql", "011_memoria_semillas.sql", "012_memoria_fuentes.sql", "crear_colecciones",
             "--ff-only", "migrar_sprint3", "indexar_catalogo", "systemctl restart", "comprobar_fase2.sh", "Telegram"]
    posiciones = [fase2.index(p) for p in orden]
    assert posiciones == sorted(posiciones), dict(zip(orden, posiciones))        # el orden de PLAN §3 H4.4
    assert "--dry-run" in fase2 and "--produccion" in fase2
    assert "SEBASTIAN_DB_NAME=sebastian_db" in fase2 and "SEBASTIAN_MEMORY_COLLECTION=sebastian_memory" in fase2
    assert "git reset --hard" in fase2 and "no se borra" in fase2.lower()        # vuelta atrás; la colección vieja se queda
    assert "¿Qué sabes de mí?" in fase2 and "2,4 bares" in fase2                 # la prueba de Josem (plan H4.5)
