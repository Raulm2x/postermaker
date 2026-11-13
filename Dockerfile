FROM python:3.12-slim

WORKDIR /app

# Fuentes del sistema para marcas y textos
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY postermaker ./postermaker

RUN pip install --no-cache-dir .

EXPOSE 8000

ENV POSTERMAKER_OUTPUT=/tmp/postermaker

CMD ["postermaker-web", "--host", "0.0.0.0", "--port", "8000"]
