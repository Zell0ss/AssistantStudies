# Comandos de Sebastian 2.0

Referencia rápida de todos los comandos disponibles por tipo de lista.

---

## 📊 Resumen del Sistema

Sebastian 2.0 gestiona 6 módulos:

1. **Inventory** - Múltiples inventarios nombrados (con cantidades y alertas de stock bajo)
2. **Shopping** - Listas de compra múltiples (con cantidades)
3. **Packing** - Listas de equipaje para viajes (con items recurrentes)
4. **Notes** - Notas de texto libre con tags
5. **Calendar** - Agenda personal con eventos recurrentes
6. **Tickets** - Entradas y códigos QR/barcode asociados a eventos

---

## 📋 Tabla Comparativa

| Tipo | Base de datos | Comandos disponibles | Características especiales |
|------|--------------|---------------------|---------------------------|
| **inventory** | `lists` + `list_items`<br>(category='inventory') | • `add` - "compré 6 aguacates"<br>• `set` - "me quedan 2 aguacates"<br>• `get` - "cuántos aguacates tengo"<br>• `remove` - "elimina aguacates"<br>• `list` - "qué tengo en despensa madrid"<br>• `check_low_stock` - "items con stock bajo" | • Cantidad + unidad + threshold<br>• Avisos ⚠️ cuando stock bajo<br>• **Múltiples inventarios nombrados**<br>• Smart defaults (auto-selección) |
| **shopping** | `lists`<br>(category='shopping') | • `create` - "crea lista mercadona"<br>• `add` - "añade 2 kg de pan a mercadona"<br>• `remove` - "elimina pan de mercadona"<br>• `list` - "lista de mercadona"<br>• `list_all_lists` - "qué listas tengo" | • Items con cantidad y unidad<br>• Se eliminan manualmente<br>• **Múltiples listas** (mercadona, carrefour, etc.)<br>• Smart defaults |
| **packing** | `lists`<br>(category='packing') | • `add` - "añade toalla a gijón"<br>• `add` (recurring) - "añade cepillo a gijón, siempre"<br>• `check` - "marca toalla en gijón"<br>• `list` - "lista equipaje gijón" | • Items + flag recurring 🔄<br>• Items recurrentes permanecen<br>• **Múltiples listas** (gijón, madrid, playa, etc.)<br>• Smart defaults |
| **notes** | `notes` | • `add` - "apunta que rebe prefiere X"<br>• `search` - "busca notas sobre rebe"<br>• `list` - "mis notas" | • Texto libre + tags<br>• Búsqueda por contenido y tags<br>• **Múltiples notas** |

---

## 🎯 Ejemplos de Uso

### 1. Inventory (Múltiples Inventarios Nombrados)

**Crear/usar inventarios nombrados:**
```
✅ "añade aguacates a despensa de madrid"
✅ "cuánto me queda en nevera de gijón"
✅ "lista de despensa magán"
✅ "qué tengo en mi inventario"  (smart default: auto-selecciona si tienes 1 solo)
```

**Añadir items con threshold:**
```
✅ "compré 6 aguacates"  (threshold por defecto: 2)
✅ "añadí 2 kilos de arroz a despensa madrid"
✅ "me llegaron 12 huevos en nevera gijón"
```

**Establecer cantidad exacta:**
```
✅ "me quedan 2 limones"
✅ "tengo 1 litro de leche en nevera gijón"
✅ "actualiza aguacates a 3 en despensa madrid"
```

**Consultar:**
```
✅ "cuántos aguacates tengo en despensa madrid?"
✅ "cuánta leche me queda?"
✅ "qué tengo en nevera de gijón?"
✅ "dime que cosas me queda poco"  (check low stock)
```

**Eliminar:**
```
✅ "elimina linterna de despensa madrid"
✅ "quita aguacates"
```

**Avisos de stock bajo:**
Cuando actualizas un item y cae por debajo del threshold, recibes un aviso:
```
"quita 5 aguacates" → "✅ Actualizado. ⚠️ Te queda poco aguacates (1 unidades). Piensa en comprar."
```

