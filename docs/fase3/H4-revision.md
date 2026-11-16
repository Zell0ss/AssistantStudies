# H4 — revisión (fase 3): preparación del despliegue

> Responde a: f6623e7 (H4-informe). 2026-11-16, arquitecto. La revisé contra el código en `9f529e7`.

**Veredicto: aprobado. Listo para que Josem despliegue.**

## 1. Lo que comprobé

- **Pruebas sin API:** `pytest -m "not golden"` da **851 en verde**.
- **R13:**
  - Solo compara pendientes del mismo usuario y del mismo evento, con el texto normalizado.
  - En el log van los ids, nunca el texto.
  - El compromiso repetido vuelve en su sitio del lote, con su momento ya calculado.
  - La línea `existente.update(texto=…, estado="pendiente")` no cambia nada y sobra. Bórrala si
    vuelves a tocar el fichero; no hace falta otra vuelta.
- **`comprobar_fase3.sh`:**
  - Ni `INSERT`, ni `UPDATE`, ni `DELETE`, ni `sudo`.
  - No manda nada a Telegram.
- **Los pasos:**
  - El orden es el correcto: copia, migración, `ff-only`, reinicio y comprobación.
  - La vuelta atrás está bien, y el `DROP` no se lanza sin preguntar.
  - El aviso sobre la FK con el código viejo está bien visto.
- **`ff-only` posible:** `main` está en `b4c426d`, que es antecesor de `fase-3`.

## 2. Decisiones que pedías

| # | Decisión |
|---|---|
| 1 | **La fase 2 sí está desplegada.** Está en producción desde el 15/11 (`main` = `b4c426d`) y Josem la probó por Telegram. Tu `TOMORROW.md` estaba atrasado. El paso 0 lo vuelve a comprobar de todos modos |
| 2 | Los pasos son de Josem |
| 3 | La pregunta de D52 a Tristras es mía y queda en mi lista |
| 4 | **Vale `exists` para el lote entero.** Es coherente con R3. Que dos iguales en una misma llamada se creen los dos lo acepto en esta fase |

## 3. Un cambio en la prueba real (paso 5.3)

**No muevas la cita de verdad** para probar R13. Si Josem la mueve y la devuelve a su fecha, hay
dos oportunidades de error sobre la preparación real, y eso a tres semanas de la prueba.

R13 se prueba con una cita inventada:
1. Crear una cita de prueba con dos pasos.
2. Moverla.
3. Mirar que los pasos no se duplican.
4. Borrarla. Borrar la cita cancela sus pasos.

Lo cambio yo al acompañar a Josem. No hace falta tocar el fichero.

## 4. Gasto

**0 $ en H4.** La fase queda en ≈ 9,59 $ de los 10 $ autorizados.

## Para el programador

Responde a: f6623e7 (H4-informe)

H4 aprobado. Nada más que hacer en código. Actualiza `TOMORROW.md`: la fase 2 está en producción
y la fase 3 espera el despliegue de Josem. **Para** aquí hasta que el arquitecto te escriba
después del despliegue.
