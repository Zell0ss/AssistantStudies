"""Fase 4, H1 (plan §2.1, §2.7 y §3, prueba 26): la migración 014, la validación de vigilancias y el script de carga.
Contra `sebastian_test`; el YAML es inventado y vive en `tmp_path` (el de Josem no va al repo)."""
import re
from pathlib import Path

import pytest
import yaml

from db.connection import close_connection, get_connection
from modules.vigilancias import repositorio
from modules.vigilancias.repositorio import VigilanciaInvalida, guardar, validar
from scripts.vigilancias import cargar as script

RAIZ = Path(__file__).resolve().parent.parent
MIGRACION = RAIZ / "db" / "migrations" / "014_vigilancias.sql"
USUARIO = "987650111"

VALIDA = {"nombre": "Mac mini", "fuente": "wallapop", "consultas": ["mac mini m4", "mac mini m2 pro"],
          "filtros": {"precio_min": 300, "precio_max": 1800, "excluir": ["8gb", "intel"]},
          "reglas": "Apple Silicon con 24 GB o más. Descarta revendedores.", "hora": "07:30"}


@pytest.fixture
def conn():
    c = get_connection()
    _limpiar(c)
    yield c
    _limpiar(c)
    close_connection()


def _limpiar(c):
    cur = c.cursor()
    cur.execute("DELETE FROM vigilancias WHERE user_id = %s", (USUARIO,))
    c.commit()
    cur.close()


def _filas(c, sql, params=()):
    cur = c.cursor()
    cur.execute(sql, params)
    filas = list(cur.fetchall())
    cur.close()
    return filas


def _yaml(tmp_path, contenido, nombre="vigilancia.yaml"):
    ruta = tmp_path / nombre
    ruta.write_text(yaml.safe_dump(contenido, allow_unicode=True), encoding="utf-8")
    return ruta


# ── Migración ────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_la_migracion_existe_no_lleva_use_y_es_idempotente(conn):
    assert MIGRACION.exists() and not re.search(r"(?im)^\s*USE\s+", MIGRACION.read_text())            # D20
    sql = re.sub(r"--[^\n]*", "", MIGRACION.read_text())
    cur = conn.cursor()
    for sentencia in [s.strip() for s in sql.split(";") if s.strip()]:
        cur.execute(sentencia)                                                                          # aplicarla otra vez no falla
    cur.close()


def test_las_tablas_tienen_las_columnas_y_claves_del_contrato(conn):
    cols = {c["COLUMN_NAME"]: c for c in _filas(conn, "SELECT COLUMN_NAME, IS_NULLABLE, DATA_TYPE FROM information_schema.COLUMNS"
                                                       " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vigilancias'")}
    assert set(cols) == {"id", "user_id", "nombre", "fuente", "consultas", "filtros", "reglas", "hora", "activa", "ultima_ronda",
                         "aviso_fallo", "created_at", "updated_at"}
    assert cols["ultima_ronda"]["IS_NULLABLE"] == "YES" and cols["aviso_fallo"]["IS_NULLABLE"] == "YES"
    assert cols["ultima_ronda"]["DATA_TYPE"] == "date" and cols["hora"]["DATA_TYPE"] == "time"
    assert cols["fuente"]["DATA_TYPE"] == "varchar"                                                      # texto, no ENUM: añadir fuentes no migra
    vistos = {c["COLUMN_NAME"]: c for c in _filas(conn, "SELECT COLUMN_NAME, IS_NULLABLE FROM information_schema.COLUMNS"
                                                         " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'vigilancia_vistos'")}
    assert set(vistos) == {"vigilancia_id", "anuncio_id", "precio", "firma", "modificado", "visto_en"}
    assert vistos["precio"]["IS_NULLABLE"] == "YES" and vistos["firma"]["IS_NULLABLE"] == "NO"
    indices = {i["INDEX_NAME"] for i in _filas(conn, "SELECT INDEX_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE()"
                                                     " AND TABLE_NAME IN ('vigilancias', 'vigilancia_vistos')")}
    assert {"uq_user_nombre", "idx_activa", "idx_visto", "PRIMARY"} <= indices


