# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Comandi

```bash
# Avvio locale senza container (richiede un MySQL raggiungibile)
pip install -r requirements.txt
python3 main.py                      # uvicorn su 0.0.0.0:8000

# Popolamento/sincronizzazione del DB (processo separato, NON eseguito dall'app)
PYTHONPATH=. python3 popola_db.py

# Stack containerizzato
docker compose up --build            # richiede un file .env nella radice
docker compose run --rm popola-db    # esegue python3 popola_db/popola_db.py

# Build per GHCR con la revisione git nelle label OCI
docker build --build-arg GIT_SHA=$(git rev-parse --short HEAD) -t ghcr.io/martinazelli/menu:v2 .
```

Non esistono test, linter o formatter configurati nel repo: non inventare comandi
`pytest`/`ruff` — se servono, vanno introdotti esplicitamente.

Verifica manuale delle API: `http://localhost:8000/docs` (Swagger generato da FastAPI).

## Architettura

FastAPI + SQLAlchemy (ORM) + MySQL, frontend HTML/JS vanilla servito dalla stessa
applicazione. Nessun template engine, nessun build step per il frontend.

**Flusso di una richiesta di generazione menù:**
`static/index.html` → `POST /menu` → [router.py](src/router.py) valida il body come
`Richiesta` → [service.py](src/service.py) `genera_menu_ordinato()` apre e chiude da sé
la sessione DB → ritorna un `Risposta` → il frontend può poi inviarlo a `POST /menu/salva`.

**Due livelli di modelli, da tenere allineati a mano:**
- ORM SQLAlchemy in [src/database.py](src/database.py): `PiattoDB`, `MacroDB`,
  `SettimanaDB`, `PastoSalvatoDB`.
- Pydantic in [src/piatto.py](src/piatto.py), [src/richiesta_menu.py](src/richiesta_menu.py),
  [src/risposta_menu.py](src/risposta_menu.py), [src/piatto_manuale.py](src/piatto_manuale.py).
  La conversione avviene con `Piatto.model_validate(piatto_db)` (`from_attributes`).

**Gli enum non arrivano al database.** [src/enums.py](src/enums.py) definisce
`Proteina`, `Stagione`, `Tipologia`, `Giorni_settimana`, ma le colonne sono `String`
e sia [data_piatti.py](data_piatti.py) sia [src/service.py](src/service.py) confrontano
i **valori stringa** (`p.proteina == "carne bianca"`). Modificare un `value` in `enums.py`
rompe silenziosamente il matching finché i record esistenti non vengono riscritti.

**Chiavi dei pasti.** Il servizio indicizza la settimana con stringhe
`f"{giorno}_{momento}"` dove `giorno` è senza accento (`lunedi`, `martedi`, …) e
`momento` è `pranzo` o `cena`. `Giorni_settimana` usa invece gli accenti (`lunedì`):
`service.py` normalizza con `.replace("ì", "i")`. Qualunque nuovo codice che tocchi
i giorni deve rispettare questa doppia convenzione.

**Algoritmo di generazione** (`genera_menu_ordinato`), 14 slot (7 giorni × 2 pasti):
1. legge da `macro` le frequenze desiderate per proteina e le decrementa in base ai
   `pasti_bloccati` ricevuti dal client;
2. costruisce un pool di proteine di lunghezza pari ai posti liberi;
3. riempie **a ritroso** i pranzi lavorativi (indici 4→0), filtrando per proteina,
   stagione, `tempo <= tempo_massimo` e `adatto_al_lavoro`; con probabilità 0.60
   ripete lo stesso piatto nel giorno precedente (avanzi);
4. riempie gli slot restanti; se nessun candidato soddisfa i filtri inserisce un
   piatto segnaposto con **`id=999`** e nome `"Manca <proteina>"`.

`id=999` è un valore sentinella, non un piatto reale: `salva_menu_settimanale()` lo
salva come `nome_manuale` con `piatto_id=None`. Ogni codice che manipola i piatti deve
gestirlo.

**Persistenza dei menù:** salvare una settimana già presente **cancella e riscrive**
i suoi `pasti_salvati` (upsert per `data_inizio`).

## Vincoli operativi

- `main.py` monta `StaticFiles` su `/` **dopo** `include_router`. L'ordine è
  necessario: un mount su `/` inserito prima intercetterebbe le rotte `/menu`.
- `docker-compose.yml` **non definisce un servizio MySQL**. Il default `DB_HOST=db`
  presuppone un database esterno raggiungibile su quella rete (in Kubernetes è il
  nome del Service). In locale serve un MySQL avviato a parte e un `.env` coerente.
- `popola_db.py` gira da `/app/popola_db/` nel container ma importa `src.*`: da qui
  `PYTHONPATH=/app` in compose. Se lo esegui dalla radice del repo usa `PYTHONPATH=.`.
- `popola_db.py` **svuota `pasti_salvati` a ogni esecuzione**: rilanciarlo distrugge
  lo storico dei menù. Non eseguirlo come passo di routine.
- `popola_db.py` indicizza i piatti esistenti con `{nome: obj}`, ma
  [data_piatti.py](data_piatti.py) contiene **nomi duplicati con proteine diverse**
  (es. "Riso alla cantonese" uova/carne rossa). Alla seconda esecuzione i duplicati
  vengono visti come obsoleti e cancellati. La correzione prevista è una chiave
  `(nome, proteina)`.
- `popola_db()` cattura le eccezioni senza uscire con codice non-zero: un fallimento
  sembra un successo per Docker e per un Job Kubernetes. Verificare nei log la riga
  `Sincronizzazione database completata.`
- CORS è `allow_origins=["*"]` — accettabile in sviluppo, da restringere prima di
  qualsiasi esposizione reale.
- Le label OCI stanno **in fondo** al Dockerfile di proposito: `revision` cambia a
  ogni commit e invaliderebbe i layer di `apk add`/`pip install`.
- `requirements.txt` non fissa le versioni; il container gira come root.

Il [README.md](README.md) contiene la lista completa dei punti aperti ("Da fare"):
endpoint `/health`, chiave composta in `popola_db.py`, `sys.exit(1)` sugli errori,
versioni fissate, Dockerfile multi-stage e utente non-root, CORS ristretto, licenza.

## Configurazione

Variabili d'ambiente lette sia da [src/database.py](src/database.py) sia da
[popola_db.py](popola_db.py) (duplicate, non condivise): `DB_HOST`, `DB_PORT`,
`DB_NAME`, `DB_USER`, `DB_PASSWORD`. I default (`db`/`3306`/`menu_progetto`/`menu`/`menu`)
esistono per retrocompatibilità locale e vanno sovrascritti in ogni deploy —
`DB_NAME` incluso (in Kubernetes è `menu`, non `menu_progetto`).

Il deploy Kubernetes vive in un repo separato:
https://github.com/MartinaZelli/kubernetes-lab (cartella `manifests/`).

## Convenzioni

Codice, nomi di identificatori, commenti e messaggi di commit sono in **italiano**.
Mantieni questa lingua nelle modifiche.
