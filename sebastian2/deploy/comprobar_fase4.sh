#!/bin/bash
# Fase 4 (vigilancias: Sebastian busca por ti cada mañana: D63-D67) — comprobación de SOLO LECTURA tras el despliegue de
# PASOS-CON-SUDO.md, sección «Fase 4». No escribe en ninguna BD, no toca unidades ni ficheros, no usa sudo, no llama a ninguna API
# (ni a Wallapop ni a ninguna de pago) y NO manda nada por Telegram.
# No imprime consultas, reglas, títulos ni texto de anuncios (D42): solo cuentas, horas y fechas.
#
# Uso:  bash deploy/comprobar_fase4.sh            (después de reiniciar sebastian.service)
# Sale con 0 si todo está bien y con 1 si algo falla. Cada comprobación imprime OK / FALLO.

RAIZ="${RAIZ:-/data/AssistantStudies/sebastian2}"
PY="$RAIZ/.venv/bin/python"
BD="${BD:-sebastian_db}"          # solo para ensayar el apartado 4 contra sebastian_test; en el despliegue, no se toca
FALLOS=0

ok()    { echo "  OK     $1"; }
fallo() { echo "  FALLO  $1"; FALLOS=$((FALLOS + 1)); }

echo "1. El código desplegado es el de la fase 4 (main)"
rama=$(git -C "$RAIZ/.." rev-parse --abbrev-ref HEAD 2>/dev/null)
if [ "$rama" = "main" ]; then ok "producción está en main"; else fallo "producción no está en main (está en '$rama')"; fi
for f in modules/vigilancias/ronda.py modules/vigilancias/juez.py scripts/vigilancias/cargar.py db/migrations/014_vigilancias.sql; do
    if [ -e "$RAIZ/$f" ]; then ok "$f existe"; else fallo "falta $f: ¿se hizo el merge de fase-4?"; fi
done

echo "2. Las dos unidades siguen fijando la BD de producción (systemctl show)"
for u in sebastian.service cuaderno.service; do
    entorno=$(systemctl show -p Environment --value "$u")
    if grep -qw -- "SEBASTIAN_DB_NAME=sebastian_db" <<<"$entorno"; then ok "$u lleva SEBASTIAN_DB_NAME=sebastian_db"; else fallo "$u NO lleva SEBASTIAN_DB_NAME=sebastian_db"; fi
done

echo "3. El bot arrancó con la fase 4: BD de producción y planificador con las vigilancias (LogCentral, desde el reinicio)"
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
        fallo "no hay línea «Planificador arrancado» desde el arranque: el planificador no se ha iniciado después del reinicio"
    elif grep -q "vigilancias cada 15 min" <<<"$linea"; then ok "$linea"; else fallo "el planificador arrancó sin las vigilancias (¿código de la fase 3?): $linea"; fi
fi

echo "4. $BD: tablas vigilancias y vigilancia_vistos, y la vigilancia de Josem activa y con hora (solo SELECT; sin consultas ni reglas, D42)"
# El config.yaml apunta a desarrollo (D19): la BD de producción se nombra aquí, explícita, y solo se lee.
"$PY" - "$RAIZ" "$BD" <<'PYEOF'
import sys, yaml, pymysql
from datetime import datetime
raiz, bd = sys.argv[1], sys.argv[2]
c = yaml.safe_load(open(f"{raiz}/config.yaml"))["mariadb"]
con = pymysql.connect(host=c["host"], port=c["port"], user=c["user"], password=c["password"], database=bd)
mal = False
NECESARIAS = {
    "vigilancias": {"id", "user_id", "nombre", "fuente", "consultas", "filtros", "reglas", "hora", "activa", "ultima_ronda",
                    "aviso_fallo", "created_at", "updated_at"},
    "vigilancia_vistos": {"vigilancia_id", "anuncio_id", "precio", "firma", "modificado", "visto_en"},
}
try:
    cur = con.cursor()
    for tabla, necesarias in NECESARIAS.items():
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = %s AND table_name = %s", (bd, tabla))
        columnas = {f[0] for f in cur.fetchall()}
        if not columnas:
            print(f"  FALLO  {bd} no tiene la tabla {tabla}: aplica db/migrations/014_vigilancias.sql (paso 1)"); mal = True
        elif necesarias - columnas:
            print(f"  FALLO  a {tabla} le faltan columnas: {sorted(necesarias - columnas)}"); mal = True
        else:
            print(f"  OK     {tabla} existe, con sus {len(necesarias)} columnas (migración 014)")
    if not mal:
        cur.execute("SELECT id, user_id, fuente, activa, hora, ultima_ronda, aviso_fallo, JSON_LENGTH(consultas) FROM vigilancias ORDER BY id")
        filas = cur.fetchall()
        activas = [f for f in filas if f[3]]
        if not activas:
            print("  FALLO  no hay ninguna vigilancia activa: ¿falta el paso 3 (cargar el YAML)?"); mal = True
        for id_, user, fuente, activa, hora, ultima, aviso, consultas in activas:
            print(f"  OK     vigilancia id={id_} user={user} fuente={fuente} activa, hora={(datetime.min + hora).strftime('%H:%M')}, "
                  f"{consultas} consulta(s), última ronda={ultima or 'ninguna todavía'}, aviso de fallo={aviso or 'ninguno'}")
        cur.execute("SELECT COUNT(*) FROM vigilancia_vistos")
        print(f"  OK     vigilancia_vistos tiene {cur.fetchone()[0]} anuncio(s) visto(s)")
finally:
    con.close()
sys.exit(1 if mal else 0)
PYEOF
[ $? -eq 0 ] || FALLOS=$((FALLOS + 1))

echo "5. Rondas desde el reinicio (LogCentral; solo cuentas: la primera ronda sale a la hora de la vigilancia)"
if [ -n "$desde_utc" ]; then
    logcentral query --source sebastian --grep "Vigilancia id=" 2>/dev/null | "$PY" -c "
import sys, json, re
from collections import Counter
desde = sys.argv[1]
cuentas = Counter()
for l in sys.stdin:
    try: r = json.loads(l)
    except ValueError: continue
    if r.get('timestamp', '') < desde: continue
    m = re.search(r'resultado=(\w+)', r.get('message', ''))
    if m: cuentas[m.group(1)] += 1
if cuentas:
    print('  OK     rondas desde el reinicio: ' + ', '.join(f'{k}={v}' for k, v in sorted(cuentas.items())))
else:
    print('  OK     todavía no ha habido ninguna ronda (normal si aún no es la hora de la vigilancia)')" "$desde_utc"
else
    fallo "no se puede comprobar: sebastian.service no tiene hora de arranque"
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
