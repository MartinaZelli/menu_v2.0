# Gestione Menù v2

Applicazione web per la generazione automatica e il salvataggio di menù
settimanali, con vincoli su proteine, stagionalità e tempo di preparazione.

**Stack:** FastAPI + SQLAlchemy + MySQL/MariaDB, frontend HTML/JS vanilla servito
staticamente dalla stessa applicazione. Nessun build step per il frontend.

---

## Struttura

```text
.
├── Dockerfile
├── docker-compose.yml
├── main.py                  # entrypoint: monta router e file statici, avvia uvicorn
├── requirements.txt
├── popola_db.py             # script di inizializzazione/sincronizzazione DB
├── data_piatti.py           # dataset dei piatti (usato da popola_db.py)
├── .env                     # NON versionato: credenziali DB + HOST_IP
├── src/
│   ├── __init__.py
│   ├── database.py          # modelli ORM SQLAlchemy + init_db()
│   ├── enums.py             # Proteina, Stagione, Tipologia, Giorni_settimana
│   ├── piatto.py            # modello Pydantic Piatto
│   ├── piatto_manuale.py    # modello Pydantic PiattoManuale (pasto bloccato)
│   ├── richiesta_menu.py    # modello Pydantic Richiesta (body di POST /menu)
│   ├── risposta_menu.py     # modelli Pydantic Pasti / Pasti_settimana / Risposta
│   ├── router.py            # endpoint FastAPI
│   └── service.py           # logica di generazione e salvataggio del menù
└── static/
    ├── index.html           # generatore di menù
    └── piatti.html          # gestione anagrafica piatti
```

⚠️ `popola_db.py` e `data_piatti.py` stanno nella **radice** del repo, non in
`src/`. Nel container vengono copiati in `/app/popola_db/`.

---

## Architettura

### Due processi, una sola immagine

| Processo | Comando | Ruolo |
|---|---|---|
| applicazione | `python3 main.py` (default del Dockerfile) | serve API e frontend su :8000 |
| inizializzazione | `python3 popola_db/popola_db.py` | crea le tabelle e sincronizza i dati, poi termina |

Un'immagine è un **ambiente di esecuzione**, non un programma: contiene tutto il
necessario, e il comando si sceglie all'avvio. Costruirne due separate
duplicherebbe le dipendenze e le farebbe divergere nel tempo.

`popola_db.py` **non** viene eseguito dall'applicazione all'avvio: è un processo a
sé, che va lanciato prima o indipendentemente.

### Ordine dei mount in `main.py`

```python
app.include_router(router.router)                                   # PRIMA
app.mount("/", StaticFiles(directory="static", html=True), ...)     # POI
```

L'ordine è vincolante. Un mount su `/` registrato prima del router
intercetterebbe qualunque percorso, incluse le rotte `/menu`, e le API
smetterebbero di rispondere. Non riordinare queste due righe.

### Due livelli di modelli, allineati a mano

- **ORM SQLAlchemy** in `src/database.py`: `PiattoDB`, `MacroDB`, `SettimanaDB`,
  `PastoSalvatoDB`.
- **Pydantic** in `src/piatto.py`, `src/richiesta_menu.py`, `src/risposta_menu.py`.

La conversione da riga di database a modello Pydantic avviene con
`Piatto.model_validate(piatto_db)`, resa possibile da
`model_config = {"from_attributes": True}`.

Non esiste generazione automatica di un livello dall'altro: aggiungere una colonna
richiede di toccare entrambi i file.

### Gli enum non arrivano al database

`src/enums.py` definisce `Proteina`, `Stagione`, `Tipologia` e `Giorni_settimana`,
ma le colonne corrispondenti sono `String`, non `Enum` SQL. Sia `data_piatti.py`
sia `src/service.py` lavorano sui **valori stringa**:

```python
p.proteina == "carne bianca"     # confronto su stringa, non su Proteina.CARNE_BIANCA
```

Conseguenza: cambiare un `value` in `enums.py` non produce un errore di importazione,
ma rompe silenziosamente il matching finché i record già in tabella non vengono
riscritti.

### Doppia convenzione sui giorni

`Giorni_settimana` usa gli accenti (`"lunedì"`), mentre le chiavi interne dei pasti
e i campi di `Pasti_settimana` sono senza (`lunedi`). `service.py` normalizza con
`.replace("ì", "i")`. Qualunque codice che tocchi i giorni deve rispettare entrambe
le forme.

---

## Logica di generazione del menù

`genera_menu_ordinato()` in `src/service.py` riempie **14 slot** (7 giorni × pranzo
e cena) in cinque passaggi:

1. **Lettura dei vincoli** — legge dalla tabella `macro` le frequenze settimanali
   desiderate per ogni proteina.
