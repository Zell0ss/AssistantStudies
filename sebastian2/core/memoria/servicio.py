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
from qdrant_client.models import FieldCondition, Filter, MatchValue, PointIdsList, PointStruct

from core.memoria.normalizar import normalizar
from core.memoria.resolucion import (
    decidir_hecho, decidir_retirar_nota, resolver_atributo, resolver_entidad, valor_encaja,
)
from core.memoria.vault import CAMPOS_CONTRATO, leer_proyectos, proyecto_por_nombre

logger = get_logger("sebastian")

_ESPACIO_NOTAS = uuid.UUID("a4c1d7e0-3b52-4f6a-8d19-5e2f9c0b7a31")
_MAX_ENTIDADES_EN_PROMPT = 60
_NOTAS_CANDIDATAS = 8       # R3: de mas, porque las cerradas siguen en Qdrant y se descartan despues
_MAX_NOTAS_EN_CONSULTA = 3  # search_memory: las notas mas parecidas que se devuelven
_OPERACION_DE = {"anadir": "afirmar", "sustituir": "corregir", "retirar": "retirar"}


def _nombre_atributo(crudo: str) -> str:
    """snake_case sin tildes: el mismo normalizador que los alias, con guion bajo."""
    return normalizar(crudo).replace(" ", "_")[:80]