**Comportamiento especial:**
- Puedes tener múltiples inventarios: "despensa madrid", "nevera gijón", "despensa magán", etc.
- Threshold warnings automáticos (⚠️) cuando stock bajo - **ya no auto-añade a compra**
- Smart defaults: si solo tienes 1 inventario, no necesitas especificar el nombre
- Si tienes múltiples inventarios → debes especificar cuál: "despensa madrid", "nevera gijón", etc.
- Threshold por defecto: 2 unidades

---

### 2. Shopping (Listas de Compra con Cantidades)

**Crear listas:**
```
✅ "crea una lista que se llame mercadona"
✅ "crea lista carrefour"
✅ "nueva lista lidl"
```

**Añadir items CON cantidades:**
```
✅ "añade 5 aguacates a mercadona"
✅ "añade 2 kg de pan a la compra"
✅ "añade 3 litros de leche a carrefour"
✅ "añade tomates a mercadona"  (cantidad por defecto: 1)
```

**Ver listas:**
```
✅ "lista de mercadona"
✅ "qué tengo en la lista carrefour?"
✅ "qué listas de compra tengo?"
✅ "dime que listas tengo"
```

**Eliminar items:**
```
✅ "elimina pan de mercadona"
✅ "quita leche de carrefour"
```

**Smart defaults:**
- Si solo tienes 1 lista de compra → auto-selecciona (no necesitas especificar nombre)
- Si tienes múltiples → debes especificar: "mercadona", "carrefour", etc.

**Listas comunes:**
- `compra` - Lista por defecto (cuando dices "la compra")
- `mercadona`
- `carrefour`
- `lidl`
- O cualquier nombre que crees

---

### 3. Packing (Listas de Equipaje)

**Añadir items normales:**
```
✅ "añade toalla a gijón"
✅ "añade protector solar a playa"
```

**Añadir items recurrentes** (se mantienen siempre):
```
✅ "añade cepillo dental a gijón, siempre"
✅ "añade cargador a madrid, siempre"
```

**Marcar como empacado:**
```
✅ "marca toalla en gijón"
✅ "empaqué cepillo en madrid"
```

**Ver lista:**
```
✅ "lista equipaje gijón"
✅ "qué llevo a madrid?"
```

**Comportamiento especial:**
- Items normales: desaparecen al marcar como empacados
- Items recurrentes (con "siempre"): permanecen en la lista
- Útil para items que siempre llevas (cepillo, cargador, etc.)

---

### 4. Notes (Notas)

**Crear notas:**
```
✅ "apunta que rebe prefiere manzanas verdes"
✅ "nota: el wifi es password123"
✅ "recuerda que juan cumple el 15 de marzo"
```

**Buscar notas:**
```
✅ "busca notas sobre rebe"
✅ "busca notas de wifi"
✅ "qué notas tengo de juan?"
```

**Listar todas:**
```
✅ "mis notas"
✅ "lista de notas"
✅ "qué notas tengo?"
```

**Características:**
- Tags automáticos extraídos del contenido
- Búsqueda por palabras clave
- Texto libre (cualquier contenido)

---

## 🔧 Comandos Compartidos vs Específicos

### Comandos Comunes (todos los tipos)
- `add` - Añadir items/contenido
- `list` - Listar contenido de UNA lista

### Solo Inventory
- `set` - Establecer cantidad exacta (no suma, reemplaza)
- `get` - Consultar un item específico
- `remove` - Eliminar item del inventario
- ⚡ **Auto-trigger**: Añade automáticamente a shopping cuando bajo de threshold

### Solo Shopping
- `create` - Crear nueva lista vacía
- `list_all_lists` - Ver todas las listas de compra disponibles
- `bought` - Marcar como comprado (elimina el item)

### Solo Packing
- `check` - Marcar como empacado
- `recurring` flag - Items que siempre se mantienen en la lista

### Solo Notes
- `search` - Buscar notas por contenido o tags
- Tags automáticos del texto

---

## 🎨 Parser y Lenguaje Natural

Sebastian entiende español natural. No necesitas comandos exactos:

### Variaciones Aceptadas

**Para añadir:**
- "compré X"
- "añade X"
- "agregar X"
- "pon X"