2. **Binding dei pasti bloccati** — i `pasti_bloccati` scelti manualmente
   dall'utente vengono inseriti subito nella mappa dei pasti, e le loro proteine
   sottratte dalle frequenze residue.
3. **Costruzione del pool** — `genera_pool_proteine_dinamico()` produce una lista di
   proteine lunga quanto i posti liberi, ripetendo ciascuna secondo la sua frequenza
   e completando a caso se non basta. La lista viene mescolata.
4. **Pranzi lavorativi, a ritroso** — cicla dal venerdì al lunedì (indici 4→0) e per
   ogni pranzo ancora vuoto sceglie una proteina dal pool, poi un piatto che
   soddisfi tutti i filtri: proteina, stagione richiesta, `tempo <= tempo_massimo` e
   `adatto_al_lavoro == True`.
   Con probabilità **0.60** lo stesso piatto viene ripetuto nel giorno precedente
   (prima si tenta il pranzo, altrimenti la cena): è la logica degli avanzi, e il
   verso all'indietro serve proprio perché l'avanzo si cucina *prima* di essere
   consumato.
5. **Riempimento degli slot restanti** — stessa selezione, ma `adatto_al_lavoro` è
   richiesto solo se lo slot è un pranzo in un giorno lavorativo.

### Il piatto sentinella `id=999`

Se al punto 5 nessun piatto in anagrafica soddisfa i filtri, lo slot riceve un
segnaposto:

```python
Piatto(id=999, nome=f"Manca {prot_scelta}", tempo=0, adatto_al_lavoro=False)
```

Non è un piatto reale. `salva_menu_settimanale()` lo riconosce e lo persiste come
`nome_manuale` con `piatto_id = None`. Qualunque nuovo codice che manipoli i piatti
deve gestire questo valore magico — non c'è nulla, oltre all'id, che lo distingua.

### Salvataggio

`POST /menu/salva` fa un **upsert per `data_inizio`**: se esiste già una settimana
con quella data, i suoi `pasti_salvati` vengono **cancellati e riscritti**. Salvare
due volte la stessa settimana non duplica i record, ma sovrascrive il contenuto
precedente senza chiedere conferma.

---

## API

Tutti gli endpoint sono sotto il prefisso `/menu`.

| Metodo | Percorso | Descrizione |
|---|---|---|
| `POST` | `/menu` | genera un menù dai vincoli passati nel body (`Richiesta`) |
| `POST` | `/menu/salva` | salva il menù generato nello storico |
| `GET` | `/menu/elenco-piatti` | elenco completo dei piatti |
| `POST` | `/menu/aggiungi-piatto` | inserisce un piatto in anagrafica |
| `DELETE` | `/menu/elimina-piatto/{id}` | rimuove un piatto |

Il frontend è montato sulla radice `/` con `StaticFiles(..., html=True)`, quindi
`http://host:porta/` serve `index.html` e `/piatti.html` la pagina di anagrafica.

Documentazione interattiva generata da FastAPI: `/docs`.

Non esiste un endpoint `/health`: le probe di readiness/liveness su Kubernetes non
sono configurabili correttamente finché non viene aggiunto.

---

## Configurazione

Tutta via variabili d'ambiente, con default pensati per lo sviluppo locale:

| Variabile | Default | Note |
|---|---|---|
| `DB_HOST` | `db` | nome del servizio nella rete Docker/Kubernetes |
| `DB_PORT` | `3306` | |
| `DB_NAME` | `menu_progetto` | **nel deploy Kubernetes è `menu`** |
| `DB_USER` | `menu` | |
| `DB_PASSWORD` | `menu` | |
| `HOST_IP` | *(nessuno)* | usato **solo** da Compose per il binding della porta |

I default esistono per retrocompatibilità locale: **in qualsiasi deploy vanno
sovrascritti tutti**, `DB_NAME` incluso.

`DB_*` sono lette in **due punti indipendenti** — `src/database.py` e `popola_db.py`
ne hanno ciascuno la propria copia. Modificandone una, va aggiornata anche l'altra.

`popola_db.py` richiede inoltre `PYTHONPATH=/app` nel container, perché gira da
`/app/popola_db/` ma importa `from src.database import ...`.

### Il file `.env` ha due ruoli distinti

Questo è il punto che più spesso confonde, e vale la pena chiarirlo:

1. **Interpolazione nel compose file.** Compose legge automaticamente `.env` dalla
   directory del progetto per risolvere i `${...}` scritti *dentro*
   `docker-compose.yml`. È così che viene valorizzato `HOST_IP` in
   `ports: - "${HOST_IP}:8000:8000"`. Questa sostituzione avviene sulla macchina
   host, prima che il container esista.