def test_el_nombre_es_unico_por_usuario_y_borrar_la_vigilancia_borra_sus_vistos(conn):
    v = guardar(conn, USUARIO, VALIDA)
    cur = conn.cursor()
    with pytest.raises(Exception):
        cur.execute("INSERT INTO vigilancias (user_id, nombre, fuente, consultas, filtros, reglas, hora, created_at, updated_at)"
                    " VALUES (%s,'Mac mini','wallapop','[]','{}','r','07:30',NOW(),NOW())", (USUARIO,))
    conn.rollback()
    cur.execute("INSERT INTO vigilancia_vistos VALUES (%s, 'x', 10, %s, NOW(), NOW())", (v["id"], "0" * 40))
    conn.commit()
    cur.execute("DELETE FROM vigilancias WHERE id = %s", (v["id"],))
    conn.commit()
    cur.execute("SELECT COUNT(*) AS n FROM vigilancia_vistos WHERE vigilancia_id = %s", (v["id"],))
    assert cur.fetchone()["n"] == 0
    cur.close()


# ── Validación ───────────────────────────────────────────────────────────────────────────────────────────────────────

def test_validar_normaliza_y_acepta_la_vigilancia_valida():
    v = validar({**VALIDA, "filtros": {"excluir": [" 8gb ", ""]}})
    assert v["hora"].strftime("%H:%M") == "07:30" and v["activa"] is True
    assert v["filtros"] == {"precio_min": None, "precio_max": None, "excluir": ["8gb"]}


@pytest.mark.parametrize("cambio, campo", [
    ({"nombre": ""}, "nombre"), ({"nombre": "n" * 101}, "nombre"),
    ({"fuente": "amazon"}, "fuente"),
    ({"consultas": []}, "consultas"), ({"consultas": ["abc"] * 11}, "consultas"), ({"consultas": ["x"]}, "consultas"),
    ({"consultas": ["y" * 81]}, "consultas"), ({"consultas": [5]}, "consultas"),
    ({"reglas": ""}, "reglas"), ({"reglas": "r" * 4001}, "reglas"),
    ({"hora": "25:99"}, "hora"), ({"hora": None}, "hora"),
    ({"filtros": {"precio_min": -1}}, "precio_min"), ({"filtros": {"precio_max": "mucho"}}, "precio_max"),
    ({"filtros": {"precio_min": 500, "precio_max": 100}}, "precio_min"), ({"filtros": {"excluir": "8gb"}}, "excluir"),
    ({"activa": "si"}, "activa"),
])
def test_validar_rechaza_y_dice_el_campo(cambio, campo):
    with pytest.raises(VigilanciaInvalida) as e:
        validar({**VALIDA, **cambio})
    assert campo in str(e.value)


def test_validar_no_repite_el_texto_de_las_consultas_ni_de_las_reglas():
    with pytest.raises(VigilanciaInvalida) as e:
        validar({**VALIDA, "reglas": "ZZREGLA" + "r" * 4000})
    assert "ZZREGLA" not in str(e.value)
    with pytest.raises(VigilanciaInvalida) as e:
        validar({**VALIDA, "consultas": ["ZZCONSULTA"] * 11})
    assert "ZZCONSULTA" not in str(e.value)


def test_el_tope_es_de_5_vigilancias_activas_por_usuario(conn):
    for i in range(5):
        guardar(conn, USUARIO, {**VALIDA, "nombre": f"v{i}"})
    with pytest.raises(VigilanciaInvalida):
        guardar(conn, USUARIO, {**VALIDA, "nombre": "la sexta"})
    guardar(conn, USUARIO, {**VALIDA, "nombre": "v0", "reglas": "cambiada"})                          # actualizar una existente no cuenta de más
    guardar(conn, USUARIO, {**VALIDA, "nombre": "la sexta", "activa": False})                          # una inactiva no cuenta
    assert len(_filas(conn, "SELECT id FROM vigilancias WHERE user_id = %s", (USUARIO,))) == 6


def test_guardar_actualiza_sin_tocar_ultima_ronda(conn):
    v = guardar(conn, USUARIO, VALIDA)
    cur = conn.cursor()
    cur.execute("UPDATE vigilancias SET ultima_ronda = '2026-11-20' WHERE id = %s", (v["id"],))
    conn.commit()
    cur.close()
    again = guardar(conn, USUARIO, {**VALIDA, "reglas": "otras reglas"})
    fila = _filas(conn, "SELECT reglas, ultima_ronda FROM vigilancias WHERE id = %s", (v["id"],))[0]
    assert again == {"id": v["id"], "creada": False, "nombre": "Mac mini"} and v["creada"] is True
    assert fila["reglas"] == "otras reglas" and str(fila["ultima_ronda"]) == "2026-11-20"


