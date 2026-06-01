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
WORKDIR /app
CMD python3 popola_db/popola_db.py && python3 main.py

