# Módulo del agricultor: entrevista, diagnóstico y rotación

Le hace preguntas sencillas al agricultor y le devuelve tres cosas:
1. **Cómo está su lote**: un semáforo de erosión, cansancio del suelo, plagas y agua, con consejos.
2. **Qué sembrar en el año**: las 3 mejores rotaciones, con la explicación y las alertas de cada una.
3. **Un resumen corto** para imprimir o mandar por WhatsApp.

Cada entrevista queda guardada, así que se pueden comparar los lotes de una finca y ver cómo cambia un lote con el tiempo.

> **No usa el módulo climático.** El clima sale de dos respuestas del agricultor: si su zona es fría, templada o caliente, y cómo son las lluvias. Los requisitos de cada cultivo salen **solo de FAO ECOCROP**. La aptitud del municipio sale de UPRA.

## Cómo usarlo

```
pip install pandas openpyxl                    # una sola vez
python entrevista.py                           # entrevista corta (22 preguntas)
python entrevista.py --completa                # agrega preguntas abiertas para el equipo
python lotes.py                                # fincas guardadas
python lotes.py --finca "La Esperanza"         # comparar los lotes de una finca
python lotes.py --finca "La Esperanza" --lote "Lote de arriba"   # historia de un lote
python diagnostico.py                          # solo el semáforo, con las respuestas de ejemplo
python motor_rotacion.py                       # solo la rotación, con las respuestas de ejemplo
```

Durante la entrevista: se escribe el **número** de la opción, **?** muestra por qué se hace la pregunta y **Enter** la salta.

## Archivos

| Archivo | Qué hace |
|---|---|
| `entrevista.py` | Hace las preguntas una por una, muestra el resultado y lo guarda |
| `diagnostico.py` | Semáforo del lote (verde / amarillo / rojo) con consejos |
| `motor_rotacion.py` | Arma y califica las rotaciones del año |
| `lotes.py` | Guarda entrevistas, compara lotes y genera el resumen de WhatsApp |
| `actualizar_ecocrop.py` | Saca los rangos de ECOCROP del Excel y crea `datos/ecocrop_cultivos.csv` |
| `datos/preguntas_agricultor.json` | **Las preguntas.** La interfaz arma el formulario desde aquí |
| `datos/cultivos.csv` | Los cultivos: cadena UPRA, especie ECOCROP, familia, ciclo y valores estimados |
| `datos/ecocrop_cultivos.csv` | Temperatura y lluvia óptimas y absolutas de cada especie (ECOCROP) |
| `datos/aptitud_transitorios_municipio.csv` | Aptitud UPRA por municipio |
| `datos/Cultivos_rotables_mas_sembrados_y_aptos_Antioquia.xlsx` | Excel con aptitud, ranking y hoja ECOCROP |
| `datos/fincas/` | Aquí se guardan las entrevistas (una carpeta por finca y por lote) |

## Las preguntas (para la interfaz)

En `datos/preguntas_agricultor.json`, cada pregunta tiene estos campos:

- `texto`: lo que ve el agricultor, en lenguaje sencillo.
- `tipo`: el espacio de respuesta que se dibuja:
  - `opcion`: botones con `opciones`, donde cada una trae el `texto` que se ve y el `valor` que se guarda;
  - `si_no`: dos botones;
  - `lista_cultivos` y `lista_texto`: caja de texto;
  - `numero`: campo de número;
  - `municipio`: buscador con los 125 municipios de Antioquia.
- `nivel`: `basico` va en la entrevista corta y `completo` solo en la completa.
- `ayuda`: el texto del botón «¿Por qué preguntamos esto?».
- `mostrar_si`: la pregunta solo aparece si se cumple la condición. Por ejemplo, «¿cuántas veces fumiga?» solo sale si el agricultor nombró alguna plaga.
- `campo`: dónde se guarda la respuesta.

Recomendaciones para que sea fácil de usar:
- una pregunta por pantalla;
- botones grandes;
- una barra de avance («3 de 22»);
- un botón para saltar la pregunta.

## Cómo decide

**Diagnóstico.** Suma puntos con las respuestas de cada área:

| Área | Qué suma puntos |
|---|---|
| Erosión | pendiente, tractor en loma, tierra que se lava, suelo pelado, sin coberturas |
| Cansancio del suelo | misma familia repetida, produce menos, sin abono orgánico, nunca descansa, sin leguminosas |
| Plagas y enfermedades | cuántas plagas, cuántas fumigaciones, cultivo repetido, encharcamiento |
| Agua | encharcamiento, sin riego |

Con pocos puntos el área sale en verde, con algunos en amarillo y con muchos en rojo. Cada color trae sus consejos.

**Clima.** La zona se convierte en una temperatura media típica:
- fría: 15 °C (2.000–3.000 m);
- templada: 21 °C;
- caliente: 26 °C.

Las lluvias marcan qué temporadas son de lluvia (más hongos y más erosión) y cuál es seca.

**Filtros: un cultivo no se recomienda si…**
- tiene aptitud UPRA menor a 10 en el municipio;
- la temperatura de la zona está fuera de su rango **absoluto** de ECOCROP;
- el agricultor no lo puede sembrar;
- necesita más mano de obra de la que hay;
- en la temporada seca, sin riego, ECOCROP le pide 1.000 mm de lluvia al año o más.

**Reglas de rotación:**
- no repetir la misma familia de planta seguida;
- máximo una solanácea al año;
- si el agricultor no puede aguantar sin vender, no se deja el lote en descanso.

**Puntaje.** Se calcula con cuatro componentes:

`Puntaje = w_ingreso·I + w_riesgo·(1 − R) + w_suelo·S + w_trabajo·(1 − T)`

- **R (riesgo)** combina:
  - 45 % la falta de aptitud de temperatura según ECOCROP (vale 0 si la temperatura está en el rango óptimo y sube hasta 1 en los límites absolutos);
  - 25 % el riesgo de hongos en las temporadas de lluvia;
  - 15 % la erosión;
  - 15 % la falta de agua en la temporada seca.
- **Pesos.** Lo que el agricultor escoge como lo **más** importante pesa 55 % y cada una de las otras tres cosas 15 %. Si el diagnóstico sale en rojo en erosión o en cansancio del suelo, cuidar la tierra pesa más.

## Pendientes

- [ ] Los valores de tolerancia a hongos, aporte al suelo, ingreso y trabajo de `datos/cultivos.csv` están marcados `ESTIMADO`. Los debe ajustar el equipo, sobre todo el módulo de suelo.
- [ ] Validar el semáforo y las rotaciones con agricultores reales.
