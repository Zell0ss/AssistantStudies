# H3 (fase 1) — Revisión del arquitecto

Responde a: 38f3499 (H3-informe)

**Veredicto: aprobado.** Listo para que Josem despliegue con `sebastian2/deploy/PASOS-CON-SUDO.md`
§«Fase 1».

## 1. Comprobado

- **R4 y R5:** `f5a2437` y `d6d2bd2`. Los dos tests de lado vacío hacen lo que pedía H2-revision
  §2.2.
- **Unidades del repo frente a las instaladas:** quitando las líneas `Environment=` y su
  comentario, `diff` no da nada. El `cp` del paso 3 solo añade las dos variables. Correcto.
- **El orden de los pasos es el del PLAN §4.** Las variables (paso 3) van antes del merge
  (paso 4), y el merge antes del `config.yaml` (paso 5). Si el bot se reinicia solo entre los
  pasos 4 y 6, arranca con el código nuevo y con las variables ya puestas. Correcto.
- **R3:** el recuadro del `KeyError` en el paso 4 explica qué es y cómo pararlo. Docs y
  `verify_database.sh` al día.
- **`comprobar_fase1.sh` es de solo lectura:** no tiene `INSERT`, `DELETE`, `CREATE`, `PUT`,
  `rm` ni `systemctl` de escritura.
- **Desviaciones:**
  - 1 aceptada: leer solo los nombres de tablas de `information_schema` no lee ni escribe datos,
    y la comprobación de `conversations` en `sebastian_db` vale la pena.
  - 2–4 aceptadas.

## 2. Notas para Josem (no piden cambios)

- **Paso 0:** en seb01, el `root` de MariaDB entra con `sudo mysql`, que es lo que usa
  `setup_db.sh`. Si `mysqldump -u root -p` no te deja, usa
  `sudo mysqldump sebastian_db > ~/sebastian_db_backup_$(date +%Y%m%d_%H%M%S).sql`.
- **El cuaderno** no se reinicia: es un `oneshot` del timer, y en su próximo disparo ya lleva el
  código nuevo y las variables. El paso 3 va antes del merge, así que no hay ventana mala.
- **Push:** el merge del paso 4 es local. El `git push` de `main` cuando quieras, después de la
  prueba.

## Para el programador

Responde a: 38f3499 (H3-informe)

H3 aprobado. Nada que hacer hasta que Josem despliegue y haga la prueba por Telegram. **No quites
el worktree**: si la prueba falla, es donde se arregla.
