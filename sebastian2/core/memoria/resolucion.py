"""Escalera de resolucion y reglas de decision del hecho (fase 2, D35, D8). Funciones puras.

El LLM propone nombres; quien decide es este codigo (D8). Escalera: alias exacto normalizado ->
busqueda semantica con puntuacion y margen (umbrales de `config.memoria.umbrales`) -> crear. **Solo se
sustituye con resolucion fuerte** (D35): una sustitucion erronea hace olvidar algo cierto sin avisar.
"""
from dataclasses import dataclass

from core.memoria.normalizar import normalizar


@dataclass(frozen=True)
class Resolucion:
    accion: str                 # 'reutilizar' | 'crear'
    id: int | None
    fuerte: bool
    via: str                    # 'alias' | 'semantica' | 'nueva'
    puntuacion: float | None = None
    margen: float | None = None


@dataclass(frozen=True)
class DecisionHecho:
    tipo: str                   # 'anadir' | 'sustituir' | 'retirar' | 'nota' | 'sin_cambio'
    hecho_id: int | None = None
    regla: str = ""
    aviso: str = ""


NUEVA = Resolucion("crear", None, False, "nueva")


def compatible(tipos_entidad: str, tipo_entidad: str) -> bool:
    """`tipos_entidad` de un atributo es un csv de tipos o '*'."""
    tipos = {t.strip() for t in tipos_entidad.split(",")}
    return "*" in tipos or tipo_entidad in tipos


def _margen(candidatos: list[dict]) -> float:
    if len(candidatos) < 2:
        return candidatos[0]["score"] if candidatos else 0.0
    return candidatos[0]["score"] - candidatos[1]["score"]


def _semantica(candidatos: list[dict], umbrales: dict):
    """(candidata, fuerte, margen) si la mejor llega a `reutilizar`; si no, None."""
    if not candidatos:
        return None
    mejor, margen = candidatos[0], _margen(candidatos)
    u = umbrales["reutilizar"]
    if mejor["score"] < u["puntuacion"] or margen < u["margen"]:
        return None
    s = umbrales["sustituir"]
    return mejor, mejor["score"] >= s["puntuacion"] and margen >= s["margen"], margen


def resolver_atributo(por_alias: list[dict], semanticos: list[dict], umbrales: dict, *,
                      tipo_entidad: str, tipo_valor: str | None = None) -> Resolucion:
    """`por_alias`: atributos cuyo alias normalizado coincide. `semanticos`: candidatos del catalogo
    (de mayor a menor puntuacion), ya con `tipos_entidad` y `tipo_valor`. Un atributo cuyo tipo no encaja con el
    de la entidad cuenta como resolucion debil.

    D69 (R12): por semantica, un `tipo_valor` distinto del del candidato tambien la hace debil. Un id (numero) y
    un usuario (texto) no son el mismo atributo aunque suenen parecido; con una resolucion debil, `decidir_hecho`
    manda el hecho a `nota` en lugar de sustituir. Por alias no se toca: el nombre exacto manda."""
    if len(por_alias) == 1:
        a = por_alias[0]
        return Resolucion("reutilizar", a["id"], compatible(a["tipos_entidad"], tipo_entidad), "alias", 1.0)
    encontrada = _semantica(semanticos, umbrales)
    if encontrada is None:
        return NUEVA
    mejor, fuerte, margen = encontrada
    fuerte = fuerte and compatible(mejor.get("tipos_entidad", "*"), tipo_entidad)
    if tipo_valor is not None and mejor.get("tipo_valor", tipo_valor) != tipo_valor:
        fuerte = False
    return Resolucion("reutilizar", mejor["id"], fuerte, "semantica", mejor["score"], margen)


def resolver_entidad(por_alias: list[dict], semanticos: list[dict], umbrales: dict, *, tipo: str) -> Resolucion:
    """Igual para entidades. El tipo `otro` no contradice a ninguno; dos tipos concretos distintos, si."""
    def encaja(tipo_existente: str) -> bool:
        return "otro" in (tipo, tipo_existente) or tipo == tipo_existente

    if len(por_alias) == 1:
        e = por_alias[0]
        return Resolucion("reutilizar", e["id"], encaja(e["tipo"]), "alias", 1.0)
    encontrada = _semantica(semanticos, umbrales)
    if encontrada is None:
        return NUEVA
    mejor, fuerte, margen = encontrada
    fuerte = fuerte and encaja(mejor.get("tipo_entidad", "otro"))
    return Resolucion("reutilizar", mejor["id"], fuerte, "semantica", mejor["score"], margen)


def decidir_retirar_nota(candidatas: list[dict], umbrales: dict) -> DecisionHecho:
    """Retirar una nota de texto libre por similitud (H2-revision §2.3, R3).

    `candidatas`: [{hecho_id, score}] de las notas **vigentes** del usuario, de mayor a menor puntuacion
    (las cerradas ya vienen fuera: una nota cerrada no puede restar margen a la que queda). Solo se cierra
    con el mismo listón que una sustitucion (D35): puntuacion y margen de `umbrales["sustituir"]`.
    """
    sin_cambio = {"aviso": "No he encontrado qué olvidar."}
    if not candidatas:
        return DecisionHecho("sin_cambio", regla="retirar_nota_sin_candidatas", **sin_cambio)
    s = umbrales["sustituir"]
    if candidatas[0]["score"] < s["puntuacion"]:
        return DecisionHecho("sin_cambio", regla="retirar_nota_debil", **sin_cambio)
    if _margen(candidatas) < s["margen"]:
        return DecisionHecho("sin_cambio", regla="retirar_nota_ambigua", **sin_cambio)
    return DecisionHecho("retirar", candidatas[0]["hecho_id"], "retirar_nota")


def decidir_hecho(operacion: str, cardinalidad: str, vigentes: list[dict], valor: str,
                  fuerte: bool) -> DecisionHecho:
    """Que hacer con el hecho, segun las reglas del plan §3 H2.2. `vigentes`: [{id, valor}]."""
    objetivo = normalizar(valor)
    iguales = [v for v in vigentes if normalizar(v["valor"]) == objetivo]

    if operacion == "retirar":
        if not fuerte:
            return DecisionHecho("sin_cambio", regla="retirar_debil",
                                 aviso="No he encontrado qué olvidar.")
        if cardinalidad == "uno" and len(vigentes) == 1:
            return DecisionHecho("retirar", vigentes[0]["id"], "retirar_fuerte")
        if iguales:
            return DecisionHecho("retirar", iguales[0]["id"], "retirar_fuerte")
        if len(vigentes) == 1 and not objetivo:
            return DecisionHecho("retirar", vigentes[0]["id"], "retirar_fuerte")
        return DecisionHecho("sin_cambio", regla="retirar_sin_coincidencia",
                             aviso="No he encontrado qué olvidar.")

    if cardinalidad == "varios":
        if iguales:
            return DecisionHecho("sin_cambio", iguales[0]["id"], "varios_mismo_valor")
        return DecisionHecho("anadir", regla="varios_anade")

    if not vigentes:
        return DecisionHecho("anadir", regla="uno_sin_vigente")
    if iguales:
        return DecisionHecho("sin_cambio", iguales[0]["id"], "uno_igual")
    if fuerte:
        return DecisionHecho("sustituir", vigentes[0]["id"], "uno_distinto_fuerte")
    return DecisionHecho("nota", regla="uno_distinto_debil")
