# Vista de despliegue

Esta vista describe las configuraciones ejecutables del repositorio. La instalación
productiva, sus respaldos y objetivos de carga requieren validación del entorno.

## Docker Compose

```mermaid
flowchart LR
    USER[Navegador] -->|localhost:3000| WEB[web: Nginx y Angular]
    WEB -->|api:8000| API[api: FastAPI]
    API --> PG[(postgres:5432)]
    API --> MONGO[(mongo:27017)]
    ING[worker: ingesta] --> PG
    TRAIN[training-worker] --> PG
    REC[recommendation-worker] --> PG
    TRAIN --> MONGO
    REC --> MONGO
    API --> DATA[Montaje ./data:/app/data]
    ING --> DATA
    TRAIN --> DATA
    REC --> DATA
```

| Servicio | Función | Persistencia o acceso |
| --- | --- | --- |
| web | Build Angular servido por Nginx y proxy `/backend/` | Puerto host 3000 en loopback |
| api | HTTP y aplicación de migraciones al arrancar | Puerto host 8000 en loopback |
| postgres | Identidad, fincas, observaciones y calendarios | Volumen `agrogeo_postgres_data`; puerto host 5432 en loopback |
| mongo | Registro ML y resultados | Volumen `agrogeo_mongo_data`; sin puerto publicado al host |
| worker | Ingesta periódica | Directorio compartido `/app/data` |
| training-worker | Construcción, entrenamiento y evaluación | Directorio compartido y registro ML |
| recommendation-worker | Inferencia y evaluación de rotación | Snapshots, artefactos y resultados |

API y workers esperan los healthchecks de las bases. Los workers se construyen
con el extra ML y `libgomp1`; la API puede leer metadatos sin cargar XGBoost.
Los artefactos empaquetados están bajo `/app/ml/artifacts`; los datos operativos
usan `/app/data`. Las rutas de overrides deben existir dentro del contenedor.
El proyecto Compose se llama `agrogeo`. Los nombres de bases, usuario y volúmenes
se pueden configurar para conservar instalaciones existentes; cambiar el nombre
del proyecto no migra su almacenamiento. El build Angular genera
`frontend/dist/agrogeo/browser`, que Nginx sirve desde su directorio público.

## Entorno nativo

`scripts.dev_stack` inicia PostgreSQL persistente y opcionalmente MongoDB local,
API y Angular. Usa directorios de `data/local/` y MongoDB en puerto 27018 cuando
se elige `--with-mongo`. Incluye el consumidor de actualizaciones manuales, que
permanece inactivo hasta que se encola una solicitud. `--with-workers` activa
también ingesta y entrenamiento diarios y recomendaciones cada hora, en procesos
independientes con los mismos calendarios y conexiones. No mezclar las bases nativas con las de Compose suponiendo
que comparten estado.

## Requisitos de operación

Configurar secretos propios, HTTPS, cookie Secure, orígenes y proxies de confianza
antes de exponer la aplicación. Las bases y los archivos privados no deben estar
servidos por Nginx. Los respaldos deben cubrir PostgreSQL, el backend de resultados,
CSV privados, snapshots y modelos referenciados con un corte consistente.

No hay un orquestador externo ni una política automática de eliminación de
artefactos referenciados. La operación debe comprobar capacidad, restauración,
retención, dependencias y métricas bajo el volumen de despliegue elegido.

Ver [configuración](../reference/configuration.md),
[guía local](../guides/development.md) y [runbook](../operations/runbook.md).