2. **Variabili d'ambiente del container.** La direttiva `env_file: - .env` prende
   lo stesso file e ne inietta il contenuto *dentro* il container. È così che
   l'applicazione riceve `DB_HOST`, `DB_USER`, ecc.

Se `HOST_IP` manca, Compose non fallisce: emette un warning e lo sostituisce con
stringa vuota, ottenendo `":8000:8000"`, che Docker interpreta come binding su
**tutte** le interfacce. Funziona, ma espone la porta oltre l'intenzione: se volevi
`127.0.0.1` ti ritrovi raggiungibile dalla rete locale.

```
WARN[0000] The "HOST_IP" variable is not set. Defaulting to a blank string.
```

---

## Schema del database

Quattro tabelle, create da `Base.metadata.create_all()` dentro `popola_db.py`:

| Tabella | Contenuto |
|---|---|
| `piatti` | anagrafica dei piatti (166 record dal dataset) |
| `macro` | frequenze settimanali desiderate per proteina (6 record) |
| `settimane` | una riga per settimana salvata, chiave `data_inizio` (unique) |
| `pasti_salvati` | i singoli pasti, con FK verso `settimane` e `piatti` |

Le frequenze in `macro`, definite in `popola_db.py`, sommano a 18 su 14 slot
settimanali: il pool viene troncato ai posti disponibili, quindi non tutte le
frequenze sono soddisfatte a ogni generazione.

---

## Esecuzione locale (Docker Compose)

> **Attenzione:** `docker-compose.yml` definisce solo i servizi `app` e `popola-db`.
> **Non contiene un servizio MySQL.** Il default `DB_HOST=db` presuppone un database
> **già esistente e raggiungibile** su quella rete. Con il solo `docker compose up`
> l'applicazione parte ma non riesce a connettersi, e `popola-db` esaurisce i suoi
> 10 tentativi e termina con codice 1.

Serve un file `.env` nella radice — nota `HOST_IP`, che l'esempio precedente di
questo README ometteva:

```dotenv
HOST_IP=127.0.0.1
DB_HOST=db
DB_PORT=3306
DB_NAME=menu_progetto
DB_USER=menu
DB_PASSWORD=…
```

Poi, avendo un MySQL/MariaDB raggiungibile come `db` sulla rete `menu-network`:

```bash
docker compose up --build            # avvia l'applicazione
docker compose run --rm popola-db    # popola il database (processo separato)
```

L'app risponde su `http://127.0.0.1:8000`.

### Esecuzione senza container

```bash
pip install -r requirements.txt
python3 main.py                      # uvicorn su 0.0.0.0:8000
PYTHONPATH=. python3 popola_db.py    # dalla radice del repo, non da src/
```

Vanno esportate le variabili `DB_*` che puntano a un MySQL raggiungibile, oppure
si accettano i default (`db:3306`), che in locale funzionano solo con una voce
corrispondente in `/etc/hosts`.

### Test e qualità

Il repository **non contiene test, linter o formatter configurati**. Non esistono
`pytest`, `ruff` o simili: la verifica è manuale, tipicamente da `/docs`.

---

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

Le label OCI sono **in fondo** al Dockerfile di proposito: `revision` cambia a ogni
commit, e ogni istruzione modificata invalida tutti i layer successivi. In cima
costringerebbe a rifare `apk add` e `pip install` a ogni build.

---

## Comportamento di `popola_db.py`

Non è un semplice "inserisci tutto": **sincronizza** l'anagrafica verso lo stato
descritto in `data_piatti.py`.

- attende il database, ritentando 10 volte a distanza di 5 secondi;
- crea le tabelle mancanti con `Base.metadata.create_all()`;
- aggiorna i piatti già presenti, aggiunge i nuovi, **cancella quelli non più nel
  dataset**;
- **svuota `pasti_salvati` a ogni esecuzione**.

Quest'ultimo punto non è innocuo: rilanciarlo cancella lo storico dei menù. Non è
un passo di routine da eseguire a ogni deploy.

---

# Punti critici e fragilità

## Nomi duplicati in `data_piatti.py`

Il dataset contiene volutamente piatti con lo **stesso nome ma proteine diverse**.
Su 166 record ci sono **153 nomi distinti**: 10 nomi compaiono più volte, tra cui
"Polpettone" (×4, con carne rossa, carne bianca, latticini e uova) e "Rotolo di
frittata farcito" (×3).

`popola_db.py` però costruisce l'indice dei piatti esistenti come dizionario
`nome → oggetto`:

```python
nomi_db = {p.nome: p for p in piatti_db}
```

Con nomi duplicati le voci si sovrascrivono a vicenda: alla **seconda** esecuzione
ne resta una sola per gruppo, e le altre finiscono tra le "obsolete da cancellare".

Sintomo: dopo un secondo `popola_db.py`, alcuni piatti spariscono.

