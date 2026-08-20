# Gestione Menù v2

Applicazione web per la generazione automatica e il salvataggio di menù
settimanali, con vincoli su proteine, stagionalità e tempo di preparazione.

**Stack:** FastAPI + SQLAlchemy + MySQL 8.0, frontend HTML/JS servito
staticamente dalla stessa applicazione.

## Struttura

```text
.
├── Dockerfile
├── docker-compose.yml
├── main.py                  # entrypoint: monta router e file statici, avvia uvicorn
├── requirements.txt
├── popola_db.py             # script di inizializzazione/sincronizzazione DB
├── data_piatti.py           # dataset dei piatti (usato da popola_db.py)
├── .env                     # NON versionato: credenziali DB
├── src/
│   ├── __init__.py
│   ├── database.py          # modelli ORM SQLAlchemy + init_db()
│   ├── enums.py             # Proteina, Stagione, Tipologia
│   ├── piatto.py            # modello Pydantic Piatto
│   ├── piatto_manuale.py    # modello Pydantic PiattoManuale
│   ├── richiesta_menu.py    # modello Pydantic Richiesta
│   ├── risposta_menu.py     # modello Pydantic Risposta
│   ├── router.py            # endpoint FastAPI
│   └── service.py           # logica di generazione del menù
└── static/
    ├── index.html           # generatore di menù
    └── piatti.html          # gestione anagrafica piatti
```

⚠️ `popola_db.py` e `data_piatti.py` stanno nella **radice** del repo, non in
`src/`. Nel container vengono copiati in `/app/popola_db/`.

## Architettura

Due processi distinti che condividono **la stessa immagine**:

| Processo | Comando | Ruolo |
|---|---|---|
| applicazione | `python3 main.py` (default) | serve API e frontend su :8000 |
| inizializzazione | `python3 popola_db/popola_db.py` | crea le tabelle e sincronizza i dati, poi termina |

Un'immagine è un **ambiente di esecuzione**, non un programma: contiene tutto il
necessario, e il comando si sceglie all'avvio. Costruirne due separate
duplicherebbe le dipendenze e le farebbe divergere.

`popola_db.py` **non** viene eseguito dall'applicazione all'avvio: è un processo
a sé, che va lanciato prima o indipendentemente.

## API

Tutti gli endpoint sono sotto il prefisso `/menu`.

| Metodo | Percorso | Descrizione |
|---|---|---|
| `POST` | `/menu` | genera un menù dai vincoli passati nel body |
| `POST` | `/menu/salva` | salva il menù generato nello storico |
| `GET` | `/menu/elenco-piatti` | elenco completo dei piatti |
| `POST` | `/menu/aggiungi-piatto` | inserisce un piatto in anagrafica |
| `DELETE` | `/menu/elimina-piatto/{id}` | rimuove un piatto |

Il frontend è montato sulla radice `/` con `StaticFiles(..., html=True)`, quindi
`http://host:porta/` serve `index.html`.

Documentazione interattiva generata da FastAPI: `/docs`.

## Configurazione

Tutta via variabili d'ambiente, con default pensati per lo sviluppo locale:

| Variabile | Default | Note |
|---|---|---|
| `DB_HOST` | `db` | nome del servizio nella rete Docker/Kubernetes |
| `DB_PORT` | `3306` | |
| `DB_NAME` | `menu_progetto` | **nel deploy Kubernetes è `menu`** |
| `DB_USER` | `menu` | |
| `DB_PASSWORD` | `menu` | |

I default esistono per retrocompatibilità locale: **in qualsiasi deploy vanno
sovrascritti tutti**, `DB_NAME` incluso.

`popola_db.py` richiede inoltre `PYTHONPATH=/app`, perché gira da
`/app/popola_db/` ma importa `from src.database import ...`.

## Schema del database

Quattro tabelle, create da `Base.metadata.create_all()` dentro `popola_db.py`:

| Tabella | Contenuto |
|---|---|
| `piatti` | anagrafica dei piatti (~166 record dal dataset) |
| `macro` | frequenze settimanali desiderate per proteina (6 record) |
| `pasti_salvati` | storico dei menù salvati |
| `settimane` | raggruppamento dei pasti per settimana |

## Esecuzione locale (Docker Compose)

Serve un file `.env` nella radice:

```
DB_HOST=db
DB_PORT=3306
DB_NAME=menu_progetto
DB_USER=menu
DB_PASSWORD=…
```

```bash
docker compose up --build
```

L'app risponde su `http://localhost:8000`.

## Esecuzione su Kubernetes

