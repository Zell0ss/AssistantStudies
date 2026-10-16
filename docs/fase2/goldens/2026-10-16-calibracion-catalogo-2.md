### Regla del §2.2

| representacion | max(negativas) | corte (+0,03) | reutilizar | positivas sobre el corte | positivas >= reutilizar |
|---|---|---|---|---|---|
| a (descripcion) | 0.544 | 0.574 | 0.58 | 11/15 | 10/15 |
| b (nombre_descripcion) | 0.540 | 0.570 | 0.58 | 7/15 | 6/15 |
| c (con_ejemplos) | 0.629 | 0.659 | 0.66 | 6/15 | 6/15 |

**Representacion elegida: a (descripcion).**
- reutilizar: 0.58, margen 0.03
- sustituir: 0.68, margen 0.05

## Representacion a: descripcion

### Umbral de puntuacion (15 positivas, 25 negativas; margen exigido 0.03)

| umbral | positivas aceptadas | negativas que pasan | pos. con margen | neg. con margen |
|---|---|---|---|---|
| 0.50 | 11/15 | 2/25 | 11/15 | 2/25 |
| 0.55 | 11/15 | 0/25 | 11/15 | 0/25 |
| 0.60 | 6/15 | 0/25 | 6/15 | 0/25 |
| 0.65 | 4/15 | 0/25 | 4/15 | 0/25 |
| 0.70 | 2/15 | 0/25 | 2/15 | 0/25 |
| 0.75 | 1/15 | 0/25 | 1/15 | 0/25 |
| 0.80 | 0/15 | 0/25 | 0/15 | 0/25 |
| 0.85 | 0/15 | 0/25 | 0/15 | 0/25 |
| 0.90 | 0/15 | 0/25 | 0/15 | 0/25 |

### Detalle

| clase | expresion | esperada / parecida a | mejor | puntuacion | segunda | margen |
|---|---|---|---|---|---|---|
| positiva | las ruedas del coche | presion_neumaticos | presion_neumaticos | 0.445 | matricula | 0.083 |
| positiva | mi cuñado | parentesco | parentesco | 0.435 | profesion | 0.118 |
| positiva | no puede comer frutos secos | alergia | alergia | 0.331 | nota | 0.052 |
| positiva | cuando cumple años mi madre | cumpleanos | cumpleanos | 0.597 | fecha_revision | 0.354 |
| positiva | su numero de movil | telefono | telefono | 0.601 | direccion | 0.171 |
| positiva | en que calle vive | direccion | direccion | 0.583 | repo | 0.224 |
| positiva | el numero de la placa del coche | matricula | matricula | 0.681 | fecha_revision | 0.240 |
| positiva | a que se dedica | profesion | profesion | 0.579 | parentesco | 0.241 |
| positiva | que le gusta beber | preferencia | preferencia | 0.434 | alergia | 0.147 |
| positiva | en que servidor corre | host | host | 0.585 | db | 0.208 |
| positiva | con que lenguajes esta hecho | stack | stack | 0.701 | host | 0.312 |
| positiva | donde esta el codigo fuente | repo | repo | 0.585 | stack | 0.206 |
| positiva | en que fase va el proyecto | estado | estado | 0.649 | host | 0.236 |
| positiva | que base de datos usa | db | db | 0.782 | host | 0.375 |
| positiva | cuando toca pasar la revision del coche | fecha_revision | fecha_revision | 0.674 | matricula | 0.232 |
| negativa | la presion arterial | presion_neumaticos | presion_neumaticos | 0.446 | fecha_revision | 0.207 |
| negativa | la temperatura del horno | presion_neumaticos | presion_neumaticos | 0.264 | fecha_revision | 0.008 |
| negativa | el saldo de la cuenta del banco | nota | telefono | 0.299 | repo | 0.036 |
| negativa | la altura de Paco | profesion | direccion | 0.240 | presion_neumaticos | 0.001 |
| negativa | el color favorito del coche | preferencia | preferencia | 0.404 | fecha_revision | 0.050 |
| negativa | el numero de hijos | parentesco | telefono | 0.449 | direccion | 0.162 |
| negativa | el peso de la maleta | nota | presion_neumaticos | 0.338 | matricula | 0.053 |
| negativa | la contraseña del wifi | nota | matricula | 0.315 | parentesco | 0.026 |
| negativa | el seguro del coche | matricula | matricula | 0.413 | fecha_revision | 0.059 |
| negativa | la hora de la cena | fecha_revision | cumpleanos | 0.279 | estado | 0.020 |
| negativa | el grupo sanguineo | alergia | alergia | 0.267 | parentesco | 0.010 |
| negativa | el precio de la gasolina | presion_neumaticos | presion_neumaticos | 0.345 | matricula | 0.084 |
| negativa | cuantos kilometros tiene el coche | matricula | fecha_revision | 0.303 | presion_neumaticos | 0.008 |
| negativa | el nombre del perro | parentesco | direccion | 0.272 | nota | 0.006 |
| negativa | la talla de zapato | preferencia | presion_neumaticos | 0.301 | preferencia | 0.037 |
| negativa | mi coche nuevo | matricula | fecha_revision | 0.414 | matricula | 0.049 |
| negativa | el coche de mi hermano | matricula | matricula | 0.356 | parentesco | 0.012 |
| negativa | la presion del agua en la ducha | presion_neumaticos | presion_neumaticos | 0.453 | estado | 0.204 |
| negativa | la fecha de entrega del pedido | fecha_revision | cumpleanos | 0.412 | fecha_revision | 0.006 |
| negativa | la direccion de correo electronico | direccion | direccion | 0.441 | telefono | 0.046 |
| negativa | el numero de la cuenta bancaria | telefono | telefono | 0.526 | direccion | 0.122 |
| negativa | la edad de Paco | cumpleanos | cumpleanos | 0.335 | parentesco | 0.112 |
| negativa | el trabajo de fin de master | profesion | profesion | 0.393 | estado | 0.032 |
| negativa | el estado del trafico | estado | matricula | 0.335 | presion_neumaticos | 0.009 |
| negativa | el codigo postal | direccion | direccion | 0.544 | repo | 0.143 |