**Para consultar:**
- "qué tengo?"
- "muéstrame"
- "lista"
- "dime qué hay"

**Para eliminar:**
- "elimina X"
- "quita X"
- "borra X"
- "saca X"

**El parser detecta automáticamente:**
1. El módulo (inventory, shopping, packing, notes)
2. La acción (add, remove, list, etc.)
3. Los parámetros (item, quantity, list_name, etc.)

---

## 💡 Tips de Uso

### 1. Inventory + Shopping Automático
```
# Tienes 8 aguacates (threshold=2)
"me quedan 1 aguacate"
# → Inventory actualizado
# → Aguacates añadidos automáticamente a "compra" (stock bajo)
```

### 2. Listas de Compra por Supermercado
```
"crea lista mercadona"
"crea lista carrefour"
"añade pan a mercadona"      # Pan solo en mercadona
"añade leche a carrefour"    # Leche solo en carrefour
"lista de mercadona"          # Solo items de mercadona
```

### 3. Items Recurrentes en Packing
```
"añade cepillo a gijón, siempre"  # Item recurrente
"marca cepillo en gijón"           # Lo marcas como empacado
# → Cepillo permanece para el próximo viaje
```

### 4. Notas con Tags Automáticos
```
"apunta que rebe prefiere manzanas verdes"
# Tags automáticos: ["rebe", "manzanas"]
"busca notas sobre rebe"
# → Encuentra la nota
```

---

## 🐛 Problemas Comunes

### "No entendí tu mensaje"
- El parser no reconoció la intención
- Intenta reformular con palabras más directas
- Ejemplos: "añade X", "lista Y", "cuántos Z tengo"

### "Acción desconocida"
- El comando no existe para ese tipo de lista
- Verifica la tabla de arriba para comandos disponibles

### "No tienes X en el inventario"
- El item no existe (para `get` o `set`)
- Primero añádelo con `add`

### Lista creada como tipo incorrecto
- Si mencionas ciudades → puede detectarse como packing
- Especifica: "crea lista de compra llamada X"

---

## 📁 Estructura de Base de Datos

### Tabla: `inventory`
```sql
user_id, item_name, quantity, unit, low_threshold, created_at, updated_at
```

### Tabla: `lists` (shopping + packing)
```sql
id, user_id, name, list_type ('shopping' | 'packing'), created_at
```

### Tabla: `list_items`
```sql
id, list_id, name, checked, recurring, created_at
```

### Tabla: `notes`
```sql
id, user_id, content, tags, created_at, updated_at
```

---

## 🔄 Estado Actual de tus Listas

Ejecuta este comando para ver tus listas:
```bash
mysql -u root sebastian_db -e "SELECT name, list_type FROM lists WHERE user_id='TU_USER_ID'"
```

O pregúntale a Sebastian:
```
"qué listas tengo?"              # Shopping lists
"qué tengo en mi inventario?"    # Inventory
"lista equipaje gijón"           # Packing list específica
"mis notas"                      # Notes
```

---

### 5. Calendar (Agenda Personal)

**Añadir eventos:**
```
✅ "apunta dentista el jueves a las 5"
✅ "el 15 de marzo es el cumpleaños de rebe"
✅ "cada lunes inglés a las 7 de la tarde"
✅ "inglés cada lunes y miércoles a las 7 hasta junio"
✅ "todos los días tengo medicación a las 8"
✅ "el día 1 de cada mes pago el alquiler"
```

**Ver agenda:**
```
✅ "qué tengo hoy"
✅ "qué tengo mañana"
✅ "agenda de esta semana"
✅ "qué tengo en marzo"
```

**Buscar y borrar:**
```
✅ "cuándo tengo dentista"
✅ "próxima reunión"
✅ "borra el dentista del jueves"
✅ "elimina el inglés"
```

**Reglas de recurrencia (`recurrence_rule`):**
| Sintaxis | Significado |
|----------|-------------|
| `daily` | Todos los días |
| `weekly:MON` | Cada lunes |
| `weekly:MON,WED` | Lunes y miércoles |
| `monthly:15` | Día 15 de cada mes |
| `monthly:first-TUE` | Primer martes del mes |

