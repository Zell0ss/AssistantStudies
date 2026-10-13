#!/bin/bash
# Fase 1 (D19, D20, D25) — comprobación de SOLO LECTURA tras el despliegue de PASOS-CON-SUDO.md.
# No escribe en ninguna BD, ni en Qdrant, ni toca unidades ni ficheros. No usa sudo.
#
# Uso:  bash deploy/comprobar_fase1.sh            (después de reiniciar sebastian.service)
# Sale con 0 si todo está bien y con 1 si algo falla. Cada comprobación imprime OK / FALLO.

RAIZ="${RAIZ:-/data/AssistantStudies/sebastian2}"
PY="$RAIZ/.venv/bin/python"
UNIDADES="sebastian.service cuaderno.service"
FALLOS=0

ok()    { echo "  OK     $1"; }
fallo() { echo "  FALLO  $1"; FALLOS=$((FALLOS + 1)); }

echo "1. Las dos unidades fijan las dos variables (systemctl show)"
for u in $UNIDADES; do
    entorno=$(systemctl show -p Environment --value "$u")
    for v in "SEBASTIAN_DB_NAME=sebastian_db" "SEBASTIAN_MEMORY_COLLECTION=sebastian_memory"; do
        if grep -qw -- "$v" <<<"$entorno"; then ok "$u lleva $v"; else fallo "$u NO lleva $v"; fi
    done
done

echo "2. La línea de arranque del bot dice sebastian_db / sebastian_memory (LogCentral)"
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

echo "3. sebastian_dev existe y tiene las tablas de las migraciones (las de sebastian_test)"
"$PY" - "$RAIZ" <<'PYEOF'
import sys, yaml, pymysql
raiz = sys.argv[1]
c = yaml.safe_load(open(f"{raiz}/config.yaml"))["mariadb"]
def tablas(bd):
    con = pymysql.connect(host=c["host"], port=c["port"], user=c["user"], password=c["password"])
    try:
        cur = con.cursor()
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = %s", (bd,))
        return {f[0] for f in cur.fetchall()}
    finally:
        con.close()
dev, test, prod = tablas("sebastian_dev"), tablas("sebastian_test"), tablas("sebastian_db")
mal = False
if not dev:
    print("  FALLO  sebastian_dev no existe o está vacía"); mal = True
else:
    faltan = sorted(test - dev)
    if faltan:
        print(f"  FALLO  a sebastian_dev le faltan tablas que sí tiene sebastian_test: {faltan}"); mal = True
    else:
        print(f"  OK     sebastian_dev tiene {len(dev)} tablas (todas las de sebastian_test)")
# El historial (D21) escribe en la BD que fijan las unidades, o sea en producción: tiene que
# tener `conversations` (migración 007) o el bot lo ignorará con un warning (D22).
if "conversations" in prod:
    print("  OK     sebastian_db tiene la tabla conversations (historial entre turnos)")
else:
    print("  FALLO  sebastian_db NO tiene la tabla conversations: aplica db/migrations/007_conversations.sql"); mal = True
sys.exit(1 if mal else 0)
PYEOF
[ $? -eq 0 ] || FALLOS=$((FALLOS + 1))

echo "4. La colección sebastian_memory_dev existe en Qdrant (1536, Cosine)"
dim=$(curl -s --max-time 5 localhost:6333/collections/sebastian_memory_dev | "$PY" -c "
import sys, json
try:
    v = json.load(sys.stdin)['result']['config']['params']['vectors']
    print(f\"{v['size']} {v['distance']}\")
except Exception:
    print('')")
if [ "$dim" = "1536 Cosine" ]; then ok "sebastian_memory_dev: $dim"; else fallo "sebastian_memory_dev no existe o no es 1536/Cosine (leído: '${dim}')"; fi

echo "5. config.yaml ya no menciona sebastian_db y apunta a dev"
if grep -q "sebastian_db" "$RAIZ/config.yaml"; then fallo "config.yaml todavía menciona sebastian_db"; else ok "config.yaml no menciona sebastian_db"; fi
if grep -qE "^\s*database:\s*[\"']?sebastian_dev" "$RAIZ/config.yaml" \
   && grep -qE "^memory_collection:\s*[\"']?sebastian_memory_dev" "$RAIZ/config.yaml"; then
    ok "config.yaml: database=sebastian_dev, memory_collection=sebastian_memory_dev"
else
    fallo "config.yaml no tiene database: sebastian_dev y memory_collection: sebastian_memory_dev"
fi

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