class ServicioMemoria:
    def __init__(self, repo, catalogo, extractor, embedder, qdrant, base: str, umbrales: dict, hoy=date.today,
                 vault_path: str | None = None, propietario_vault: str = ""):
        self._repo = repo
        self._catalogo = catalogo
        self._extractor = extractor
        self._embedder = embedder
        self._qdrant = qdrant
        self._coleccion_notas = f"{base}_notas"
        self._umbrales = umbrales
        self._hoy = hoy
        self._vault_path = vault_path            # `vault_docs_path` (D37); sin el, no hay datos en vivo
        self._propietario_vault = propietario_vault

    # --- API -----------------------------------------------------------------------------

    def guardar(self, user_id: str, texto: str, username: str | None = None, mensaje: str | None = None) -> dict:
        """`texto` es lo que recibio el extractor (la frase autocontenida del planner); `mensaje`, el literal del
        usuario en ese turno. Los dos quedan en una fuente (D41), de la que cuelgan los hechos de esta llamada."""
        try:
            hechos = self._extractor.extraer(texto, self.texto_catalogo(user_id, username), self._hoy())
        except Exception as e:
            # Mejora, no camino critico: la memoria caida no rompe el turno (patron de MemoryModule).
            logger.warning(f"memoria.guardar: el extractor fallo: {type(e).__name__}")
            return {"success": False, "result": "No he podido registrar eso ahora mismo.", "data": {}}

        yo = self._repo.entidad_usuario(user_id, username)
        data = {"guardados": [], "nuevos_pendientes": {"entidades": [], "atributos": []},
                "notas": [], "sin_cambio": []}
        # Una fuente por llamada, aunque la frase de varios hechos o ninguno (D41). R3 y R9: como mucho UN cierre
        # indirecto (por similitud con una nota, o por el valor) en cada turno, compartido.
        # D69 (R11): `atributos_creados` = ids de los atributos que abrió esta llamada.
        turno = {"cierres_indirectos": 0, "fuente_id": self._repo.crear_fuente(user_id, texto, mensaje),
                 "atributos_creados": set()}
        for hecho in hechos:
            self._procesar(user_id, texto, hecho, data, turno)
        # Si no dejo ningun hecho (frase vacia, o todo «ya constaba»), no queda texto sin hecho (D42).
        self._repo.purgar_fuente_sin_hechos(turno["fuente_id"])
        # R10: el extractor descarto hechos cuya entidad era un marcador (`<UNKNOWN>`): no supo de quien hablaba.
        sin_entidad = getattr(self._extractor, "marcadores_descartados", 0)
        if sin_entidad:
            data["sin_cambio"].append("No he sabido de quién o de qué se hablaba en parte de lo dicho: ¿de quién se trata?")
        # H1c (R10c, D42): `chars` es solo la longitud de lo que recibió el extractor; si el planner manda una frase vacía
        # o de pocas letras, se ve sin guardar el texto.
        logger.info(f"memoria.guardar: user={user_id} hechos={len(hechos)} guardados={len(data['guardados'])} "
                    f"notas={len(data['notas'])} sin_cambio={len(data['sin_cambio'])} yo={yo} chars={len(texto)}")
        resumen = self._resumen(hechos, data)
        if sin_entidad and not hechos:
            resumen = "No sé de quién o de qué se habla."
        return {"success": True, "result": resumen, "data": data}

    def consultar(self, user_id: str, query: str, entidad: str | None = None, atributo: str | None = None,
                  historial: bool = False) -> dict:
        """`search_memory` (plan §2.3). La entidad y el atributo se resuelven **solo por alias exacto** y la
        consulta se arma con ids: no hay SQL libre ni busqueda semantica sobre el catalogo. Lo unico semantico
        son las notas de texto libre. Si el vault tiene el proyecto, añade su valor en vivo y marca el choque
        con lo dicho en conversacion (D37: gana el vault)."""
        salida = {"hechos": [], "historial": [], "notas": [], "vault": None, "conflictos": []}
        ent = self._por_alias_unico(self._repo.entidades_por_alias(user_id, entidad)) if entidad else None
        attr = self._por_alias_unico(self._repo.atributos_por_alias(atributo)) if atributo else None

        # Pedir una entidad o un atributo que no se resuelven no amplia la consulta a «todo».
        if (entidad and ent is None) or (atributo and attr is None) or (not entidad and not atributo):
            filas = []
        else:
            filas = self._repo.hechos_con_nombres(user_id, ent["id"] if ent else None, attr["id"] if attr else None,
                                                  solo_vigentes=False)
        for f in filas:
            if f["valid_to"] is None:
                salida["hechos"].append({"entidad": f["entidad"], "atributo": f["atributo"], "valor": f["valor"],
                                         "desde": f["valid_from"].date().isoformat()})
            elif historial and f["valor"] != "":    # lo olvidado (D42) ya no tiene texto: no sale una entrada vacia
                salida["historial"].append({
                    "entidad": f["entidad"], "atributo": f["atributo"], "valor": f["valor"],
                    "desde": f["valid_from"].date().isoformat(), "hasta": f["valid_to"].date().isoformat(),
                    "sustituido_por": f["sustituido_por_valor"]})

        if query:
            salida["notas"] = self._notas_para(user_id, query)
        salida["vault"], salida["conflictos"] = self._vault_y_conflictos(user_id, entidad, ent, atributo, attr)
        logger.info(f"memoria.consultar: user={user_id} hechos={len(salida['hechos'])} "
                    f"historial={len(salida['historial'])} notas={len(salida['notas'])} "
                    f"vault={salida['vault'] is not None} conflictos={len(salida['conflictos'])}")
        return salida

    @staticmethod
    def _por_alias_unico(filas: list[dict]) -> dict | None:
        """Un alias ambiguo (dos entidades o atributos) no se resuelve: mejor no contestar que contestar mal."""
        return filas[0] if len(filas) == 1 else None

    def _notas_para(self, user_id: str, query: str) -> list[dict]:
        minimo = self._umbrales["reutilizar"]["puntuacion"]   # tentativo: se calibro para el catalogo, no para notas
        parecidas = [c for c in self._notas_vigentes_parecidas(user_id, query) if c["score"] >= minimo]
        notas = []
        for c in parecidas[:_MAX_NOTAS_EN_CONSULTA]:
            n = self._repo.hecho(c["hecho_id"])
            notas.append({"texto": n["valor"], "entidad": self._repo.entidad(n["entidad_id"])["nombre"],
                          "desde": n["valid_from"].date().isoformat()})
        return notas

    def _vault_y_conflictos(self, user_id, entidad, ent, atributo, attr) -> tuple[dict | None, list]:
        """D37. Solo para el propietario del vault y solo para los campos del contrato."""
        if not entidad or not self._vault_path or user_id != self._propietario_vault:
            return None, []
        proyectos = leer_proyectos(self._vault_path)
        hallado = proyecto_por_nombre(proyectos, ent["nombre"] if ent else entidad) \
            or proyecto_por_nombre(proyectos, entidad)
        if hallado is None:
            return None, []
        carpeta, campos = hallado
        if atributo:
            if attr is None or attr["nombre"] not in CAMPOS_CONTRATO:
                return None, []
            campos = {k: v for k, v in campos.items() if k == attr["nombre"]}
        if not campos:
            return None, []
        conflictos = []
        for campo, valor_vault in campos.items():
            if ent is None:
                break
            propio = self._repo.atributos_por_alias(campo)
            if len(propio) != 1:
                continue
            for h in self._repo.hechos_vigentes(user_id, ent["id"], propio[0]["id"]):
                if normalizar(h["valor"]) != normalizar(valor_vault):
                    conflictos.append({"entidad": ent["nombre"], "atributo": campo, "vault": valor_vault,
                                       "conversacion": h["valor"], "desde": h["valid_from"].date().isoformat(),
                                       "gana": "vault"})
        return {"proyecto": carpeta, "campos": campos}, conflictos

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
        attr = self._resolver_atributo(hecho, turno["atributos_creados"])

        if retirar and "crear" in (ent.accion, attr.accion):
            # Olvidar algo que no existe no crea entidades ni atributos. Puede ser una nota de texto libre.
            if not (self._retirar_nota(user_id, hecho, texto, ent, attr, data, turno)
                    or self._retirar_por_valor(user_id, hecho, ent, attr, data, turno)):
                self._decidir_sin_cambio(user_id, ent, attr, "retirar_sin_coincidencia", data,
                                         "No he encontrado qué olvidar.")
            return

        entidad_id = self._materializar_entidad(user_id, hecho, ent, data)
        atributo_id = self._materializar_atributo(user_id, hecho, attr, entidad_tipo=hecho["tipo_entidad"], data=data)
        if attr.accion == "crear":
            turno["atributos_creados"].add(atributo_id)          # D69 (R11): ya no es candidato semantico en esta llamada
        atributo = self._repo.atributo(atributo_id)
        entidad = self._repo.entidad(entidad_id)

        vigentes = self._repo.hechos_vigentes(user_id, entidad_id, atributo_id)
        # D70 (R13): el valor tiene que encajar con el tipo del atributo, también si el nombre coincidió por alias (el
        # extractor usa el nombre exacto del catálogo, que no le enseña el tipo). Si no encaja, la resolución es débil: con un
        # valor vigente va a `nota` y sin él se añade. `retirar` no se mira: su valor puede ir vacío. Lo recién creado
        # tiene el tipo del propio hecho.
        tipo_no_encaja = (not retirar and attr.accion == "reutilizar"
                          and not valor_encaja(hecho["valor"], atributo["tipo_valor"]))
        fuerte = ent.fuerte and attr.fuerte and not tipo_no_encaja
        decision = decidir_hecho(hecho["operacion"], atributo["cardinalidad"], vigentes, hecho["valor"], fuerte)
        if decision.regla == "retirar_debil" and (self._retirar_nota(user_id, hecho, texto, ent, attr, data, turno)
                                                  or self._retirar_por_valor(user_id, hecho, ent, attr, data, turno)):
            return
        senales = self._senales(ent, attr, fuerte, decision.regla)
        if tipo_no_encaja:
            senales["tipo_no_encaja"] = True                 # solo la señal, nunca el valor (D42)
        confianza = self._confianza(ent, attr)
        detalle = f"entidad={entidad_id} atributo={atributo_id} regla={decision.regla}"

        if decision.tipo == "anadir":
            hid = self._repo.anadir_hecho(user_id, entidad_id, atributo_id, hecho["valor"], confianza=confianza,
                                          fuente_id=turno["fuente_id"])
            self._repo.registrar_decision(user_id, "anadir", senales, detalle, hecho_id=hid)
            if atributo["nombre"] == "nota":
                self._embeber_nota(user_id, hid, hecho["valor"])   # R3: toda nota se puede encontrar despues
            data["guardados"].append(self._guardado(entidad, atributo, hecho["valor"], "anadir", None))
        elif decision.tipo == "sustituir":
            viejo = self._repo.hecho(decision.hecho_id)
            hid = self._repo.sustituir_hecho(user_id, decision.hecho_id, entidad_id, atributo_id,
                                             hecho["valor"], confianza=confianza, fuente_id=turno["fuente_id"])
            self._repo.registrar_decision(user_id, "sustituir", senales, detalle, hecho_id=hid)
            sustituye = {"valor": viejo["valor"], "desde": viejo["valid_from"].date().isoformat()}
            data["guardados"].append(self._guardado(entidad, atributo, hecho["valor"], "sustituir", sustituye))
        elif decision.tipo == "retirar":
            viejo = self._repo.hecho(decision.hecho_id)
            self._retirar(user_id, decision.hecho_id)
            self._repo.registrar_decision(user_id, "retirar", senales, detalle, hecho_id=decision.hecho_id)
            data["guardados"].append(self._guardado(entidad, atributo, viejo["valor"], "retirar", None))
        elif decision.tipo == "nota":
            self._guardar_nota(user_id, texto, entidad_id, senales, detalle, data, turno["fuente_id"])
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
        semanticos = []
        if len(por_alias) != 1:
            # SQL manda: un punto del catalogo cuya entidad ya no existe (o no es de este usuario) no cuenta.
            candidatos = self._semantica(
                self._catalogo.buscar_entidades, user_id, f"{hecho['entidad']}: {hecho['tipo_entidad']}")
            semanticos = [c for c in candidatos if self._es_entidad_de(user_id, c["id"])]
        return resolver_entidad(por_alias, semanticos, self._umbrales, tipo=hecho["tipo_entidad"])

    def _es_entidad_de(self, user_id: str, entidad_id: int) -> bool:
        fila = self._repo.entidad(entidad_id)
        return fila is not None and fila["user_id"] == user_id

    def _resolver_atributo(self, hecho: dict, creados_en_el_turno: frozenset | set = frozenset()):
        # Los candidatos semanticos se enriquecen con `tipos_entidad` y `tipo_valor` (el payload no los lleva) para las
        # reglas de compatibilidad de tipo (R12, D69).
        por_alias = self._repo.atributos_por_alias(hecho["atributo"])
        semanticos = []
        if len(por_alias) != 1:
            consulta = hecho["descripcion_atributo"] or hecho["atributo"].replace("_", " ")
            for c in self._semantica(self._catalogo.buscar_atributos, consulta):
                # D69 (R11): un atributo creado en esta misma llamada no es candidato semantico de otro hecho de la misma
                # frase (un hecho no sustituye a otro de su frase). Por alias exacto si se reutiliza, y arriba ya se miro.
                if c["id"] in creados_en_el_turno:
                    continue
                fila = self._repo.atributo(c["id"])
                if fila:
                    semanticos.append({**c, "tipos_entidad": fila["tipos_entidad"], "tipo_valor": fila["tipo_valor"]})
        # D69 (R12): `retirar` no pasa por el tipo del valor: su valor va vacío y `_validar` pone `texto` por defecto.
        return resolver_atributo(por_alias, semanticos, self._umbrales, tipo_entidad=hecho["tipo_entidad"],
                                 tipo_valor=None if hecho["operacion"] == "retirar" else hecho["tipo_valor"])

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

    def _guardar_nota(self, user_id, texto, entidad_id, senales, detalle, data, fuente_id=None) -> None:
        """Una resolucion debil no sustituye: el texto original se guarda como `nota` y se embebe en
        `<base>_notas` con {hecho_id, user_id} (el texto no va al payload; se lee de SQL)."""
        atributo_nota = self._repo.atributos_por_alias("nota")[0]["id"]
        hid = self._repo.anadir_hecho(user_id, entidad_id, atributo_nota, texto, fuente_id=fuente_id)
        self._repo.registrar_decision(user_id, "nota", senales, detalle, hecho_id=hid)
        self._embeber_nota(user_id, hid, texto)
        if texto not in data["notas"]:
            data["notas"].append(texto)

    def _retirar(self, user_id: str, hecho_id: int) -> None:
        """«Olvida lo de...» (D42): cierra y purga en una transaccion (SQL manda) y, despues del commit, borra el
        vector de las notas purgadas. Si Qdrant falla se avisa, sin texto, y el turno sigue: la nota ya no esta
        vigente y su texto ya no esta en SQL, asi que un punto huerfano no puede devolverla (se filtra por SQL)."""
        notas = self._repo.retirar_y_purgar(user_id, hecho_id)
        if not notas:
            return
        try:
            self._qdrant.delete(collection_name=self._coleccion_notas, points_selector=PointIdsList(
                points=[str(uuid.uuid5(_ESPACIO_NOTAS, f"nota:{n}")) for n in notas]))
        except Exception as e:
            logger.warning(f"memoria: no se pudo borrar el vector de {len(notas)} nota(s) retirada(s): "
                           f"{type(e).__name__}")

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
        if turno["cierres_indirectos"] >= 1:
            return False
        candidatas = self._notas_vigentes_parecidas(user_id, hecho["valor"].strip() or texto)
        decision = decidir_retirar_nota(candidatas, self._umbrales)
        if decision.tipo != "retirar":
            return False
        nota = self._repo.hecho(decision.hecho_id)
        self._retirar(user_id, nota["id"])
        senales = {**self._senales(ent, attr, False, decision.regla),
                   "nota": {"puntuacion": round(candidatas[0]["score"], 3),
                            "margen": round(self._catalogo.margen(candidatas), 3)}}
        self._repo.registrar_decision(user_id, "retirar", senales,
                                      f"hecho={nota['id']} regla={decision.regla}", hecho_id=nota["id"])
        data["guardados"].append(self._guardado(self._repo.entidad(nota["entidad_id"]),
                                                self._repo.atributo(nota["atributo_id"]),
                                                nota["valor"], "retirar", None))
        turno["cierres_indirectos"] += 1
        return True

    def _retirar_por_valor(self, user_id, hecho, ent, attr, data, turno) -> bool:
        """R9 (H3-revision): un `retirar` sin entidad resuelta con fuerza, y sin nota que supere el umbral de R3, busca
        entre los hechos vigentes **del usuario** los que **contienen** el valor que se quiere olvidar (normalizado,
        como palabras completas: «M» no cierra «marzo»). Uno solo: se retira, con purga. Varios: no se toca y se
        pregunta cuál. Ninguno: devuelve False y queda el aviso de siempre. Comparte con R3 el limite de uno por turno.
        Devuelve True si lo ha resuelto el (cerrando uno o preguntando)."""
        buscado = normalizar(hecho["valor"])
        if turno["cierres_indirectos"] >= 1 or not buscado:
            return False
        patron = f" {buscado} "
        candidatos = [h for h in self._repo.hechos_con_nombres(user_id) if h["valor"]
                      and patron in f" {normalizar(h['valor'])} "]
        if not candidatos:
            return False
        if len(candidatos) > 1:
            opciones = "; ".join(f"«{c['valor']}» ({c['entidad']} · {c['atributo']})" for c in candidatos)
            self._repo.registrar_decision(user_id, "sin_cambio", self._senales(ent, attr, False, "retirar_valor_ambiguo"),
                                          f"regla=retirar_valor_ambiguo candidatos={len(candidatos)}")
            data["sin_cambio"].append(f"Hay varios datos que encajan con lo que quiere olvidar: {opciones}. ¿Cuál olvido?")
            return True
        h = candidatos[0]
        self._retirar(user_id, h["id"])
        self._repo.registrar_decision(user_id, "retirar", self._senales(ent, attr, False, "retirar_valor"),
                                      f"hecho={h['id']} regla=retirar_valor", hecho_id=h["id"])
        data["guardados"].append({"entidad": h["entidad"], "atributo": h["atributo"], "valor": h["valor"],
                                  "operacion": "retirar", "sustituye": None})
        turno["cierres_indirectos"] += 1
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

        from core.memoria.ajustes import propietario_vault, umbrales
        from core.memoria.catalogo import Catalogo
        from core.memoria.embedder import OpenAIEmbedder
        from core.memoria.extractor import Extractor
        from core.memoria.repositorio import RepositorioMemoria

        base = config["memory_collection"]   # D20: sin valor por defecto, que no caiga en produccion
        repo = RepositorioMemoria(db)
        embedder = OpenAIEmbedder(config["openai_apikey"])
        qdrant = QdrantClient(url=config.get("qdrant_url", "http://localhost:6333"))
        extractor = Extractor(anthropic.Anthropic(api_key=config["anthropic_apikey"]), on_usage=on_usage)
        return cls(repo, Catalogo(repo, embedder, qdrant, base), extractor, embedder, qdrant, base, umbrales(config),
                   vault_path=config.get("vault_docs_path"), propietario_vault=propietario_vault(config))
