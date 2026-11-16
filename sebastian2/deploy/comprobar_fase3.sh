#!/bin/bash
# Fase 3 (prospectiva: compromisos, resumen de las 08:00 y avisos: D45-D52) — comprobación de SOLO LECTURA tras el despliegue
# de PASOS-CON-SUDO.md, sección «Fase 3». No escribe en ninguna BD ni en Qdrant, no toca unidades ni ficheros, no usa sudo,
# no llama a ninguna API de pago y NO manda nada por Telegram (la prueba seca solo CONSTRUYE el resumen, no lo envía).
# No imprime el texto de ningún compromiso (D52): solo cuentas. Con MOSTRAR=1 enseña el resumen de la prueba seca en tu terminal.
#
# Uso:  bash deploy/comprobar_fase3.sh            (después de reiniciar sebastian.service)
#       FECHA=2026-12-14 bash deploy/comprobar_fase3.sh      (la prueba seca con otro día; por defecto, mañana)
# Sale con 0 si todo está bien y con 1 si algo falla. Cada comprobación imprime OK / FALLO.

RAIZ="${RAIZ:-/data/AssistantStudies/sebastian2}"
PY="$RAIZ/.venv/bin/python"
BD="${BD:-sebastian_db}"          # solo para ensayar los apartados 4 y 5 contra sebastian_test; en el despliegue, no se toca
FALLOS=0

ok()    { echo "  OK     $1"; }
fallo() { echo "  FALLO  $1"; FALLOS=$((FALLOS + 1)); }

echo "1. El código desplegado es el de la fase 3 (main)"
rama=$(git -C "$RAIZ/.." rev-parse --abbrev-ref HEAD 2>/dev/null)
if [ "$rama" = "main" ]; then ok "producción está en main"; else fallo "producción no está en main (está en '$rama')"; fi
for f in modules/compromisos.py core/tools/compromisos_tools.py db/migrations/013_compromisos.sql; do
    if [ -e "$RAIZ/$f" ]; then ok "$f existe"; else fallo "falta $f: ¿se hizo el merge de fase-3?"; fi
done

echo "2. Las dos unidades siguen fijando la BD de producción (systemctl show)"
for u in sebastian.service cuaderno.service; do
    entorno=$(systemctl show -p Environment --value "$u")
    if grep -qw -- "SEBASTIAN_DB_NAME=sebastian_db" <<<"$entorno"; then ok "$u lleva SEBASTIAN_DB_NAME=sebastian_db"; else fallo "$u NO lleva SEBASTIAN_DB_NAME=sebastian_db"; fi
done

echo "3. El bot arrancó con la fase 3: BD de producción y planificador con avisos (LogCentral, desde el reinicio)"
desde_local=$(systemctl show -p ActiveEnterTimestamp --value sebastian.service)
desde_utc=$(date -u -d "$desde_local" +%Y-%m-%dT%H:%M:%S 2>/dev/null)
ultima_linea() {   # ultima_linea <texto a buscar>: el último mensaje desde el arranque que lo contiene
    logcentral query --source sebastian --grep "$1" 2>/dev/null | "$PY" -c "
import sys, json
desde = sys.argv[1]
ultima = None
for l in sys.stdin:
    try: r = json.loads(l)
    except ValueError: continue
    if r.get('timestamp', '') >= desde: ultima = r['message']
print(ultima or '')" "$desde_utc"
}
if [ -z "$desde_utc" ]; then
    fallo "sebastian.service no tiene hora de arranque (¿no está activo?)"
else
    linea=$(ultima_linea "Escribiendo en BD")
    if [ -z "$linea" ]; then
        fallo "no hay línea «Escribiendo en BD» desde el arranque ($desde_utc UTC): ¿se reinició con el código nuevo?"
    elif grep -q "BD=sebastian_db " <<<"$linea"; then ok "$linea"; else fallo "la línea de arranque dice otra cosa: $linea"; fi
    linea=$(ultima_linea "Planificador arrancado")
    if [ -z "$linea" ]; then
        fallo "no hay línea «Planificador arrancado» desde el arranque: el planificador de la fase 3 no se ha iniciado"
    elif grep -q "avisos cada minuto" <<<"$linea"; then ok "$linea"; else fallo "el planificador arrancó sin los avisos de compromisos: $linea"; fi