## Representacion b: nombre_descripcion

### Umbral de puntuacion (15 positivas, 25 negativas; margen exigido 0.03)

| umbral | positivas aceptadas | negativas que pasan | pos. con margen | neg. con margen |
|---|---|---|---|---|
| 0.50 | 11/15 | 2/25 | 11/15 | 2/25 |
| 0.55 | 10/15 | 0/25 | 10/15 | 0/25 |
| 0.60 | 5/15 | 0/25 | 5/15 | 0/25 |
| 0.65 | 2/15 | 0/25 | 2/15 | 0/25 |
| 0.70 | 1/15 | 0/25 | 1/15 | 0/25 |
| 0.75 | 1/15 | 0/25 | 1/15 | 0/25 |
| 0.80 | 0/15 | 0/25 | 0/15 | 0/25 |
| 0.85 | 0/15 | 0/25 | 0/15 | 0/25 |
| 0.90 | 0/15 | 0/25 | 0/15 | 0/25 |

### Detalle

| clase | expresion | esperada / parecida a | mejor | puntuacion | segunda | margen |
|---|---|---|---|---|---|---|
| positiva | las ruedas del coche | presion_neumaticos | presion_neumaticos | 0.406 | matricula | 0.045 |
| positiva | mi cuñado | parentesco | parentesco | 0.467 | profesion | 0.147 |
| positiva | no puede comer frutos secos | alergia | alergia | 0.300 | nota | 0.009 |
| positiva | cuando cumple años mi madre | cumpleanos | cumpleanos | 0.577 | parentesco | 0.331 |
| positiva | su numero de movil | telefono | telefono | 0.584 | direccion | 0.189 |
| positiva | en que calle vive | direccion | direccion | 0.560 | telefono | 0.227 |
| positiva | el numero de la placa del coche | matricula | matricula | 0.646 | telefono | 0.247 |
| positiva | a que se dedica | profesion | profesion | 0.565 | direccion | 0.223 |
| positiva | que le gusta beber | preferencia | preferencia | 0.454 | alergia | 0.190 |
| positiva | en que servidor corre | host | host | 0.551 | db | 0.162 |
| positiva | con que lenguajes esta hecho | stack | stack | 0.662 | estado | 0.272 |
| positiva | donde esta el codigo fuente | repo | repo | 0.534 | stack | 0.145 |
| positiva | en que fase va el proyecto | estado | estado | 0.628 | host | 0.235 |
| positiva | que base de datos usa | db | db | 0.750 | stack | 0.369 |
| positiva | cuando toca pasar la revision del coche | fecha_revision | fecha_revision | 0.625 | matricula | 0.206 |
| negativa | la presion arterial | presion_neumaticos | presion_neumaticos | 0.514 | alergia | 0.260 |
| negativa | la temperatura del horno | presion_neumaticos | presion_neumaticos | 0.271 | telefono | 0.022 |
| negativa | el saldo de la cuenta del banco | nota | telefono | 0.287 | estado | 0.028 |
| negativa | la altura de Paco | profesion | nota | 0.256 | presion_neumaticos | 0.027 |
| negativa | el color favorito del coche | preferencia | preferencia | 0.413 | fecha_revision | 0.062 |
| negativa | el numero de hijos | parentesco | telefono | 0.415 | cumpleanos | 0.116 |
| negativa | el peso de la maleta | nota | presion_neumaticos | 0.314 | nota | 0.011 |
| negativa | la contraseña del wifi | nota | matricula | 0.320 | parentesco | 0.032 |
| negativa | el seguro del coche | matricula | matricula | 0.389 | presion_neumaticos | 0.078 |
| negativa | la hora de la cena | fecha_revision | cumpleanos | 0.276 | preferencia | 0.004 |
| negativa | el grupo sanguineo | alergia | alergia | 0.267 | parentesco | 0.032 |
| negativa | el precio de la gasolina | presion_neumaticos | presion_neumaticos | 0.334 | matricula | 0.077 |
| negativa | cuantos kilometros tiene el coche | matricula | presion_neumaticos | 0.288 | telefono | 0.007 |
| negativa | el nombre del perro | parentesco | nota | 0.279 | direccion | 0.001 |
| negativa | la talla de zapato | preferencia | presion_neumaticos | 0.295 | nota | 0.023 |
| negativa | mi coche nuevo | matricula | fecha_revision | 0.385 | matricula | 0.033 |
| negativa | el coche de mi hermano | matricula | parentesco | 0.340 | matricula | 0.006 |
| negativa | la presion del agua en la ducha | presion_neumaticos | presion_neumaticos | 0.469 | estado | 0.236 |
| negativa | la fecha de entrega del pedido | fecha_revision | fecha_revision | 0.392 | cumpleanos | 0.025 |
| negativa | la direccion de correo electronico | direccion | direccion | 0.487 | telefono | 0.109 |
| negativa | el numero de la cuenta bancaria | telefono | telefono | 0.492 | direccion | 0.111 |
| negativa | la edad de Paco | cumpleanos | cumpleanos | 0.348 | parentesco | 0.088 |
| negativa | el trabajo de fin de master | profesion | profesion | 0.384 | estado | 0.020 |
| negativa | el estado del trafico | estado | estado | 0.338 | matricula | 0.005 |
| negativa | el codigo postal | direccion | direccion | 0.540 | telefono | 0.159 |

