# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Regola primaria: i due laboratori NON si toccano

Questo progetto è di **appoggio** a due laboratori di studio, che vivono in repo
separati:

- `/home/topina/Sviluppo/ansible_ubuntu_docker_menu` — clona il branch indicato
  da `GIT_VERSION` (oggi `feature/implementazioni`) e fa `docker compose up`
- `/home/topina/Sviluppo/kubernetes-lab` — consuma `ghcr.io/martinazelli/menu:v2`

**Non modificarli mai.** Sono materiale di studio: i passaggi vanno fatti a mano,
uno alla volta, per assimilarli. Quando una modifica a `menu_v2.0` richiede un
intervento là, va annotata in **`NOTE_LAB.md`** (file non versionato, nella
radice) e lasciata a chi studia.

## Comandi

```bash
# Ambiente di sviluppo
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# Test (SQLite in memoria, nessun database richiesto)
./.venv/bin/python -m pytest
./.venv/bin/python -m pytest tests/test_popola_db.py -v      # un singolo file
./.venv/bin/python -m pytest -k "duplicato"                  # per nome

# Linter
./.venv/bin/ruff check .
./.venv/bin/ruff check --fix .

# Avvio locale (richiede un MySQL raggiungibile)
python3 main.py                      # uvicorn su 0.0.0.0:8000

# Popolamento del DB (processo separato, NON eseguito dall'app)
PYTHONPATH=. python3 popola_db.py

# Stack containerizzato
docker compose up --build            # richiede un .env nella radice, con HOST_IP
docker compose run --rm popola-db

# Build per GHCR con la revisione git nelle label OCI
docker build --build-arg GIT_SHA=$(git rev-parse --short HEAD) -t ghcr.io/martinazelli/menu:v2 .
```

Verifica manuale delle API: `http://localhost:8000/docs`.

## Vincoli inviolabili

Rompere uno di questi significa rompere un laboratorio. Verificati leggendo i
due repo.

1. Le env var `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` — nomi
   invariati. In Kubernetes arrivano da `envFrom`, quindi una rinomina è
   invisibile fino al runtime.
2. Servizi compose `app` e `popola-db`; `${HOST_IP}`; `docker-compose.yml` nella
   radice (il ruolo Ansible elenca i servizi e punta `project_src` alla radice).
3. Layout nell'immagine: `/app/popola_db/popola_db.py` con `data_piatti.py`
   accanto, `WORKDIR /app`, import `from src.database import …` con `PYTHONPATH=/app`.
4. Porta 8000, bind `0.0.0.0`, avvio via `CMD ["python3","main.py"]`.
5. `static/piatti.html` deve rispondere 200: è l'healthcheck di HAProxy
   (`LB_CHECK_PATH`).
6. `GET /menu/elenco-piatti` è la smoke test documentata in entrambi i lab.
7. `ARG GIT_SHA` + `LABEL org.opencontainers.image.revision` nel Dockerfile.
8. Nessuna env var **obbligatoria** nuova: solo facoltative con default.
9. **Nessun modulo nuovo nella radice.** Il Dockerfile elenca i file uno per
   uno; solo `src/` entra tutto. Un modulo nella radice supera il build e
   fallisce all'avvio con `ModuleNotFoundError`.

## Architettura

FastAPI + SQLAlchemy (ORM) + MySQL, frontend HTML/JS vanilla servito dalla stessa
applicazione. Nessun template engine, nessun build step per il frontend.

**Flusso di generazione:** `static/index.html` → `POST /menu` →
[router.py](src/router.py) valida il body come `Richiesta` → [service.py](src/service.py)
`genera_menu_ordinato(db, richiesta)` → `Risposta` → il frontend può inviarlo a
`POST /menu/salva`.

**Sessioni del database.** Gli endpoint ricevono la sessione con
`Depends(get_db)` ([src/database.py](src/database.py)) e i service la ricevono
come parametro. **Chi apre chiude**: né gli endpoint né i service devono
chiamare `db.close()`. È anche ciò che rende possibile
`app.dependency_overrides[get_db]` nei test.

**Configurazione in un punto solo:** [src/config.py](src/config.py), importato
sia dall'app sia da `popola_db.py`. Sta in `src/` per il vincolo 9. Stampa una
diagnostica all'avvio che dice, per ogni variabile, se il valore viene
dall'ambiente o da un default, con la password mascherata.

**Due livelli di modelli, da tenere allineati a mano:**
- ORM in [src/database.py](src/database.py): `PiattoDB`, `MacroDB`,
  `SettimanaDB`, `PastoSalvatoDB`
- Pydantic in [src/piatto.py](src/piatto.py) (`PiattoBase` → `Piatto` con id,
  `PiattoCreate` senza), [src/richiesta_menu.py](src/richiesta_menu.py),
  [src/risposta_menu.py](src/risposta_menu.py)

⚠️ **Aggiungere una colonna a un modello ORM è la modifica più pericolosa del
repo.** `Base.metadata.create_all()` non esegue `ALTER TABLE` e i due lab hanno
volumi persistenti: la colonna non comparirebbe e ogni query fallirebbe con
`Unknown column`. L'app partirebbe comunque (l'engine è lazy) e HAProxy
resterebbe verde perché controlla un file statico. Serve una migrazione esplicita.

**Gli enum non arrivano al database.** [src/enums.py](src/enums.py) definisce
`Proteina`, `Stagione`, `Tipologia`, `Giorni_settimana`, ma le colonne sono
`String` e i confronti sono sui **valori stringa**. `valore_enum()` in
`src/enums.py` è l'unico punto che estrae `.value`. Modificare un `value`
rompe silenziosamente il matching finché i record non vengono riscritti.