fi

echo "4. sebastian_db: tabla compromisos y sus columnas (solo SELECT; sin textos, D52)"
# El config.yaml apunta a desarrollo (D19): la BD de producción se nombra aquí, explícita, y solo se lee.
"$PY" - "$RAIZ" "$BD" <<'PYEOF'
import sys, yaml, pymysql
raiz, bd = sys.argv[1], sys.argv[2]
c = yaml.safe_load(open(f"{raiz}/config.yaml"))["mariadb"]
con = pymysql.connect(host=c["host"], port=c["port"], user=c["user"], password=c["password"], database=bd)
mal = False
try:
    cur = con.cursor()
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = 'compromisos'", (bd,))
    columnas = {f[0] for f in cur.fetchall()}
    necesarias = {"id", "user_id", "texto", "evento_id", "fecha_inicio", "fecha_fin", "dias_inicio", "dias_fin", "hora", "minutos",
                  "estado", "aviso_para", "created_at", "updated_at"}
    if not columnas:
        print("  FALLO  sebastian_db no tiene la tabla compromisos: aplica db/migrations/013_compromisos.sql (paso 1)"); mal = True
    elif necesarias - columnas:
        print(f"  FALLO  a compromisos le faltan columnas: {sorted(necesarias - columnas)}"); mal = True
    else:
        print(f"  OK     compromisos existe, con sus {len(necesarias)} columnas (migración 013)")
        cur.execute("SELECT estado, COUNT(*) FROM compromisos GROUP BY estado")
        cuentas = dict(cur.fetchall())
        print("  OK     compromisos por estado: " + (", ".join(f"{k}={v}" for k, v in sorted(cuentas.items())) or "ninguno todavía"))
        cur.execute("SELECT COUNT(*) FROM compromisos c LEFT JOIN events e ON e.id = c.evento_id"
                    " WHERE c.evento_id IS NOT NULL AND e.id IS NULL")
        if cur.fetchone()[0] == 0:
            print("  OK     ningún compromiso apunta a un evento que no existe")
        else:
            print("  FALLO  hay compromisos atados a un evento inexistente"); mal = True
finally:
    con.close()
sys.exit(1 if mal else 0)
PYEOF
[ $? -eq 0 ] || FALLOS=$((FALLOS + 1))

echo "5. Prueba seca de armar_resumen con la fecha de mañana, contra sebastian_db (construye el texto; NO lo envía)"
FECHA="${FECHA:-$(date -d tomorrow +%Y-%m-%d)}"
(cd "$RAIZ" && SEBASTIAN_DB_NAME="$BD" MOSTRAR="${MOSTRAR:-}" "$PY" - "$FECHA" "$BD" <<'PYEOF'
import os, sys
from datetime import datetime, time
from db.connection import init_pool
from utils.config import get_config
from bot.scheduler import armar_resumen

cfg = get_config()
if cfg["mariadb"]["database"] != sys.argv[2]:
    print(f"  FALLO  la prueba seca iba a leer {cfg['mariadb']['database']} y no {sys.argv[2]}"); sys.exit(1)
ids = cfg.get("authorized_ids") or []
if not ids:
    print("  FALLO  config.yaml no tiene authorized_ids: no sé para quién armar el resumen"); sys.exit(1)
ahora = datetime.combine(datetime.strptime(sys.argv[1], "%Y-%m-%d").date(), time(8, 0))
conn = init_pool().connection()
try:
    texto = armar_resumen(str(ids[0]), ahora, conn=conn)
finally:
    conn.close()
if texto is None:
    print(f"  OK     armar_resumen para {ahora:%Y-%m-%d} no tiene nada que decir (devuelve None: no se mandaría nada)")
else:
    viñetas = sum(1 for l in texto.splitlines() if l.startswith("•"))
    print(f"  OK     armar_resumen para {ahora:%Y-%m-%d} arma un resumen de {len(texto.splitlines())} líneas, {viñetas} viñeta(s)")
    if os.environ.get("MOSTRAR") == "1":
        print("\n" + texto + "\n")
PYEOF
) || FALLOS=$((FALLOS + 1))

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
