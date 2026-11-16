FROM python:3.14-slim
ARG PYTHON_EXTRAS=api,storage,geospatial,mongo
RUN case ",$PYTHON_EXTRAS," in *,ml,*) apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/* ;; esac
WORKDIR /app
COPY pyproject.toml README.md ./
COPY apps ./apps
COPY packages ./packages
COPY pipelines ./pipelines
COPY scripts ./scripts
COPY ml ./ml
COPY modulo_rotacion/*.py ./modulo_rotacion/
COPY modulo_rotacion/datos/cultivos.csv ./modulo_rotacion/datos/cultivos.csv
COPY infra/database ./infra/database
RUN pip install --no-cache-dir ".[${PYTHON_EXTRAS}]"
RUN case ",$PYTHON_EXTRAS," in *,processing,*) apt-get update && apt-get install -y --no-install-recommends libexpat1 && rm -rf /var/lib/apt/lists/* ;; esac
EXPOSE 8000
CMD ["sh", "-c", "python -m scripts.migrate && uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers"]
