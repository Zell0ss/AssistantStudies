"""Servicio de la memoria (fase 2, D31): `guardar(texto)` para la tool `mark_as_memorable`.

Escritura sincrona por una tool del planner: llama al extractor (D32), resuelve cada hecho con la
escalera (D35, `resolucion.py`), escribe y deja cada decision en `mem_decisiones` (D8). Devuelve el
contrato del plan §2.2 para que Alfred confirme lo que guardo, lo que sustituyo y lo nuevo (D16).

Privacidad (D39-D42): al log van ids y tipos de decision, **nunca** el valor ni el texto del usuario.
Las decisiones de BD tampoco los llevan: solo ids y la regla aplicada.
"""
import uuid
from datetime import date, datetime

from logcentral_client import get_logger
from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct

from core.memoria.normalizar import normalizar
from core.memoria.resolucion import (
    decidir_hecho, decidir_retirar_nota, resolver_atributo, resolver_entidad,
)

logger = get_logger("sebastian")

_ESPACIO_NOTAS = uuid.UUID("a4c1d7e0-3b52-4f6a-8d19-5e2f9c0b7a31")
_MAX_ENTIDADES_EN_PROMPT = 60
_NOTAS_CANDIDATAS = 8       # R3: de mas, porque las cerradas siguen en Qdrant y se descartan despues
_OPERACION_DE = {"anadir": "afirmar", "sustituir": "corregir", "retirar": "retirar"}


def _nombre_atributo(crudo: str) -> str:
    """snake_case sin tildes: el mismo normalizador que los alias, con guion bajo."""
    return normalizar(crudo).replace(" ", "_")[:80]


