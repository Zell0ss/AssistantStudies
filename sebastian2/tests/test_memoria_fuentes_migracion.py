"""H3 (R7, D41): migración 012, la frase de origen de cada hecho. Contra `sebastian_test`; sin API."""
import re
from pathlib import Path

from db.connection import close_connection, get_connection

RAIZ = Path(__file__).resolve().parent.parent
MIGRACION = RAIZ / "db" / "migrations" / "012_memoria_fuentes.sql"


def _sentencias():
    sql = re.sub(r"--[^\n]*", "", MIGRACION.read_text())
    return [s.strip() for s in sql.split(";") if s.strip()]


def _filas(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params)
    return list(cur.fetchall())


def test_la_migracion_existe_y_no_lleva_use():
    assert MIGRACION.exists()
    assert not re.search(r"(?im)^\s*USE\s+", MIGRACION.read_text())      # D20: la BD la elige quien aplica


def test_mem_fuentes_tiene_las_columnas_del_contrato():
    conn = get_connection()
    try:
        cols = {c["COLUMN_NAME"]: c for c in _filas(
            conn, "SELECT COLUMN_NAME, IS_NULLABLE, DATA_TYPE FROM information_schema.COLUMNS"
                  " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mem_fuentes'")}
        assert set(cols) == {"id", "user_id", "texto", "mensaje", "purgada_at", "created_at"}
        assert cols["texto"]["IS_NULLABLE"] == "YES" and cols["mensaje"]["IS_NULLABLE"] == "YES"   # NULL = purgada
        assert cols["user_id"]["IS_NULLABLE"] == "NO" and cols["created_at"]["IS_NULLABLE"] == "NO"
        indices = {i["INDEX_NAME"] for i in _filas(
            conn, "SELECT INDEX_NAME FROM information_schema.STATISTICS"
                  " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mem_fuentes'")}
        assert "idx_user_fecha" in indices
    finally:
        close_connection()


def test_mem_hechos_apunta_a_su_fuente_con_clave_ajena_e_indice():
    conn = get_connection()
    try:
        [col] = _filas(conn, "SELECT IS_NULLABLE, DATA_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE()"
                             " AND TABLE_NAME = 'mem_hechos' AND COLUMN_NAME = 'fuente_id'")
        assert col["IS_NULLABLE"] == "YES" and col["DATA_TYPE"] == "bigint"   # NULL solo para lo anterior (D18)
        fk = _filas(conn, "SELECT REFERENCED_TABLE_NAME AS t FROM information_schema.KEY_COLUMN_USAGE"
                          " WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'mem_hechos' AND COLUMN_NAME = 'fuente_id'"
                          " AND REFERENCED_TABLE_NAME IS NOT NULL")
        assert [f["t"] for f in fk] == ["mem_fuentes"]
        indices = _filas(conn, "SELECT INDEX_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE()"
                               " AND TABLE_NAME = 'mem_hechos' AND COLUMN_NAME = 'fuente_id'")
        assert indices, "fuente_id tiene que tener índice"
    finally:
        close_connection()


def test_la_migracion_es_idempotente():
    conn = get_connection()
    try:
        antes = _filas(conn, "SELECT COUNT(*) AS n FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA = DATABASE()"
                             " AND TABLE_NAME = 'mem_hechos' AND COLUMN_NAME = 'fuente_id'")[0]["n"]
        cur = conn.cursor()
        for _ in range(2):
            for sentencia in _sentencias():
                cur.execute(sentencia)
            conn.commit()
        despues = _filas(conn, "SELECT COUNT(*) AS n FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA = DATABASE()"
                               " AND TABLE_NAME = 'mem_hechos' AND COLUMN_NAME = 'fuente_id'")[0]["n"]
        assert despues == antes                       # ni columna, ni clave ajena, ni índice duplicados
    finally:
        close_connection()
