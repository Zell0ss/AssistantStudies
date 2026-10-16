### Umbral de puntuacion (15 positivas, 15 negativas; margen exigido 0.05)

| umbral | positivas aceptadas | negativas que pasan | pos. con margen | neg. con margen |
|---|---|---|---|---|
| 0.50 | 11/15 | 0/15 | 11/15 | 0/15 |
| 0.55 | 11/15 | 0/15 | 11/15 | 0/15 |
| 0.60 | 6/15 | 0/15 | 6/15 | 0/15 |
| 0.65 | 4/15 | 0/15 | 4/15 | 0/15 |
| 0.70 | 2/15 | 0/15 | 2/15 | 0/15 |
| 0.75 | 1/15 | 0/15 | 1/15 | 0/15 |
| 0.80 | 0/15 | 0/15 | 0/15 | 0/15 |
| 0.85 | 0/15 | 0/15 | 0/15 | 0/15 |
| 0.90 | 0/15 | 0/15 | 0/15 | 0/15 |

### Detalle

| clase | expresion | esperada / parecida a | mejor | puntuacion | segunda | margen |
|---|---|---|---|---|---|---|
| positiva | las ruedas del coche | presion_neumaticos | presion_neumaticos | 0.445 | matricula | 0.083 |
| positiva | mi cuñado | parentesco | parentesco | 0.435 | profesion | 0.118 |
| positiva | no puede comer frutos secos | alergia | alergia | 0.331 | nota | 0.057 |
| positiva | cuando cumple años mi madre | cumpleanos | cumpleanos | 0.597 | fecha_revision | 0.353 |
| positiva | su numero de movil | telefono | telefono | 0.603 | direccion | 0.172 |
| positiva | en que calle vive | direccion | direccion | 0.584 | repo | 0.224 |
| positiva | el numero de la placa del coche | matricula | matricula | 0.681 | fecha_revision | 0.240 |
| positiva | a que se dedica | profesion | profesion | 0.579 | parentesco | 0.241 |
| positiva | que le gusta beber | preferencia | preferencia | 0.434 | alergia | 0.147 |
| positiva | en que servidor corre | host | host | 0.584 | db | 0.208 |
| positiva | con que lenguajes esta hecho | stack | stack | 0.701 | host | 0.312 |
| positiva | donde esta el codigo fuente | repo | repo | 0.585 | stack | 0.206 |
| positiva | en que fase va el proyecto | estado | estado | 0.649 | host | 0.236 |
| positiva | que base de datos usa | db | db | 0.782 | host | 0.376 |
| positiva | cuando toca pasar la revision del coche | fecha_revision | fecha_revision | 0.675 | matricula | 0.233 |
| negativa | la presion arterial | presion_neumaticos | presion_neumaticos | 0.446 | fecha_revision | 0.207 |
| negativa | la temperatura del horno | presion_neumaticos | presion_neumaticos | 0.264 | fecha_revision | 0.008 |
| negativa | el saldo de la cuenta del banco | nota | telefono | 0.300 | repo | 0.037 |
| negativa | la altura de Paco | profesion | direccion | 0.240 | presion_neumaticos | 0.001 |
| negativa | el color favorito del coche | preferencia | preferencia | 0.404 | fecha_revision | 0.050 |
| negativa | el numero de hijos | parentesco | telefono | 0.450 | direccion | 0.163 |
| negativa | el peso de la maleta | nota | presion_neumaticos | 0.338 | matricula | 0.053 |
| negativa | la contraseña del wifi | nota | matricula | 0.315 | parentesco | 0.026 |
| negativa | el seguro del coche | matricula | matricula | 0.413 | fecha_revision | 0.057 |
| negativa | la hora de la cena | fecha_revision | cumpleanos | 0.279 | estado | 0.020 |
| negativa | el grupo sanguineo | alergia | alergia | 0.267 | parentesco | 0.010 |
| negativa | el precio de la gasolina | presion_neumaticos | presion_neumaticos | 0.345 | matricula | 0.084 |
| negativa | cuantos kilometros tiene el coche | matricula | fecha_revision | 0.303 | presion_neumaticos | 0.008 |
| negativa | el nombre del perro | parentesco | direccion | 0.272 | parentesco | 0.012 |
| negativa | la talla de zapato | preferencia | presion_neumaticos | 0.301 | preferencia | 0.037 |
