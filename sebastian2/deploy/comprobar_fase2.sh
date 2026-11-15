#!/bin/bash
# Fase 2 (memoria v1: D31-D43) — comprobación de SOLO LECTURA tras el despliegue de PASOS-CON-SUDO.md, sección «Fase 2».
# No escribe en ninguna BD ni en Qdrant, no toca unidades ni ficheros y no usa sudo. No llama a ninguna API de pago.
#
# Uso:  bash deploy/comprobar_fase2.sh            (después de reiniciar sebastian.service)
# Sale con 0 si todo está bien y con 1 si algo falla. Cada comprobación imprime OK / FALLO.

RAIZ="${RAIZ:-/data/AssistantStudies/sebastian2}"
PY="$RAIZ/.venv/bin/python"
UNIDADES="sebastian.service cuaderno.service"
FALLOS=0

ok()    { echo "  OK     $1"; }
fallo() { echo "  FALLO  $1"; FALLOS=$((FALLOS + 1)); }

echo "1. El código desplegado es el de la fase 2 (main), sin el módulo de memoria de Sprint 3"
rama=$(git -C "$RAIZ/.." rev-parse --abbrev-ref HEAD 2>/dev/null)
if [ "$rama" = "main" ]; then ok "producción está en main"; else fallo "producción no está en main (está en '$rama')"; fi
if [ -d "$RAIZ/core/memoria" ]; then ok "core/memoria existe"; else fallo "falta core/memoria: ¿se hizo el merge?"; fi
if [ ! -e "$RAIZ/modules/memory.py" ]; then ok "modules/memory.py ya no existe"; else fallo "modules/memory.py sigue en producción"; fi

echo "2. Las dos unidades siguen fijando BD y colección de producción (systemctl show)"
for u in $UNIDADES; do
    entorno=$(systemctl show -p Environment --value "$u")
    for v in "SEBASTIAN_DB_NAME=sebastian_db" "SEBASTIAN_MEMORY_COLLECTION=sebastian_memory"; do
        if grep -qw -- "$v" <<<"$entorno"; then ok "$u lleva $v"; else fallo "$u NO lleva $v"; fi
    done
done

echo "3. La línea de arranque del bot dice sebastian_db / sebastian_memory (LogCentral)"
desde_local=$(systemctl show -p ActiveEnterTimestamp --value sebastian.service)
desde_utc=$(date -u -d "$desde_local" +%Y-%m-%dT%H:%M:%S 2>/dev/null)
if [ -z "$desde_utc" ]; then
    fallo "sebastian.service no tiene hora de arranque (¿no está activo?)"
