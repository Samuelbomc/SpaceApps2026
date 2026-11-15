# Artefactos experimentales por horizonte

Cada carpeta `15d`, `30d` y `60d` contiene modelos entrenados de forma independiente
para cinco objetivos. Las temperaturas son medias del periodo, la lluvia es un
acumulado y la humedad es una media de observaciones válidas. No son condiciones
exclusivas del último día ni una trayectoria diaria futura.

Cada horizonte contiene `report.json` y subdirectorios por objetivo, con modelos
de evaluación y reajuste, metadatos, particiones, curvas y predicciones. La humedad
requiere reconstrucción residual. `summary.json` conserva las métricas y cobertura.

Ver [evaluación por horizonte](../../../docs/reference/ml/horizon-results.md) y
[contrato de inferencia](../../../docs/reference/model-inference.md). Los scores
corresponden a artefactos de evaluación, sin acreditar aprobación agronómica.