Il deploy su cluster è descritto in un repo separato:
[kubernetes-lab](https://github.com/MartinaZelli/kubernetes-lab) — cartella
`manifests/`.

Immagine pubblicata su GHCR:

```
ghcr.io/martinazelli/menu:v2
```

Build con la revisione git impressa nelle label OCI:

```bash
docker build --build-arg GIT_SHA=$(git rev-parse --short HEAD) \
  -t ghcr.io/martinazelli/menu:v2 .
docker push ghcr.io/martinazelli/menu:v2
```

Per sapere da quale commit viene un'immagine:

```bash
docker inspect ghcr.io/martinazelli/menu:v2 \
  --format '{{index .Config.Labels "org.opencontainers.image.revision"}}'
```

Le label OCI sono **in fondo** al Dockerfile di proposito: `revision` cambia a
ogni commit, e ogni istruzione modificata invalida tutti i layer successivi. In
cima costringerebbe a rifare `apk add` e `pip install` a ogni build.

## Logica di generazione del menù

L'algoritmo in `src/service.py` opera in tre fasi:

1. **Analisi** — legge dal database le frequenze desiderate per proteina
2. **Selezione** — filtra i piatti per stagionalità, tempo di preparazione e vincoli
3. **Binding** — inserisce i pasti bloccati manualmente dall'utente

## Comportamento di `popola_db.py`

Non è un semplice "inserisci tutto": **sincronizza** l'anagrafica verso lo stato
descritto in `data_piatti.py`.

- attende il database, ritentando 10 volte a distanza di 5 secondi
- crea le tabelle mancanti
- aggiorna i piatti già presenti, aggiunge i nuovi, **cancella quelli non più
  nel dataset**
- **svuota `pasti_salvati` a ogni esecuzione**

Quest'ultimo punto non è innocuo: rilanciarlo cancella lo storico dei menù.

---

# Punti critici e fragilità

## Nomi duplicati in `data_piatti.py`

Il dataset contiene volutamente piatti con lo **stesso nome ma proteine
diverse** (es. "Polpettone" con carne rossa, carne bianca, formaggi, uova).

`popola_db.py` però costruisce l'indice dei piatti esistenti come dizionario
`nome → oggetto`. Con nomi duplicati, le voci si sovrascrivono a vicenda in quel
dizionario: alla **seconda** esecuzione ne resta una sola per gruppo, e le altre
finiscono tra le "obsolete da cancellare".

Sintomo: dopo un secondo `popola_db.py`, alcuni piatti spariscono.

Correzione: usare come chiave una tupla `(nome, proteina)` invece del solo nome.

## Gli errori vengono ingoiati

`popola_db()` cattura le eccezioni, stampa il messaggio e **non esce con codice
non-zero**. Un fallimento del popolamento risulta quindi come esecuzione
riuscita per Docker e per un Job Kubernetes.

Non fidarsi dello stato di uscita: leggere i log e cercare
`Sincronizzazione database completata.`

Correzione: aggiungere `sys.exit(1)` nel blocco `except`.

## CORS aperto a chiunque

```python
allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
```

Il commento nel codice dice "perfetto per sviluppo", ed è corretto — ma va
ristretto prima di qualsiasi esposizione reale, altrimenti qualunque sito può
chiamare queste API dal browser di un utente.

## Dipendenze non fissate

`requirements.txt` elenca i pacchetti senza versione. Due build a distanza di
mesi possono produrre immagini diverse a parità di codice, ed è il tipo di
problema che si manifesta come "funzionava ieri".

Correzione: `pip freeze > requirements.txt` da un ambiente funzionante, o passare
a uno strumento con lock file.

## Immagine sovradimensionata

L'immagine pesa ~567 MB sul disco. Il Dockerfile installa `gcc`, `g++`,
`musl-dev` e le librerie di sviluppo MariaDB per compilare i pacchetti Python con
parti in C — ma restano nell'immagine finale anche dopo la build, e oggi
`cryptography` distribuisce pacchetti precompilati per Alpine (`pip install`
richiede 12 secondi, non minuti).

Correzione: build **multi-stage**, con i compilatori solo nello stage
intermedio.

## Il container gira come root

Nessuna istruzione `USER` nel Dockerfile. Un processo compromesso ha privilegi
di root dentro il container.

Correzione: creare un utente non privilegiato e aggiungere `USER app`.

## Vincoli sul database

- **Enum binding:** modificare `src/enums.py` senza aggiornare i dati già in
  tabella causa errori di `KeyError`.
- **Integrità referenziale:** eliminare un piatto presente in uno storico viola
  le foreign key.

---

# Da fare

- [ ] Endpoint `/health` per le sonde di readiness/liveness — attualmente
  assente, il che impedisce di configurare correttamente le probe su Kubernetes
- [ ] Chiave `(nome, proteina)` in `popola_db.py`
- [ ] `sys.exit(1)` sugli errori di popolamento
- [ ] Versioni fissate in `requirements.txt`
- [ ] Dockerfile multi-stage e utente non-root
- [ ] Restringere CORS
- [ ] Scegliere una licenza (senza file `LICENSE` il codice è "tutti i diritti
  riservati" anche in un repo pubblico)