else
    linea=$(logcentral query --source sebastian --grep "Escribiendo en BD" 2>/dev/null | \
        "$PY" -c "
import sys, json
desde = sys.argv[1]
ultima = None
for l in sys.stdin:
    try: r = json.loads(l)
    except ValueError: continue
    if r.get('timestamp', '') >= desde: ultima = r['message']
print(ultima or '')" "$desde_utc")
    if [ -z "$linea" ]; then
        fallo "no hay línea «Escribiendo en BD» desde el arranque ($desde_utc UTC): ¿se reinició con el código nuevo?"
    elif grep -q "BD=sebastian_db " <<<"$linea" && grep -q "memory_collection=sebastian_memory\$" <<<"$linea"; then
        ok "$linea"
    else
        fallo "la línea de arranque dice otra cosa: $linea"
    fi
fi

echo "4. sebastian_db: tablas de la memoria, columna fuente_id, semillas y hechos migrados (solo SELECT)"
"$PY" - "$RAIZ" <<'PYEOF'
import sys, yaml, pymysql
raiz = sys.argv[1]
cfg = yaml.safe_load(open(f"{raiz}/config.yaml"))
c = cfg["mariadb"]
# El config.yaml apunta a desarrollo (D19): la BD de producción se nombra aquí, explícita, y solo se lee.
con = pymysql.connect(host=c["host"], port=c["port"], user=c["user"], password=c["password"], database="sebastian_db")
mal = False
try:
    cur = con.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'sebastian_db'")
    tablas = {f[0] for f in cur.fetchall()}
    necesarias = ["mem_entidades", "mem_entidad_alias", "mem_atributos", "mem_atributo_alias", "mem_hechos",
                  "mem_decisiones", "mem_fuentes"]
    faltan = [t for t in necesarias if t not in tablas]
    if faltan:
        print(f"  FALLO  a sebastian_db le faltan tablas: {faltan} (migraciones 010, 011 y 012)"); mal = True
    else:
        print(f"  OK     sebastian_db tiene las {len(necesarias)} tablas de la memoria (incluida mem_fuentes)")
    cur.execute("SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'sebastian_db'"
                " AND table_name = 'mem_hechos' AND column_name = 'fuente_id'")
    if cur.fetchone()[0] == 1:
        print("  OK     mem_hechos.fuente_id existe (D41)")
    else:
        print("  FALLO  mem_hechos no tiene fuente_id: aplica db/migrations/012_memoria_fuentes.sql"); mal = True
    if not faltan:
        cur.execute("SELECT nombre FROM mem_atributos WHERE estado = 'activo'")
        activos = {f[0] for f in cur.fetchall()}
        semillas = {"nota", "alergia", "cumpleanos", "parentesco", "preferencia", "estado", "host", "stack", "repo", "db"}
        if semillas <= activos:
            print(f"  OK     los {len(semillas)} atributos semilla están activos")
        else:
            print(f"  FALLO  faltan semillas activas: {sorted(semillas - activos)} (migración 011)"); mal = True
        propietario = str((cfg.get("memoria") or {}).get("propietario_vault") or cfg.get("cuaderno_chat_id") or "")
        cur.execute("SELECT a.nombre FROM mem_hechos h JOIN mem_atributos a ON a.id = h.atributo_id"
                    " WHERE h.origen = 'migracion' AND h.user_id = %s", (propietario,))
        migrados = sorted(f[0] for f in cur.fetchall())
        if migrados == ["alergia", "nota", "presion_neumaticos"]:
            print("  OK     los 3 hechos de Sprint 3 están migrados (alergia, nota, presion_neumaticos)")
        else:
            print(f"  FALLO  hechos migrados del propietario: {migrados} (se esperaban alergia, nota, presion_neumaticos): "
                  "migrar_sprint3.py"); mal = True
        cur.execute("SELECT COUNT(*) FROM mem_hechos WHERE user_id = %s AND valid_to IS NULL AND valor <> ''", (propietario,))
        if cur.fetchone()[0] >= 1:
            print("  OK     el propietario tiene hechos vigentes: el cuaderno tiene de dónde sacar su semilla")
        else:
            print("  FALLO  el propietario no tiene ningún hecho vigente"); mal = True
finally:
    con.close()
sys.exit(1 if mal else 0)
PYEOF
[ $? -eq 0 ] || FALLOS=$((FALLOS + 1))

echo "5. Qdrant: sebastian_memory_catalogo y sebastian_memory_notas (1536, Cosine); la colección de Sprint 3 sigue ahí"
for col in sebastian_memory_catalogo sebastian_memory_notas; do
    dim=$(curl -s --max-time 5 "localhost:6333/collections/$col" | "$PY" -c "
import sys, json
try:
    v = json.load(sys.stdin)['result']['config']['params']['vectors']
    print(f\"{v['size']} {v['distance']}\")
except Exception:
    print('')")
    if [ "$dim" = "1536 Cosine" ]; then ok "$col: $dim"; else fallo "$col no existe o no es 1536/Cosine (leído: '${dim}'): crear_colecciones.py --produccion"; fi
done
puntos=$(curl -s --max-time 5 "localhost:6333/collections/sebastian_memory_catalogo" | "$PY" -c "
import sys, json
try: print(json.load(sys.stdin)['result']['points_count'])
except Exception: print(0)")
if [ "${puntos:-0}" -ge 11 ]; then ok "sebastian_memory_catalogo tiene $puntos puntos (atributos y entidades indexados)"; else fallo "sebastian_memory_catalogo tiene ${puntos:-0} puntos: falta indexar_catalogo.py --produccion"; fi
antigua=$(curl -s --max-time 5 "localhost:6333/collections/sebastian_memory" | "$PY" -c "
import sys, json
try: print(json.load(sys.stdin)['result']['points_count'])
except Exception: print('')")
if [ -n "$antigua" ]; then ok "sebastian_memory (Sprint 3) sigue con $antigua puntos: no se borra en esta fase (D18)"; else fallo "sebastian_memory ya no existe: no se borra en esta fase"; fi

echo "6. Sin errores en LogCentral desde el reinicio"
if [ -n "$desde_utc" ]; then
    n=$(logcentral query --source sebastian,cuaderno --level error,critical 2>/dev/null | \
        "$PY" -c "
import sys, json
desde = sys.argv[1]
print(sum(1 for l in sys.stdin if l.strip() and json.loads(l).get('timestamp', '') >= desde))" "$desde_utc")
    if [ "$n" = "0" ]; then ok "0 errores desde $desde_utc UTC"; else fallo "$n errores desde $desde_utc UTC: logcentral query --source sebastian --level error"; fi
else
    fallo "no se puede comprobar: sebastian.service no tiene hora de arranque"
fi

echo
if [ "$FALLOS" -eq 0 ]; then echo "Todo bien."; else echo "$FALLOS comprobación(es) con FALLO."; exit 1; fi
