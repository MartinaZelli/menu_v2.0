FROM python:3.12-alpine3.20
RUN apk add --no-cache \
    g++ \
    libffi-dev \
    mariadb-dev \
    gcc \
    musl-dev \
    mariadb-connector-c-dev

RUN mkdir /app
ADD requirements.txt /app
RUN pip install -r /app/requirements.txt
ADD src /app/src
ADD static /app/static
ADD main.py /app
RUN mkdir /app/popola_db
ADD popola_db.py /app/popola_db
ADD data_piatti.py /app/popola_db
WORKDIR /app
ARG GIT_SHA=unknown
LABEL org.opencontainers.image.source="https://github.com/MartinaZelli/menu_v2.0"
LABEL org.opencontainers.image.description="Gestione Menù v2 — FastAPI + MySQL"
LABEL org.opencontainers.image.revision="${GIT_SHA}"
CMD ["python3", "main.py"]
