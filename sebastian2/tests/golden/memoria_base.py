"""Piezas del harness de goldens para la memoria nueva (fase 2, H3, plan §3 H3.2).

Siembra la memoria de test en MariaDB (lo que antes se sembraba como tres puntos planos en Qdrant), la
limpia entre goldens y da las consultas con las que los escenarios comprueban **la BD**, no solo la tool.

Toda escritura pasa por `exigir_bd_de_test`: este harness borra filas, y no puede hacerlo en otra BD que
`sebastian_test` (mismo criterio que la fixture `test_db`). Se prueba sin API en tests/test_golden_memoria_base.py.
"""
from core.memoria.normalizar import normalizar
from core.memoria.repositorio import RepositorioMemoria

BD_DE_TEST = "sebastian_test"
USUARIO_B = "golden_test_user_b"   # E7: otro usuario autorizado, para probar que no ve lo del primero (D33)

# Los tres recuerdos que antes se sembraban en Qdrant: «Paco es alérgico a los frutos secos» (golden #21 tiene
# que encontrarlo), el gusto por el vino y el cumpleaños de Rebe. (entidad, tipo, atributo, valor)
MEMORIA_BASE = (
    ("Paco", "persona", "alergia", "frutos secos"),
    ("yo", None, "preferencia", "el vino tinto de Ribera del Duero"),
    ("Rebe", "persona", "cumpleanos", "marzo"),
)


def exigir_bd_de_test(db) -> None:
    cur = db.cursor()
    cur.execute("SELECT DATABASE() AS db")
    actual = cur.fetchone()["db"]
    cur.close()
    if actual != BD_DE_TEST:
        raise RuntimeError(f"El harness de memoria solo escribe en '{BD_DE_TEST}', y la conexión apunta a '{actual}'.")


def limpiar_memoria(db, *user_ids: str) -> None:
    """Borra hechos, decisiones y entidades (con sus alias) de esos usuarios. El catálogo de atributos no."""
    exigir_bd_de_test(db)
    cur = db.cursor()
    for u in user_ids:
        cur.execute("DELETE FROM mem_decisiones WHERE user_id = %s", (u,))
        cur.execute("UPDATE mem_hechos SET superseded_by = NULL WHERE user_id = %s", (u,))
        cur.execute("DELETE FROM mem_hechos WHERE user_id = %s", (u,))
        cur.execute("DELETE FROM mem_entidad_alias WHERE entidad_id IN"
                    " (SELECT id FROM mem_entidades WHERE user_id = %s)", (u,))
        cur.execute("DELETE FROM mem_entidades WHERE user_id = %s", (u,))
    db.commit()


def limpiar_atributos_de_conversacion(db) -> None:
    """Quita del catálogo los atributos que creó una conversación y ya no usa ningún hecho, para que un escenario
    que espera `crear_atributo` lo vea también en la segunda pasada. Las semillas y los del vault no se tocan."""
    exigir_bd_de_test(db)
    cur = db.cursor()
    sin_hechos = ("SELECT id FROM mem_atributos WHERE fuente = 'conversacion'"
                  " AND id NOT IN (SELECT DISTINCT atributo_id FROM mem_hechos)")
    cur.execute(f"DELETE FROM mem_atributo_alias WHERE atributo_id IN ({sin_hechos})")
    cur.execute("DELETE FROM mem_atributos WHERE fuente = 'conversacion'"
                " AND id NOT IN (SELECT DISTINCT atributo_id FROM mem_hechos)")
    db.commit()


def sembrar_memoria_base(db, user_id: str) -> None:
    """La entidad «yo» del usuario y los tres hechos de MEMORIA_BASE. Parte de una memoria vacía."""
    exigir_bd_de_test(db)
    repo = RepositorioMemoria(db)
    yo = repo.entidad_usuario(user_id)
    for entidad, tipo, atributo, valor in MEMORIA_BASE:
        if tipo is None:
            entidad_id = yo
        else:
            entidad_id = repo.crear_entidad(user_id, entidad, tipo, estado="activo", origen="semilla")
        repo.anadir_hecho(user_id, entidad_id, repo.atributos_por_alias(atributo)[0]["id"], valor)


def hechos(db, user_id: str, *, entidad: str | None = None, atributo: str | None = None,
           vigentes: bool | None = None) -> list[dict]:
    """Hechos del usuario con `entidad` y `atributo` como nombres. `entidad` se compara como un alias
    («Paco» = «paco»); `vigentes`: True solo los vigentes, False solo los cerrados, None todos."""
    filas = RepositorioMemoria(db).hechos_con_nombres(user_id, solo_vigentes=False)
    if entidad is not None:
        filas = [f for f in filas if normalizar(f["entidad"]) == normalizar(entidad)]
    if atributo is not None:
        filas = [f for f in filas if f["atributo"] == atributo]
    if vigentes is not None:
        filas = [f for f in filas if (f["valid_to"] is None) == vigentes]
    return filas


def decisiones(db, user_id: str) -> list[dict]:
    return RepositorioMemoria(db).decisiones(user_id)