## Representacion c: con_ejemplos

### Umbral de puntuacion (15 positivas, 25 negativas; margen exigido 0.03)

| umbral | positivas aceptadas | negativas que pasan | pos. con margen | neg. con margen |
|---|---|---|---|---|
| 0.50 | 13/15 | 8/25 | 13/15 | 7/25 |
| 0.55 | 13/15 | 2/25 | 13/15 | 2/25 |
| 0.60 | 10/15 | 2/25 | 10/15 | 2/25 |
| 0.65 | 6/15 | 0/25 | 6/15 | 0/25 |
| 0.70 | 4/15 | 0/25 | 4/15 | 0/25 |
| 0.75 | 3/15 | 0/25 | 3/15 | 0/25 |
| 0.80 | 2/15 | 0/25 | 2/15 | 0/25 |
| 0.85 | 0/15 | 0/25 | 0/15 | 0/25 |
| 0.90 | 0/15 | 0/25 | 0/15 | 0/25 |

### Detalle

| clase | expresion | esperada / parecida a | mejor | puntuacion | segunda | margen |
|---|---|---|---|---|---|---|
| positiva | las ruedas del coche | presion_neumaticos | presion_neumaticos | 0.554 | matricula | 0.120 |
| positiva | mi cuñado | parentesco | parentesco | 0.626 | direccion | 0.242 |
| positiva | no puede comer frutos secos | alergia | alergia | 0.445 | preferencia | 0.104 |
| positiva | cuando cumple años mi madre | cumpleanos | cumpleanos | 0.607 | parentesco | 0.210 |
| positiva | su numero de movil | telefono | telefono | 0.843 | matricula | 0.303 |
| positiva | en que calle vive | direccion | direccion | 0.686 | host | 0.265 |
| positiva | el numero de la placa del coche | matricula | matricula | 0.820 | telefono | 0.289 |
| positiva | a que se dedica | profesion | profesion | 0.579 | direccion | 0.164 |
| positiva | que le gusta beber | preferencia | preferencia | 0.460 | presion_neumaticos | 0.124 |
| positiva | en que servidor corre | host | host | 0.623 | db | 0.220 |
| positiva | con que lenguajes esta hecho | stack | stack | 0.701 | host | 0.312 |
| positiva | donde esta el codigo fuente | repo | repo | 0.585 | direccion | 0.172 |
| positiva | en que fase va el proyecto | estado | estado | 0.649 | repo | 0.205 |
| positiva | que base de datos usa | db | db | 0.782 | host | 0.375 |
| positiva | cuando toca pasar la revision del coche | fecha_revision | fecha_revision | 0.674 | matricula | 0.186 |
| negativa | la presion arterial | presion_neumaticos | presion_neumaticos | 0.603 | telefono | 0.308 |
| negativa | la temperatura del horno | presion_neumaticos | presion_neumaticos | 0.318 | telefono | 0.011 |
| negativa | el saldo de la cuenta del banco | nota | telefono | 0.378 | host | 0.024 |
| negativa | la altura de Paco | profesion | presion_neumaticos | 0.329 | direccion | 0.035 |
| negativa | el color favorito del coche | preferencia | matricula | 0.502 | preferencia | 0.098 |
| negativa | el numero de hijos | parentesco | telefono | 0.548 | matricula | 0.083 |
| negativa | el peso de la maleta | nota | presion_neumaticos | 0.407 | nota | 0.051 |
| negativa | la contraseña del wifi | nota | matricula | 0.369 | host | 0.001 |
| negativa | el seguro del coche | matricula | matricula | 0.469 | fecha_revision | 0.046 |
| negativa | la hora de la cena | fecha_revision | cumpleanos | 0.404 | fecha_revision | 0.047 |
| negativa | el grupo sanguineo | alergia | alergia | 0.314 | repo | 0.026 |
| negativa | el precio de la gasolina | presion_neumaticos | presion_neumaticos | 0.411 | fecha_revision | 0.112 |
| negativa | cuantos kilometros tiene el coche | matricula | matricula | 0.442 | fecha_revision | 0.088 |
| negativa | el nombre del perro | parentesco | cumpleanos | 0.341 | telefono | 0.000 |
| negativa | la talla de zapato | preferencia | presion_neumaticos | 0.339 | nota | 0.016 |
| negativa | mi coche nuevo | matricula | fecha_revision | 0.454 | parentesco | 0.005 |
| negativa | el coche de mi hermano | matricula | parentesco | 0.543 | matricula | 0.103 |
| negativa | la presion del agua en la ducha | presion_neumaticos | presion_neumaticos | 0.531 | telefono | 0.230 |
| negativa | la fecha de entrega del pedido | fecha_revision | cumpleanos | 0.412 | fecha_revision | 0.001 |
| negativa | la direccion de correo electronico | direccion | telefono | 0.459 | direccion | 0.018 |
| negativa | el numero de la cuenta bancaria | telefono | telefono | 0.629 | matricula | 0.128 |
| negativa | la edad de Paco | cumpleanos | cumpleanos | 0.339 | parentesco | 0.029 |
| negativa | el trabajo de fin de master | profesion | estado | 0.425 | profesion | 0.033 |
| negativa | el estado del trafico | estado | matricula | 0.543 | fecha_revision | 0.173 |
| negativa | el codigo postal | direccion | direccion | 0.544 | telefono | 0.010 |

Coste OpenAI medido: 981 tokens x 0.02 $/millon = 0.000020 $ (Anthropic: 0 $)
