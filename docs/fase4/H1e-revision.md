# H1e — revisión (fase 4, parche D70)

> Responde a: 898ee44 (H1e-informe). 2026-11-20, arquitecto. Revisado contra `fcf5494..898ee44` y la suite.

**Veredicto: aprobado. Josem lo despliega.**

- **R13:** `valor_encaja` es pura y usa el patrón del encargo. Se aplica solo a lo **reutilizado**, y nunca a `retirar`. La señal `tipo_no_encaja` no lleva el valor, y la prueba lo comprueba. El caso de producción por alias va a `nota`, y la corrección legítima sigue sustituyendo. Bien.
- **Retoques de H1d:**
  - R12 ya no se aplica a `retirar`, y la 5 lo prueba;
  - los trozos vacíos se descartan;
  - el espacio está arreglado.
- **Suite:** la he ejecutado yo: **1155 pasan**. `main` (`4c044fc`) es ancestro de `fase-4`.
- **Gasto:** 0 $.
- **Los dos límites que señalas los acepto:**
  - el patrón de `numero` mira la forma y no el significado, así que «1234 ABC» pasa por número;
  - un atributo `varios` de tipo numero que recibe un texto lo añade igual.

  El caso de producción queda cubierto. Si alguno aparece en `mem_decisiones` (`tipo_no_encaja`), se mira entonces (D70, indicador).

**Cómo se reparan los datos de Josem.** Hoy, `telegram_id` vale el usuario.
1. «Corrige: mi id de Telegram es <número>». Entra por alias, el valor encaja, y sustituye al usuario.
2. «Mi usuario de Telegram es @…». Entra por alias, el valor no encaja, y va a `nota` sin pisar el id.

## Para el programador

Responde a: 898ee44 (H1e-informe)

H1e aprobado. Para hasta que te escriba: H2, después de unos días de uso de la vigilancia.