---

### 6. Tickets y Entradas

Los tickets (QR, códigos de barras, DataMatrix, Aztec, PDF417) se asocian a eventos del calendario.

**Guardar un ticket:**
```
1. Envía una foto con el código QR o barcode
2a. Si el mensaje tiene caption → lo busca como evento automáticamente
2b. Si no → te pregunta a qué evento asociarlo (lista numerada)
3. Responde con el número o el nombre del evento
```

**Ver tickets guardados:**
```
✅ "qué tickets tengo para el teatro"
✅ "las entradas del concierto del viernes"
✅ "los tickets del dentista"
✅ "dame el código del tren"
```

**Borrar tickets:**
```
✅ "borra los tickets del teatro"
✅ "elimina las entradas del concierto"
```

**Formatos soportados:**
| Tipo | Generación | Notas |
|------|-----------|-------|
| QR_CODE | qrcode | Alta calidad |
| CODE_128, CODE_39 | python-barcode | Lineal estándar |
| EAN_13, EAN_8, UPC_A, UPC_E | python-barcode | Con check digit |
| AZTEC | zxingcpp | Pixel-art 2D |
| DATA_MATRIX | zxingcpp | Cuadrícula 2D |
| PDF417 | zxingcpp | Barcode apilado |

**Notas:**
- Si una imagen tiene múltiples códigos (p.ej. DataMatrix + barcode), se detectan todos
- Para guardar solo un formato, recorta la imagen antes de enviarla
- Los tickets se almacenan en `events.notes` (JSON) en la BD
- Backward compat: tickets antiguos con `image_b64` siguen funcionando

---

## 🖥️ Dependencias del Sistema

### Python (`requirements.txt`)
Ver archivo `requirements.txt`. Las más importantes:
- `pyTelegramBotAPI` — bot framework
- `anthropic` — Claude Haiku parser
- `zxing-cpp` — decode/encode barcodes (primary)
- `pyzbar` — decode barcodes (fallback)
- `qrcode`, `python-barcode` — generación QR y barcodes lineales
- `numpy` — conversión zxingcpp.Image → PIL.Image
- `APScheduler` — recordatorio diario

### Sistema Unix (`apt`) — NO están en requirements.txt
Deben instalarse en el servidor:
```bash
sudo apt-get install libzbar0
```
- **`libzbar0`** — biblioteca nativa requerida por `pyzbar` para decodificar barcodes
  - Sin esto, `pyzbar` falla silenciosamente y solo funciona el fallback de texto
  - Verificar: `python -c "from pyzbar.pyzbar import decode; print('ok')"`

---

## 📁 Estructura de Base de Datos (completa)

### Tabla: `events`
```sql
id, user_id, title, event_date (DATE), start_datetime (DATETIME),
end_datetime (DATETIME), all_day (BOOL), recurrence_rule (VARCHAR),
recurrence_end (DATE), notes (JSON), created_at, updated_at
```
- `notes` JSON: `{"tickets": [{"type": "CODE_128", "value": "...", "value_b64": "..."}]}`

### Tabla: `lists`
```sql
id, user_id, name, list_category ('inventory'|'shopping'|'packing'), created_at
```

### Tabla: `list_items`
```sql
id, list_id, name, quantity, unit, low_threshold, checked, recurring, created_at
```

### Tabla: `notes`
```sql
id, user_id, content, tags (JSON), created_at, updated_at
```

### Tabla: `user_settings`
```sql
user_id, sprite_skin, created_at, updated_at
```

---

## 🚀 Migraciones

| Nº | Archivo | Qué hace |
|----|---------|----------|
| 001 | `001_initial.sql` | Tablas base (inventory, lists, list_items, notes) |
| 002 | `002_user_settings.sql` | Tabla user_settings (sprite skins) |
| 003 | `003_unify_lists.sql` | Unifica inventory en lists con list_category |
| 004 | `004_calendar.sql` | Tabla events para el calendario |
| 005 | `005_event_notes.sql` | Columna notes JSON en events (tickets) |

---

**Última actualización:** 2026-02-18
**Versión Sebastian:** 2.0 (Calendar + Tickets)