**Chiavi dei pasti.** Il servizio indicizza la settimana con
`f"{giorno}_{momento}"`, dove `giorno` è **senza** accento (`lunedi`) mentre
`Giorni_settimana` li usa **con** l'accento (`lunedì`). `service.py` normalizza
con `.replace("ì", "i")`. Rispettare entrambe le convenzioni.

**Algoritmo di generazione** (`genera_menu_ordinato`), 14 slot:
1. legge da `macro` le frequenze per proteina e le decrementa in base ai
   `pasti_bloccati`;
2. costruisce un pool di proteine lungo quanto i posti liberi;
3. riempie **a ritroso** i pranzi lavorativi (indici 4→0) filtrando per
   proteina, stagione, `tempo <= tempo_massimo` e `adatto_al_lavoro`; con
   probabilità 0.60 ripete il piatto nel giorno precedente (avanzi — il verso
   all'indietro serve perché l'avanzo si cucina *prima* di essere consumato);
4. riempie gli slot restanti; se nessun candidato passa i filtri inserisce un
   segnaposto con **`id=999`** e nome `"Manca <proteina>"`.

`id=999` è un valore sentinella: `salva_menu_settimanale()` lo salva come
`nome_manuale` con `piatto_id=None`. Ogni codice che manipola i piatti deve
gestirlo.

**Sonde:** `/health/live` (non tocca il DB) e `/health/ready` (`SELECT 1`, 503 se
fallisce), registrate in [src/health.py](src/health.py). In
[main.py](main.py) l'ordine è vincolante: `include_router` **prima** di
`app.mount("/")`, altrimenti `StaticFiles` intercetta tutto e risponde 404 senza
alcun errore in avvio.

**Persistenza:** salvare una settimana già presente **cancella e riscrive** i
suoi `pasti_salvati` (upsert per `data_inizio`).

## Vincoli operativi

- `docker-compose.yml` **non definisce un servizio MySQL**: `DB_HOST=db`
  presuppone un database esterno raggiungibile su quella rete.
- Il `.env` serve a **due cose distinte**: Compose lo legge da solo per
  interpolare `${HOST_IP}` nel compose file, e `env_file:` lo inietta nel
  container. Se `HOST_IP` manca, Compose emette solo un warning e la porta
  finisce esposta su tutte le interfacce.
- `popola_db.py` **svuota `pasti_salvati` a ogni esecuzione** (default). Non è
  un capriccio: `PastoSalvatoDB.piatto_id` è una FK senza `ON DELETE`, quindi è
  lo svuotamento a rendere possibile la rimozione dei piatti obsoleti.
  Disattivabile con `POPOLA_DB_SVUOTA_STORICO=false`, al prezzo di non poter
  più rimuovere un piatto già usato in un menù.
- `popola_db.py` esce con **codice 1** se il popolamento fallisce. La riga di
  log `Sincronizzazione database completata.` è un contratto: la procedura di
  verifica del lab Kubernetes la cerca testualmente.
- L'app **non crea mai le tabelle**: `init_db()` esiste ma non è chiamato da
  nessuno. Solo `popola_db.py` esegue `create_all`. È corretto (due repliche che
  fanno DDL in parallelo sono una pessima idea), ma è una dipendenza d'ordine.
- CORS è `allow_origins=["*"]` — da restringere prima di qualsiasi esposizione reale.
- Le label OCI stanno **in fondo** al Dockerfile di proposito: `revision` cambia
  a ogni commit e invaliderebbe i layer di `apk add`/`pip install`.
- `requirements.txt` non fissa le versioni; il container gira come root.

## Test

`tests/conftest.py` usa SQLite in memoria. Tre dettagli sono documentati lì e
non vanno rimossi: `StaticPool` (il database in memoria vive nella singola
connessione), `check_same_thread=False` (`TestClient` gira in un altro thread) e
`PRAGMA foreign_keys=ON` (SQLite **non** applica le FK di default — senza, il
test sull'eliminazione di un piatto referenziato passerebbe in verde anche con
il bug presente).

Cosa SQLite non cattura: `VARCHAR` troppo corti, differenze di collation, e
soprattutto gli errori `Unknown column`. La smoke test sullo stack reale resta
indispensabile.

## Configurazione

| Variabile | Default | Note |
|---|---|---|
| `DB_HOST` | `db` | |
| `DB_PORT` | `3306` | |
| `DB_NAME` | `menu_progetto` | in Kubernetes è `menu`, in Ansible `progetto` |
| `DB_USER` | `menu` | |
| `DB_PASSWORD` | `menu` | |
| `DB_STRICT` | `false` | se `true`, un default diventa `sys.exit(1)` |
| `DB_RETRY_TENTATIVI` | `30` | tentativi di connessione di `popola_db.py` |
| `DB_RETRY_ATTESA` | `5` | secondi fra i tentativi |
| `POPOLA_DB_SVUOTA_STORICO` | `true` | se `false`, conserva i menù salvati |
| `HOST_IP` | — | usato **solo** da Compose per il binding della porta |

I default **non corrispondono a nessuno dei due lab** e sono sbagliati in modo
plausibile: vanno sempre sovrascritti. La diagnostica all'avvio esiste per
rendere visibile il fallback.

Il deploy Kubernetes vive in un repo separato:
https://github.com/MartinaZelli/kubernetes-lab (cartella `manifests/`).

## Convenzioni

Codice, identificatori, commenti e messaggi di commit sono in **italiano**.
Mantieni questa lingua. I commenti spiegano il **perché**, non il cosa: le
scelte non ovvie (l'ordine dei mount, `def` invece di `async def`, il legame fra
svuotamento e foreign key) sono annotate sul posto di proposito.