class ServicioMemoria:
    def __init__(self, repo, catalogo, extractor, embedder, qdrant, base: str, umbrales: dict, hoy=date.today):
        self._repo = repo
        self._catalogo = catalogo
        self._extractor = extractor
        self._embedder = embedder
        self._qdrant = qdrant
        self._coleccion_notas = f"{base}_notas"
        self._umbrales = umbrales
        self._hoy = hoy

    # --- API -----------------------------------------------------------------------------

    def guardar(self, user_id: str, texto: str, username: str | None = None) -> dict:
        try:
            hechos = self._extractor.extraer(texto, self.texto_catalogo(user_id, username), self._hoy())
        except Exception as e:
            # Mejora, no camino critico: la memoria caida no rompe el turno (patron de MemoryModule).
            logger.warning(f"memoria.guardar: el extractor fallo: {type(e).__name__}")
            return {"success": False, "result": "No he podido registrar eso ahora mismo.", "data": {}}

        yo = self._repo.entidad_usuario(user_id, username)
        data = {"guardados": [], "nuevos_pendientes": {"entidades": [], "atributos": []},
                "notas": [], "sin_cambio": []}
        turno = {"notas_cerradas": 0}   # R3: como mucho una nota cerrada por similitud en cada turno
        for hecho in hechos:
            self._procesar(user_id, texto, hecho, data, turno)
        logger.info(f"memoria.guardar: user={user_id} hechos={len(hechos)} guardados={len(data['guardados'])} "
                    f"notas={len(data['notas'])} sin_cambio={len(data['sin_cambio'])} yo={yo}")
        return {"success": True, "result": self._resumen(hechos, data), "data": data}

    def texto_catalogo(self, user_id: str, username: str | None = None) -> str:
        """El catalogo del usuario tal como lo ve el extractor: sus entidades y todos los atributos."""
        alias_e = self._repo.alias_de_entidades(user_id)
        alias_a = self._repo.alias_de_atributos()
        entidades = self._repo.listar_entidades(user_id)[-_MAX_ENTIDADES_EN_PROMPT:]
        lineas = ["Entidades del usuario:"]
        for e in entidades:
            etiqueta = "es el propio usuario" if e["es_usuario"] else e["tipo"]
            alias = [a for a in alias_e.get(e["id"], []) if a != normalizar(e["nombre"])]
            lineas.append(f"- {e['nombre']} ({etiqueta})" + (f" · alias: {', '.join(alias)}" if alias else ""))
        if not entidades:
            lineas.append("- (ninguna todavía)")
        lineas += ["", "Atributos:"]
        for a in self._repo.listar_atributos():
            alias = [x for x in alias_a.get(a["id"], []) if x != normalizar(a["nombre"])]
            lineas.append(f"- {a['nombre']} [{a['tipos_entidad']}, {a['cardinalidad']}]: {a['descripcion']}"
                          + (f" · alias: {', '.join(alias)}" if alias else ""))
        return "\n".join(lineas)

    # --- un hecho -------------------------------------------------------------------------

    def _procesar(self, user_id: str, texto: str, hecho: dict, data: dict, turno: dict) -> None:
        retirar = hecho["operacion"] == "retirar"
        ent = self._resolver_entidad(user_id, hecho)
        attr = self._resolver_atributo(hecho)

        if retirar and "crear" in (ent.accion, attr.accion):
            # Olvidar algo que no existe no crea entidades ni atributos. Puede ser una nota de texto libre.
            if not self._retirar_nota(user_id, hecho, texto, ent, attr, data, turno):
                self._decidir_sin_cambio(user_id, ent, attr, "retirar_sin_coincidencia", data,
                                         "No he encontrado qué olvidar.")
            return

        entidad_id = self._materializar_entidad(user_id, hecho, ent, data)
        atributo_id = self._materializar_atributo(user_id, hecho, attr, entidad_tipo=hecho["tipo_entidad"], data=data)
        atributo = self._repo.atributo(atributo_id)
        entidad = self._repo.entidad(entidad_id)

        vigentes = self._repo.hechos_vigentes(user_id, entidad_id, atributo_id)
        fuerte = ent.fuerte and attr.fuerte
        decision = decidir_hecho(hecho["operacion"], atributo["cardinalidad"], vigentes, hecho["valor"], fuerte)
        if decision.regla == "retirar_debil" and self._retirar_nota(user_id, hecho, texto, ent, attr, data, turno):
            return
        senales = self._senales(ent, attr, fuerte, decision.regla)
        confianza = self._confianza(ent, attr)
        detalle = f"entidad={entidad_id} atributo={atributo_id} regla={decision.regla}"

        if decision.tipo == "anadir":
            hid = self._repo.anadir_hecho(user_id, entidad_id, atributo_id, hecho["valor"], confianza=confianza)
            self._repo.registrar_decision(user_id, "anadir", senales, detalle, hecho_id=hid)
            if atributo["nombre"] == "nota":
                self._embeber_nota(user_id, hid, hecho["valor"])   # R3: toda nota se puede encontrar despues
            data["guardados"].append(self._guardado(entidad, atributo, hecho["valor"], "anadir", None))
        elif decision.tipo == "sustituir":
            viejo = self._repo.hecho(decision.hecho_id)
            hid = self._repo.sustituir_hecho(user_id, decision.hecho_id, entidad_id, atributo_id,
                                             hecho["valor"], confianza=confianza)
            self._repo.registrar_decision(user_id, "sustituir", senales, detalle, hecho_id=hid)
            sustituye = {"valor": viejo["valor"], "desde": viejo["valid_from"].date().isoformat()}
            data["guardados"].append(self._guardado(entidad, atributo, hecho["valor"], "sustituir", sustituye))
        elif decision.tipo == "retirar":
            viejo = self._repo.hecho(decision.hecho_id)
            self._repo.retirar_hecho(decision.hecho_id)
            self._repo.registrar_decision(user_id, "retirar", senales, detalle, hecho_id=decision.hecho_id)
            data["guardados"].append(self._guardado(entidad, atributo, viejo["valor"], "retirar", None))
        elif decision.tipo == "nota":
            self._guardar_nota(user_id, texto, entidad_id, senales, detalle, data)
        else:
            self._repo.registrar_decision(user_id, "sin_cambio", senales, detalle, hecho_id=decision.hecho_id)
            data["sin_cambio"].append(decision.aviso or f"{entidad['nombre']} · {atributo['nombre']}: ya constaba.")

    def _decidir_sin_cambio(self, user_id, ent, attr, regla, data, aviso):
        self._repo.registrar_decision(user_id, "sin_cambio", self._senales(ent, attr, False, regla),
                                      f"regla={regla}")
        data["sin_cambio"].append(aviso)

    # --- resolucion y alta de entidades y atributos -------------------------------------------

    def _resolver_entidad(self, user_id: str, hecho: dict):
        por_alias = self._repo.entidades_por_alias(user_id, hecho["entidad"])
        semanticos = [] if len(por_alias) == 1 else self._semantica(
            self._catalogo.buscar_entidades, user_id, f"{hecho['entidad']}: {hecho['tipo_entidad']}")
        return resolver_entidad(por_alias, semanticos, self._umbrales, tipo=hecho["tipo_entidad"])

    def _resolver_atributo(self, hecho: dict):
        # Los candidatos semanticos se enriquecen con `tipos_entidad` (el payload no lo lleva) para la
        # regla de compatibilidad de tipo.
        por_alias = self._repo.atributos_por_alias(hecho["atributo"])
        semanticos = []
        if len(por_alias) != 1:
            consulta = hecho["descripcion_atributo"] or hecho["atributo"].replace("_", " ")
            for c in self._semantica(self._catalogo.buscar_atributos, consulta):
                fila = self._repo.atributo(c["id"])
                if fila:
                    semanticos.append({**c, "tipos_entidad": fila["tipos_entidad"]})
        return resolver_atributo(por_alias, semanticos, self._umbrales, tipo_entidad=hecho["tipo_entidad"])

    def _semantica(self, buscar, *args) -> list[dict]:
        try:
            return buscar(*args)
        except Exception as e:
            # Sin embedder o sin Qdrant se sigue solo con alias exactos y entidades/atributos nuevos.
            logger.warning(f"memoria: busqueda semantica no disponible: {type(e).__name__}")
            return []

    def _materializar_entidad(self, user_id, hecho, res, data) -> int:
        if res.accion == "reutilizar":
            self._repo.registrar_decision(user_id, "reutilizar_entidad", self._senales_res(res),
                                          f"entidad={res.id} via={res.via}")
            return res.id
        entidad_id = self._repo.crear_entidad(user_id, hecho["entidad"], hecho["tipo_entidad"])
        self._indexar(lambda: self._catalogo.indexar_entidad(self._repo.entidad(entidad_id)))
        self._repo.registrar_decision(user_id, "crear_entidad", self._senales_res(res),
                                      f"entidad={entidad_id} tipo={hecho['tipo_entidad']}")
        data["nuevos_pendientes"]["entidades"].append(hecho["entidad"])
        return entidad_id

    def _materializar_atributo(self, user_id, hecho, res, entidad_tipo, data) -> int:
        if res.accion == "reutilizar":
            self._repo.registrar_decision(user_id, "reutilizar_atributo", self._senales_res(res),
                                          f"atributo={res.id} via={res.via}")
            return res.id
        nombre = _nombre_atributo(hecho["atributo"])
        existente = self._repo.atributos_por_alias(nombre)
        if existente:   # carrera o nombre ya tomado: se reutiliza el que existe
            return existente[0]["id"]
        atributo_id = self._repo.crear_atributo(
            nombre, hecho["descripcion_atributo"] or nombre.replace("_", " "),
            tipo_valor=hecho["tipo_valor"], cardinalidad=hecho["cardinalidad"],
            tipos_entidad="*" if entidad_tipo == "otro" else entidad_tipo)
        self._indexar(lambda: self._catalogo.indexar_atributos([self._repo.atributo(atributo_id)]))
        self._repo.registrar_decision(user_id, "crear_atributo", self._senales_res(res),
                                      f"atributo={atributo_id} tipo_valor={hecho['tipo_valor']}")
        data["nuevos_pendientes"]["atributos"].append(nombre)
        return atributo_id

    def _indexar(self, accion) -> None:
        try:
            accion()
        except Exception as e:
            logger.warning(f"memoria: no se pudo indexar en el catalogo semantico: {type(e).__name__}")

    # --- notas ----------------------------------------------------------------------------------

    def _guardar_nota(self, user_id, texto, entidad_id, senales, detalle, data) -> None:
        """Una resolucion debil no sustituye: el texto original se guarda como `nota` y se embebe en
        `<base>_notas` con {hecho_id, user_id} (el texto no va al payload; se lee de SQL)."""
        atributo_nota = self._repo.atributos_por_alias("nota")[0]["id"]
        hid = self._repo.anadir_hecho(user_id, entidad_id, atributo_nota, texto)
        self._repo.registrar_decision(user_id, "nota", senales, detalle, hecho_id=hid)
        self._embeber_nota(user_id, hid, texto)
        if texto not in data["notas"]:
            data["notas"].append(texto)

    def _embeber_nota(self, user_id: str, hecho_id: int, texto: str) -> None:
        """Despues de confirmar en SQL: si falla el embedding la nota queda guardada, sin vector."""
        try:
            vector = self._embedder.embed([texto])[0]
            self._qdrant.upsert(collection_name=self._coleccion_notas, points=[PointStruct(
                id=str(uuid.uuid5(_ESPACIO_NOTAS, f"nota:{hecho_id}")), vector=vector,
                payload={"hecho_id": hecho_id, "user_id": user_id})])
        except Exception as e:
            logger.warning(f"memoria: la nota {hecho_id} se guardo sin embeber: {type(e).__name__}")

    def _retirar_nota(self, user_id, hecho, texto, ent, attr, data, turno) -> bool:
        """R3 (H2-revision §2.3): un `retirar` cuya entidad o atributo no se resuelve con fuerza busca entre
        las notas vigentes **del usuario** y cierra la que encaje, con el mismo liston que una sustitucion.
        Nunca mas de una por turno. Devuelve True si cerro una; si no, el llamador deja su `sin_cambio`."""
        if turno["notas_cerradas"] >= 1:
            return False
        candidatas = self._notas_vigentes_parecidas(user_id, hecho["valor"].strip() or texto)
        decision = decidir_retirar_nota(candidatas, self._umbrales)
        if decision.tipo != "retirar":
            return False
        nota = self._repo.hecho(decision.hecho_id)
        self._repo.retirar_hecho(nota["id"])
        senales = {**self._senales(ent, attr, False, decision.regla),
                   "nota": {"puntuacion": round(candidatas[0]["score"], 3),
                            "margen": round(self._catalogo.margen(candidatas), 3)}}
        self._repo.registrar_decision(user_id, "retirar", senales,
                                      f"hecho={nota['id']} regla={decision.regla}", hecho_id=nota["id"])
        data["guardados"].append(self._guardado(self._repo.entidad(nota["entidad_id"]),
                                                self._repo.atributo(nota["atributo_id"]),
                                                nota["valor"], "retirar", None))
        turno["notas_cerradas"] += 1
        return True

    def _notas_vigentes_parecidas(self, user_id: str, consulta: str) -> list[dict]:
        """[{hecho_id, score}] de mayor a menor. El filtro por `user_id` va en la consulta (D33) y las notas
        cerradas se descartan **antes** de calcular el margen: una cerrada no puede restarselo a la vigente."""
        try:
            vector = self._embedder.embed([consulta])[0]
            puntos = self._qdrant.query_points(
                collection_name=self._coleccion_notas, query=vector, limit=_NOTAS_CANDIDATAS,
                query_filter=Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]),
            ).points
        except Exception as e:
            logger.warning(f"memoria: busqueda de notas no disponible: {type(e).__name__}")
            return []
        candidatas = []
        for p in puntos:
            fila = self._repo.hecho(p.payload["hecho_id"])
            if fila and fila["user_id"] == user_id and fila["valid_to"] is None:
                candidatas.append({"hecho_id": fila["id"], "score": p.score})
        return candidatas

    # --- salida y señales -----------------------------------------------------------------------

    @staticmethod
    def _guardado(entidad, atributo, valor, tipo, sustituye) -> dict:
        return {"entidad": entidad["nombre"], "atributo": atributo["nombre"], "valor": valor,
                "operacion": _OPERACION_DE[tipo], "sustituye": sustituye}

    @staticmethod
    def _senales_res(res) -> dict:
        return {"via": res.via, "fuerte": res.fuerte, "puntuacion": res.puntuacion, "margen": res.margen}

    def _senales(self, ent, attr, fuerte, regla) -> dict:
        return {"entidad": self._senales_res(ent), "atributo": self._senales_res(attr),
                "fuerte": fuerte, "regla": regla}

    @staticmethod
    def _confianza(ent, attr) -> float:
        """Calculada con señales (D8), no la declara el LLM: la menor puntuacion de las dos resoluciones.
        Alias exacto = 1,0; busqueda semantica = su puntuacion; lo creado en este turno no resta."""
        puntuaciones = [r.puntuacion for r in (ent, attr) if r.puntuacion is not None]
        return round(min(puntuaciones), 3) if puntuaciones else 1.0

    @staticmethod
    def _resumen(hechos, data) -> str:
        if not hechos:
            return "No he encontrado nada que guardar."
        partes = []
        n = {op: sum(1 for g in data["guardados"] if g["operacion"] == op) for op in ("afirmar", "corregir", "retirar")}
        for op, texto in (("afirmar", "apuntado"), ("corregir", "corregido"), ("retirar", "retirado")):
            if n[op]:
                partes.append(f"{n[op]} {texto}")
        if data["notas"]:
            partes.append(f"{len(data['notas'])} guardado como nota")
        if data["sin_cambio"]:
            partes.append(f"{len(data['sin_cambio'])} sin cambio")
        return ", ".join(partes).capitalize() + "."

    # --- construccion desde la config ---------------------------------------------------------------

    @classmethod
    def desde_config(cls, db, config: dict, on_usage=None):
        """El servicio de produccion. Las colecciones salen de `memory_collection` (D34, D19)."""
        import anthropic
        from qdrant_client import QdrantClient

        from core.memoria.ajustes import umbrales
        from core.memoria.catalogo import Catalogo
        from core.memoria.embedder import OpenAIEmbedder
        from core.memoria.extractor import Extractor
        from core.memoria.repositorio import RepositorioMemoria

        base = config["memory_collection"]   # D20: sin valor por defecto, que no caiga en produccion
        repo = RepositorioMemoria(db)
        embedder = OpenAIEmbedder(config["openai_apikey"])
        qdrant = QdrantClient(url=config.get("qdrant_url", "http://localhost:6333"))
        extractor = Extractor(anthropic.Anthropic(api_key=config["anthropic_apikey"]), on_usage=on_usage)
        return cls(repo, Catalogo(repo, embedder, qdrant, base), extractor, embedder, qdrant, base, umbrales(config))
