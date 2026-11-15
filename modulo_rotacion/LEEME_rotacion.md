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
python entrevista.py                           # entrevista corta (13 preguntas)
python entrevista.py --completa                # agrega 6 preguntas opcionales
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

## Las preguntas

**Entrevista corta (13):**

| # | Pregunta | Tipo de respuesta |
|---|---|---|
| 1 | ¿Qué nombre le damos a este lote? | texto |
| 2 | ¿En qué municipio está la finca? | buscador con los 125 municipios |
| 3 | ¿Cómo es el clima en la finca? | Frío (ruana casi todo el día) / Templado (calor suave de día, fresco de noche) / Caliente (calor de día y de noche) |
| 4 | ¿Cómo son las lluvias durante el año? | Dos épocas / Una época larga / Casi todo el año / No sé |
| 5 | ¿Cómo es el terreno del lote? | Plano / Inclinado sin apoyarse / Muy inclinado, toca apoyarse |
| 6 | ¿Qué sembró en la última cosecha? | menú con los 8 cultivos + papa, pasto, otro |
| 7 | ¿Cuántas cosechas seguidas lleva con ese cultivo? | 1 / 2 / 3 o más (solo si respondió la 6) |
| 8 | Comparado con hace unos años, ¿cuánto produce la tierra? | Igual / Un poco menos / La mitad o menos |
| 9 | ¿Hay algún cultivo que NO pueda sembrar? | menú de los 8 cultivos, puede marcar varios |
| 10 | ¿Tiene ganado? | Sí / No |
| 11 | Cuando cae un aguacero fuerte, ¿qué le pasa al lote? | Nada / Charcos de un día o más / El agua arrastra tierra / Las dos cosas |
| 12 | En los años de verano muy largo, ¿qué le pasa a su cultivo? | Tengo riego / Se resiente un poco / Baja mucho / He perdido cosechas |
| 13 | En los años en que llueve mucho más de lo normal, ¿qué le pasa? | No me afecta / Se enferma (hongos) / He perdido cosechas |

Las preguntas 12 y 13 miden cómo le afectan **El Niño** (años muy secos) y **La Niña** (años muy lluviosos), sin nombrarlos.

**Opcionales (`--completa`):** cómo prepara la tierra, cómo abona, si puede dejar el lote una temporada sin vender, qué cultivo cree que mejora la tierra, a quién le vende, cómo se entera del clima.

El nombre de la finca se pide al final, solo si el agricultor quiere guardar.

**Para la interfaz:** todo está en `datos/preguntas_agricultor.json`. Cuando `opciones` dice `"cultivos_menu+..."`, el menú se arma con `cultivos_menu` más `opciones_extra`. Si `multi_opcion`, el agricultor puede marcar varias. La interfaz puede mandar las respuestas tal cual a `recomendar()` y a `diagnosticar()`; la función `normalizar()` del motor las traduce.

## Cómo decide

**Diagnóstico.** Suma puntos con las respuestas de cada área:

| Área | Qué suma puntos |
|---|---|
| Erosión | terreno inclinado, el agua arrastra tierra, último cultivo deja la tierra destapada (papa, hortalizas, maíz…) |
| Rotación y suelo | mismo cultivo seguido, produce menos, no ha sembrado leguminosas |
| Agua y años extremos | charcos, pérdidas en años muy secos o muy lluviosos |

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
- el lote no se deja en descanso, salvo que el agricultor diga (pregunta opcional) que puede aguantar una temporada sin vender.

**Puntaje.** Se calcula con cuatro componentes:

`Puntaje = w_ingreso·I + w_riesgo·(1 − R) + w_suelo·S + w_trabajo·(1 − T)`

- **R (riesgo)** combina:
  - 40 % la falta de aptitud de temperatura según ECOCROP (vale 0 si la temperatura está en el rango óptimo y sube hasta 1 en los límites absolutos);
  - 25 % el riesgo de hongos en las temporadas de lluvia (más si el lote se encharca o se enferma en años muy lluviosos);
  - 15 % la erosión;
  - 20 % la falta de agua en verano (más si pierde cosecha en años muy secos; nada si tiene riego).
- **Pesos.** Ingreso, riesgo, suelo y trabajo pesan igual (25 % cada uno). Si el diagnóstico sale en rojo en erosión o en cansancio del suelo, cuidar la tierra pesa más.

## Pendientes

- [ ] Los valores de tolerancia a hongos, aporte al suelo, ingreso y trabajo de `datos/cultivos.csv` están marcados `ESTIMADO`. Los debe ajustar el equipo, sobre todo el módulo de suelo.
- [ ] Validar el semáforo y las rotaciones con agricultores reales.