def test_listar_activas_devuelve_json_y_hora_ya_cargados(conn):
    guardar(conn, USUARIO, VALIDA)
    guardar(conn, USUARIO, {**VALIDA, "nombre": "parada", "activa": False})
    (v,) = [x for x in repositorio.listar_activas(conn) if x["user_id"] == USUARIO]
    assert v["nombre"] == "Mac mini" and v["consultas"] == VALIDA["consultas"] and v["hora"].strftime("%H:%M") == "07:30"
    assert v["filtros"]["excluir"] == ["8gb", "intel"] and v["activa"] is True
    assert repositorio.listar_activas(conn, ["otro-usuario"]) == []


# ── Carga ────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_26_cargar_crea_la_vigilancia_y_al_volver_a_cargarla_la_actualiza_sin_duplicar(conn, tmp_path):
    ruta = _yaml(tmp_path, VALIDA)
    (r,) = script.cargar(ruta, USUARIO, conn)
    assert r["creada"] is True
    fila = _filas(conn, "SELECT * FROM vigilancias WHERE user_id = %s", (USUARIO,))[0]
    assert fila["nombre"] == "Mac mini" and fila["fuente"] == "wallapop" and fila["activa"] == 1 and fila["ultima_ronda"] is None
    (r2,) = script.cargar(_yaml(tmp_path, {**VALIDA, "reglas": "reglas nuevas"}), USUARIO, conn)
    assert r2["creada"] is False and r2["id"] == r["id"]
    filas = _filas(conn, "SELECT reglas FROM vigilancias WHERE user_id = %s", (USUARIO,))
    assert len(filas) == 1 and filas[0]["reglas"] == "reglas nuevas"


@pytest.mark.parametrize("cambio", [{"consultas": [f"consulta {i}" for i in range(11)]}, {"reglas": "r" * 4001}])
def test_26_con_11_consultas_o_reglas_de_4001_caracteres_falla_sin_escribir(conn, tmp_path, cambio):
    with pytest.raises(VigilanciaInvalida):
        script.cargar(_yaml(tmp_path, {**VALIDA, **cambio}), USUARIO, conn)
    assert _filas(conn, "SELECT id FROM vigilancias WHERE user_id = %s", (USUARIO,)) == []


def test_26_un_fichero_con_varias_vigilancias_es_atomico(conn, tmp_path):
    ruta = _yaml(tmp_path, [VALIDA, {**VALIDA, "nombre": "Otra", "hora": "99:00"}])
    with pytest.raises(VigilanciaInvalida):
        script.cargar(ruta, USUARIO, conn)
    assert _filas(conn, "SELECT id FROM vigilancias WHERE user_id = %s", (USUARIO,)) == []
    script.cargar(_yaml(tmp_path, [VALIDA, {**VALIDA, "nombre": "Otra"}], "dos.yaml"), USUARIO, conn)
    assert len(_filas(conn, "SELECT id FROM vigilancias WHERE user_id = %s", (USUARIO,))) == 2


def test_26_main_dice_en_que_bd_escribe_y_devuelve_1_si_falla(tmp_path, capsys):
    # `main` cierra la conexión del proceso al acabar (es un script), así que esta prueba no usa la fixture `conn`.
    try:
        assert script.main([str(_yaml(tmp_path, VALIDA)), "--user", USUARIO]) == 0
        salida = capsys.readouterr().out
        assert "Escribiendo en BD: sebastian_test" in salida and "creada" in salida and "«Mac mini»" in salida
        assert script.main([str(_yaml(tmp_path, {**VALIDA, "reglas": ""}, "mala.yaml")), "--user", USUARIO]) == 1
        assert "No se ha escrito nada" in capsys.readouterr().err
        assert script.main([str(tmp_path / "no-existe.yaml"), "--user", USUARIO]) == 1
    finally:
        c = get_connection()
        _limpiar(c)
        close_connection()