Correzione: usare come chiave la tupla `(nome, proteina)` invece del solo nome.

## Gli errori di popolamento vengono ingoiati

`popola_db()` cattura le eccezioni, stampa il messaggio e **non esce con codice
non-zero**. Un fallimento risulta quindi come esecuzione riuscita per Docker e per
un Job Kubernetes.

Non fidarsi dello stato di uscita: leggere i log e cercare la riga
`Sincronizzazione database completata.`

Correzione: `sys.exit(1)` nel blocco `except`.

## `tipologia` è ignorata in scrittura

`POST /menu/aggiungi-piatto` riceve il campo `tipologia` dal client ma lo scarta,
scrivendo una costante:

```python
tipologia="primo"   # in src/router.py
```

Anche il frontend (`static/piatti.html`) invia `tipologia: "primo"` fisso. Ne segue
che ogni piatto aggiunto dall'interfaccia è un primo, qualunque cosa sia in realtà,
e l'enum `Tipologia` resta di fatto inutilizzato in scrittura.

## `id` obbligatorio su un piatto ancora inesistente

Il modello Pydantic `Piatto` dichiara `id: int` come campo **obbligatorio**, anche
quando il piatto va ancora creato. Il frontend aggira il vincolo inviando `id: 0`,
che il database poi ignora grazie all'auto-increment.

Correzione: separare il modello di input (senza `id`) da quello di output — la
distinzione classica fra uno schema `PiattoCreate` e uno `PiattoRead`.

## Campo `descrizione` inesistente nel database

`Piatto` espone `descrizione: Optional[str]`, ma `PiattoDB` non ha la colonna
corrispondente: `GET /menu/elenco-piatti` restituisce quindi sempre `null`.

## Eliminare un piatto referenziato restituisce 500

`DELETE /menu/elimina-piatto/{id}` esegue la cancellazione senza verificare i
riferimenti. Se il piatto compare in `pasti_salvati`, la foreign key viene violata
e l'endpoint fallisce con un errore non gestito. Il frontend non mostra il
messaggio: chiama `fetch` senza controllare `res.ok`, quindi l'eliminazione sembra
riuscita finché la lista non si ricarica identica.

## CORS aperto a chiunque

```python
allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
```

Il commento nel codice dice "perfetto per sviluppo", ed è corretto — ma va ristretto
prima di qualsiasi esposizione reale, altrimenti qualunque sito può chiamare queste
API dal browser di un utente autenticato sulla stessa rete.

## Dipendenze non fissate

`requirements.txt` elenca i pacchetti senza versione. Due build a distanza di mesi
possono produrre immagini diverse a parità di codice: è il tipo di problema che si
manifesta come "funzionava ieri".

Correzione: `pip freeze > requirements.txt` da un ambiente funzionante, o passare a
uno strumento con lock file.

## Immagine sovradimensionata

L'immagine pesa **567 MB** sul disco (151 MB compressi). Il Dockerfile installa
`gcc`, `g++`, `musl-dev` e le librerie di sviluppo MariaDB per compilare i pacchetti
Python con parti in C — ma questi restano nell'immagine finale anche dopo la build,
e oggi `cryptography` distribuisce pacchetti precompilati per Alpine.

Correzione: build **multi-stage**, con i compilatori solo nello stage intermedio.

## Il container gira come root

Nessuna istruzione `USER` nel Dockerfile. Un processo compromesso ha privilegi di
root dentro il container.

Correzione: creare un utente non privilegiato e aggiungere `USER app`.

## Accoppiamento fra enum e dati già scritti

Modificare un `value` in `src/enums.py` senza migrare i record esistenti non produce
un errore immediato, ma fa fallire i confronti su stringa in `service.py`: i piatti
con il vecchio valore smettono di essere selezionabili e il menù si riempie di
segnaposto "Manca …".

---

# Da fare

- [ ] Endpoint `/health` per le sonde di readiness/liveness su Kubernetes
- [ ] Chiave `(nome, proteina)` in `popola_db.py`
- [ ] `sys.exit(1)` sugli errori di popolamento
- [ ] Rispettare `tipologia` in `POST /menu/aggiungi-piatto` (backend e frontend)
- [ ] Schemi separati `PiattoCreate` / `PiattoRead` per togliere l'`id` fittizio
- [ ] Colonna `descrizione` in `PiattoDB`, oppure rimuovere il campo dal modello
- [ ] Gestire la violazione di foreign key su `DELETE /menu/elimina-piatto/{id}`
- [ ] Versioni fissate in `requirements.txt`
- [ ] Dockerfile multi-stage e utente non-root
- [ ] Restringere CORS
- [ ] Test automatici (nessuno presente)
- [ ] Scegliere una licenza (senza file `LICENSE` il codice è "tutti i diritti
  riservati" anche in un repo pubblico)
