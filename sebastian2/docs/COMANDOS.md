# Comandos de Sebastian 2.0

Referencia rápida de todos los comandos disponibles por tipo de lista.

---

## 📊 Resumen del Sistema

Sebastian 2.0 gestiona 4 tipos de listas diferentes:

1. **Inventory** - Inventario único de items en casa (con cantidades)
2. **Shopping** - Listas de compra múltiples (items simples)
3. **Packing** - Listas de equipaje para viajes (con items recurrentes)
4. **Notes** - Notas de texto libre con tags

---

## 📋 Tabla Comparativa

| Tipo | Base de datos | Comandos disponibles | Características especiales |
|------|--------------|---------------------|---------------------------|
| **inventory** | `inventory` | • `add` - "compré 6 aguacates"<br>• `set` - "me quedan 2 aguacates"<br>• `get` - "cuántos aguacates tengo"<br>• `remove` - "elimina aguacates"<br>• `list` - "qué tengo en inventario" | • Cantidad + unidad + threshold<br>• Auto-añade a shopping cuando bajo<br>• **1 lista única por usuario** |
| **shopping** | `lists`<br>(type='shopping') | • `create` - "crea lista bugs"<br>• `add` - "añade pan a mercadona"<br>• `remove` - "elimina pan de bugs"<br>• `bought` - "compré pan" (elimina)<br>• `list` - "lista de mercadona"<br>• `list_all_lists` - "qué listas tengo" | • Items simples (solo nombre)<br>• Se eliminan al marcar comprados<br>• **Múltiples listas** (mercadona, carrefour, etc.) |
| **packing** | `lists`<br>(type='packing') | • `add` - "añade toalla a gijón"<br>• `add` (recurring) - "añade cepillo a gijón, siempre"<br>• `check` - "marca toalla en gijón"<br>• `list` - "lista equipaje gijón"<br>• `reset` - reinicia items no-recurrentes | • Items + flag recurring<br>• Items recurrentes permanecen<br>• **Múltiples listas** (gijón, madrid, playa, etc.) |
| **notes** | `notes` | • `add` - "apunta que rebe prefiere X"<br>• `search` - "busca notas sobre rebe"<br>• `list` - "mis notas" | • Texto libre + tags<br>• Búsqueda por contenido y tags<br>• **Múltiples notas** |

---

## 🎯 Ejemplos de Uso

### 1. Inventory (Inventario Único)

**Añadir items:**
```
✅ "compré 6 aguacates"
✅ "añadí 2 kilos de arroz"
✅ "me llegaron 12 huevos"
```

**Establecer cantidad exacta:**
```
✅ "me quedan 2 limones"
✅ "tengo 1 litro de leche"
✅ "actualiza aguacates a 3"
```

**Consultar:**
```
✅ "cuántos aguacates tengo?"
✅ "cuánta leche me queda?"
✅ "qué tengo en mi inventario?"
```

**Eliminar:**
```
✅ "elimina linterna del inventario"
✅ "quita aguacates"
```

**Comportamiento especial:**
- Cuando un item cae por debajo del `threshold` → se añade automáticamente a la lista "compra"
- Threshold por defecto: 2 unidades

---

### 2. Shopping (Listas de Compra)

**Crear listas:**
```
✅ "crea una lista que se llame mercadona"
✅ "crea lista carrefour"
✅ "nueva lista lidl"
```

**Añadir items:**
```
✅ "añade pan a mercadona"
✅ "añade leche a carrefour"
✅ "añade tomates a la compra"
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
✅ "elimina bugs de la lista bugs"
```

**Marcar como comprado:**
```
✅ "compré pan"
✅ "ya compré leche"
```

**Listas comunes:**
- `compra` - Lista por defecto (cuando no especificas)
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

**Última actualización:** 2026-02-16
**Versión Sebastian:** 2.0
