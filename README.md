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
├── requirements-dev.txt     # dipendenze di test (NON entrano nell'immagine)
├── pytest.ini
├── ruff.toml                # configurazione del linter
├── popola_db.py             # script di inizializzazione/sincronizzazione DB
├── data_piatti.py           # dataset dei piatti (usato da popola_db.py)
├── .env                     # NON versionato: credenziali DB + HOST_IP
├── src/
│   ├── __init__.py
│   ├── config.py            # configurazione del DB, condivisa app/popola_db
│   ├── database.py          # modelli ORM SQLAlchemy + get_db() + init_db()
│   ├── enums.py             # Proteina, Stagione, Tipologia, Giorni_settimana
│   ├── health.py            # sonde /health/live e /health/ready
│   ├── piatto.py            # modello Pydantic Piatto
│   ├── piatto_manuale.py    # modello Pydantic PiattoManuale (pasto bloccato)
│   ├── richiesta_menu.py    # modello Pydantic Richiesta (body di POST /menu)
│   ├── risposta_menu.py     # modelli Pydantic Pasti / Pasti_settimana / Risposta
│   ├── router.py            # endpoint FastAPI
│   └── service.py           # logica di generazione e salvataggio del menù
├── tests/                   # pytest su SQLite in memoria
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
app.include_router(health.router)                                   # PRIMA
app.include_router(router.router)                                   # PRIMA
app.mount("/", StaticFiles(directory="static", html=True), ...)     # POI
```

L'ordine è vincolante. Starlette valuta le rotte nell'ordine di registrazione e
un mount su `/` corrisponde a **qualunque** percorso: registrato prima dei
router intercetterebbe `/menu` e `/health`. Il guasto sarebbe subdolo — nessun
errore in avvio, solo 404 — e `/piatti.html` continuerebbe a rispondere 200,
quindi l'healthcheck di HAProxy resterebbe verde su un'applicazione senza API.

### Due livelli di modelli, allineati a mano

- **ORM SQLAlchemy** in `src/database.py`: `PiattoDB`, `MacroDB`, `SettimanaDB`,
  `PastoSalvatoDB`.
- **Pydantic** in `src/piatto.py` (`PiattoBase` → `Piatto`, che aggiunge l'`id`,
  e `PiattoCreate`, che non lo prevede perché lo assegna il database),
  `src/richiesta_menu.py`, `src/risposta_menu.py`.

La conversione da riga di database a modello Pydantic avviene con
`Piatto.model_validate(piatto_db)`, resa possibile da
`model_config = {"from_attributes": True}`.

Non esiste generazione automatica di un livello dall'altro: aggiungere una colonna
richiede di toccare entrambi i file.

⚠️ **Aggiungere una colonna a un modello ORM è la modifica più pericolosa del
repo.** `Base.metadata.create_all()` crea le tabelle mancanti ma **non esegue
`ALTER TABLE`**, e i due laboratori hanno volumi persistenti: la colonna non
comparirebbe e ogni query fallirebbe con `Unknown column`. L'applicazione
partirebbe comunque, perché l'engine è lazy, e HAProxy resterebbe verde perché
controlla un file statico. Serve una migrazione esplicita.

### Sessioni del database: chi apre chiude

Gli endpoint ricevono la sessione con `Depends(get_db)` e i service la ricevono
come parametro. Né gli uni né gli altri devono chiamare `db.close()`: la
chiusura avviene in un punto solo, nel `finally` di `get_db()`.

È anche ciò che rende testabile il codice: nei test
`app.dependency_overrides[get_db]` sostituisce la funzione con una che restituisce
una sessione SQLite, senza toccare né l'engine né i moduli.

### Gli enum non arrivano al database

`src/enums.py` definisce `Proteina`, `Stagione`, `Tipologia` e `Giorni_settimana`,
ma le colonne corrispondenti sono `String`, non `Enum` SQL. Sia `data_piatti.py`
sia `src/service.py` lavorano sui **valori stringa**:

```python
p.proteina == "carne bianca"     # confronto su stringa, non su Proteina.CARNE_BIANCA
```

`valore_enum()` in `src/enums.py` è l'unico punto che estrae `.value`.

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
| `DELETE` | `/menu/elimina-piatto/{id}` | rimuove un piatto (404 se non esiste, 409 se è usato in un menù) |

Fuori dal prefisso, per le sonde di Kubernetes:

| Metodo | Percorso | Descrizione |
|---|---|---|
| `GET` | `/health/live` | il processo risponde. **Non tocca il database** |
| `GET` | `/health/ready` | il processo *e* il database rispondono (`SELECT 1`). 503 se no |

Il frontend è montato sulla radice `/` con `StaticFiles(..., html=True)`, quindi
`http://host:porta/` serve `index.html` e `/piatti.html` la pagina di anagrafica.

Documentazione interattiva generata da FastAPI: `/docs`.

**Perché le sonde sono due.** Kubernetes reagisce in modo opposto: se fallisce la
*liveness* **uccide e riavvia** il container, se fallisce la *readiness* lo toglie
dagli endpoint del Service lasciandolo vivo. Mettere il controllo del database
nella liveness farebbe riavviare in ciclo tutte le repliche a ogni singhiozzo del
database — si aggiunge carico a un database già in sofferenza, e riavviare l'app
non ripara il database. Nella readiness i pod restano vivi, smettono di ricevere
traffico e vi rientrano da soli.

Entrambe sono dichiarate `def` e non `async def`: un `SELECT 1` bloccante dentro
una funzione async bloccherebbe l'event loop per tutta la durata del timeout, e
in quella finestra **anche `/health/live` smetterebbe di rispondere**.

⚠️ I due laboratori non le usano ancora: HAProxy controlla `/piatti.html` e i
manifest Kubernetes non hanno probe. Vanno configurate a mano — vedi `NOTE_LAB.md`.

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

Facoltative, tutte con un default che riproduce il comportamento precedente:

| Variabile | Default | Note |
|---|---|---|
| `DB_STRICT` | `false` | se `true`, l'uso di un default termina il processo con codice 1 |
| `DB_RETRY_TENTATIVI` | `30` | tentativi di connessione di `popola_db.py` |
| `DB_RETRY_ATTESA` | `5` | secondi fra un tentativo e l'altro |
| `POPOLA_DB_SVUOTA_STORICO` | `true` | se `false`, il popolamento non azzera `pasti_salvati` |

I default esistono per retrocompatibilità locale: **in qualsiasi deploy vanno
sovrascritti tutti**, `DB_NAME` incluso.

`DB_*` sono lette in **un solo punto**, `src/config.py`, importato sia dall'app
sia da `popola_db.py`. Il modulo sta in `src/` e non nella radice perché il
Dockerfile elenca i file uno per uno: un modulo nella radice supererebbe il build
e fallirebbe all'avvio con `ModuleNotFoundError`.

### Diagnostica all'avvio

L'applicazione e `popola_db.py` stampano, come prima cosa, a quale database si
stanno collegando e **se un valore proviene da un default**:

```
[config] DB_HOST=mysql.db.svc.cluster.local  (da ambiente)
[config] DB_NAME=menu_progetto  (DEFAULT — nessuna variabile d'ambiente!)
[config] DSN: mysql+pymysql://menu_user:***@mysql.db.svc.cluster.local:3306/menu
```

La password è sempre mascherata. Serve perché i default sono sbagliati **in modo
plausibile**: producono un errore di connessione o, peggio, una connessione a un
database esistente ma diverso da quello atteso. Senza questa riga il fallback
resta invisibile finché non si indaga.

Con `DB_STRICT=true` un fallback diventa un errore fatale. Il controllo è
eseguito da `main()` e da `popola_db()`, **mai a livello di modulo**: un
`sys.exit` all'import farebbe fallire `import src.database`, mandando il
container in crashloop e impedendo perfino l'esecuzione dei test.

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

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

./.venv/bin/python -m pytest              # tutti i test
./.venv/bin/python -m pytest -k duplicato # per nome
./.venv/bin/ruff check .                  # linter
./.venv/bin/ruff check --fix .
```

I test girano su **SQLite in memoria**: non serve un database avviato e ogni
test parte da uno stato pulito. `tests/conftest.py` documenta tre dettagli senza
i quali i test sembrerebbero funzionare senza verificare nulla:

- **`poolclass=StaticPool`** — un database SQLite in memoria vive dentro la
  singola connessione che lo ha creato. Con il pool normale ogni nuova
  connessione vedrebbe un database vuoto, e il sintomo sarebbe un
  `no such table` apparentemente casuale.
- **`check_same_thread=False`** — `TestClient` esegue l'app in un thread diverso
  da quello del test.
- **`PRAGMA foreign_keys=ON`** — SQLite **non applica le foreign key** se non
  glielo si chiede, a ogni connessione. Senza, il test «eliminare un piatto
  referenziato deve dare 409» passerebbe in verde anche con la correzione
  assente: un test che non può fallire non è un test.

**Cosa SQLite non cattura:** `VARCHAR` troppo corti, differenze di collation
(MySQL è case-insensitive di default, SQLite no) e soprattutto gli errori
`Unknown column`. La verifica sullo stack reale resta indispensabile:

```bash
curl -s localhost:8000/menu/elenco-piatti | head -c 200
curl -I localhost:8000/piatti.html          # deve dare 200: healthcheck HAProxy
curl -s localhost:8000/health/ready
```

Il linter è configurato in `ruff.toml` con `target-version = "py312"`, cioè la
versione dell'**immagine** e non quella della macchina di sviluppo: è ciò che
evita di introdurre costrutti che in produzione non girerebbero.

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

- attende il database, ritentando **30 volte a distanza di 5 secondi** (150
  secondi in tutto, configurabili con `DB_RETRY_TENTATIVI` e `DB_RETRY_ATTESA`).
  Erano 10 tentativi, cioè 50 secondi, ma un MySQL al **primo** avvio — quando
  deve ancora inizializzare il volume dei dati — impiega regolarmente più di due
  minuti: lo script si arrendeva prima che il database fosse pronto;
- crea le tabelle mancanti con `Base.metadata.create_all()`;
- indicizza i piatti esistenti per **coppia `(nome, proteina)`**, aggiorna quelli
  presenti, aggiunge i nuovi e **cancella quelli non più nel dataset**;
- **svuota `pasti_salvati` a ogni esecuzione** (disattivabile con
  `POPOLA_DB_SVUOTA_STORICO=false`);
- **esce con codice 1** se qualcosa fallisce.

### Perché lo svuotamento dello storico è strutturale

Non è solo una comodità. `PastoSalvatoDB.piatto_id` è una foreign key **senza
`ON DELETE`**: finché un menù salvato referenzia un piatto, quel piatto non è
cancellabile. È lo svuotamento a rendere possibile la rimozione dei piatti
obsoleti.

Conseguenza diretta: con `POPOLA_DB_SVUOTA_STORICO=false`, un piatto tolto dal
dataset ma già usato in un menù salvato fa fallire la sincronizzazione con
`IntegrityError`. È il motivo per cui lo svuotamento resta il comportamento
predefinito, nonostante cancelli lo storico.

### Il codice di uscita

Prima l'eccezione veniva stampata e il processo terminava comunque con `0`:
Docker e un Job Kubernetes consideravano il popolamento riuscito, e si otteneva
un **deploy verde su un database vuoto**.

La riga `Sincronizzazione database completata.` resta un contratto: la procedura
di verifica documentata nel laboratorio Kubernetes la cerca testualmente nei log.

---

# Punti critici e fragilità

## Risolti in questo consolidamento

Restano documentati perché i due laboratori possono ancora girare codice
precedente, e perché i test che li coprono non vanno rimossi.

| Difetto | Sintomo | Correzione |
|---|---|---|
| Indice dei piatti sul solo nome | Le modifiche a un piatto omonimo finivano sulla riga sbagliata e andavano perse; rimuovere una variante non la cancellava. **Il conteggio restava 166**, ed è per questo che non si notava | chiave `(nome, proteina)` |
| Errori di popolamento ingoiati | Uscita con codice 0 su un database vuoto: deploy verde, Job `Completed` | `sys.exit(1)` |
| Attesa del database troppo breve | 10 tentativi × 5s = 50s, contro i oltre 2 minuti di un MySQL al primo avvio | 30 tentativi, configurabili |
| `tipologia` scartata in scrittura | Ogni piatto aggiunto dall'interfaccia risultava un «primo» | valore rispettato, e selettore aggiunto al modulo |
| `id` obbligatorio in inserimento | Il frontend inviava `id: 0` per aggirare il vincolo | schema `PiattoCreate` |
| Campo `descrizione` inesistente | L'API restituiva sempre `null` | campo rimosso (**non** colonna aggiunta) |
| `DELETE` su piatto referenziato | 500 non gestito; un id inesistente rispondeva 200 «deleted» | 409 e 404 |
| `stagione` non `Optional` | Una sola riga con `stagione` NULL faceva fallire con 500 l'**intera** `/menu/elenco-piatti` | `Optional` negli schemi di lettura |
| Assenza di `/health` | Probe Kubernetes non configurabili | `/health/live` e `/health/ready` |
| Configurazione duplicata | Due copie da tenere allineate a mano, con default sbagliati e invisibili | `src/config.py` + diagnostica all'avvio |
| Blocchi persi al salvataggio | L'utente bloccava un piatto, lo vedeva col lucchetto, salvava, e nel database finiva quello vecchio | i blocchi vengono fusi nel payload |

## Ancora aperti

### CORS aperto a chiunque

```python
allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
```

Accettabile in sviluppo, da restringere prima di qualsiasi esposizione reale:
altrimenti qualunque sito può chiamare queste API dal browser di un utente.

### Nessuna autenticazione

`DELETE /menu/elimina-piatto/{id}` è aperto a chiunque raggiunga la porta 8000, e
in Kubernetes il Service è un `NodePort` su 30080.

### Dipendenze non fissate

`requirements.txt` elenca i pacchetti senza versione. Due build a distanza di
mesi possono produrre immagini diverse a parità di codice.

Un caso concreto già evitato: `src/database.py` importava `declarative_base` da
`sqlalchemy.ext.declarative`, un alias legacy che emette già oggi un
`MovedIn20Warning` e che sparisce in SQLAlchemy 2.1. Senza versioni fissate
sarebbe diventato un `ImportError` all'avvio, senza preavviso e senza che nulla
fosse cambiato nel codice.

⚠️ **`cryptography` non va rimosso** «perché non sembra usato»: MySQL 8 usa
`caching_sha2_password` e senza quel pacchetto PyMySQL non riesce ad
autenticarsi. È un errore a runtime, non a build.

### Immagine sovradimensionata e container root

L'immagine pesa **567 MB** (151 MB compressi) e non ha alcuna istruzione `USER`.
Il Dockerfile installa `gcc`, `g++`, `musl-dev` e le librerie di sviluppo
MariaDB, che restano nell'immagine finale anche dopo la build — ma PyMySQL è
**puro Python** e `cryptography` distribuisce da anni wheel precompilate per
Alpine.

Correzione prevista: verificare se il blocco `apk add` sia del tutto superfluo,
poi build multi-stage e utente non privilegiato (`USER` **dopo** i `pip install`,
altrimenti il build fallisce per permessi).

### L'applicazione non crea mai le tabelle

`init_db()` esiste in `src/database.py` ma **non è chiamato da nessuno**: solo
`popola_db.py` esegue `create_all`. È una scelta corretta — due repliche che
fanno DDL in parallelo sono una pessima idea — ma è una dipendenza d'ordine
implicita: senza il popolamento, l'app parte e ogni richiesta va in 500 con
`Table 'piatti' doesn't exist`.

### Accoppiamento fra enum e dati già scritti

Modificare un `value` in `src/enums.py` senza migrare i record esistenti non
produce un errore immediato, ma fa fallire i confronti su stringa in
`service.py`: i piatti con il vecchio valore smettono di essere selezionabili e
il menù si riempie di segnaposto «Manca …».

### Il sentinella `id=999` non è a prova di crescita

`popola_db` inserisce i piatti con id **espliciti** 1-166, quindi
l'`AUTO_INCREMENT` riparte da 167. Servirebbero 833 piatti aggiunti
dall'interfaccia perché uno reale ottenga l'id 999 e venga scambiato per un
segnaposto. Improbabile, ma la soluzione pulita (un flag booleano) costa poco.

Effetto collaterale correlato: **un piatto aggiunto dall'interfaccia viene
cancellato al successivo `popola_db`**, perché non è in `data_piatti.py` e
finisce fra gli obsoleti.

---

# Da fare

## Fatto

- [x] Endpoint `/health/live` e `/health/ready` per le sonde Kubernetes
- [x] Chiave `(nome, proteina)` in `popola_db.py`
- [x] `sys.exit(1)` sugli errori di popolamento
- [x] Rispettare `tipologia` in `POST /menu/aggiungi-piatto` (backend e frontend)
- [x] Schema `PiattoCreate` per togliere l'`id` fittizio
- [x] Campo `descrizione` rimosso dal modello (la colonna **non** è stata aggiunta)
- [x] `DELETE /menu/elimina-piatto/{id}`: 404 e 409 al posto del 500
- [x] Test automatici (pytest su SQLite in memoria) e linter (ruff)
- [x] Configurazione del database in un punto solo, con diagnostica all'avvio
- [x] Attesa del database allungata e resa configurabile

## Da fare

- [ ] Dockerfile multi-stage e utente non-root
- [ ] Versioni fissate in `requirements.txt`
- [ ] Restringere CORS
- [ ] Autenticazione sugli endpoint di scrittura
- [ ] Sostituire il sentinella `id=999` con un flag esplicito
- [ ] Preservare i piatti aggiunti dall'interfaccia fra un popolamento e l'altro
- [ ] Scegliere una licenza (senza file `LICENSE` il codice è "tutti i diritti
  riservati" anche in un repo pubblico)

## Nei laboratori

Da fare **a mano**, nei rispettivi repo — la traccia completa è in `NOTE_LAB.md`
(non versionato):

- [ ] Kubernetes: `readinessProbe` e `livenessProbe` in `20-web-deployment.yaml`
- [ ] Ansible: `LB_CHECK_PATH` da `/piatti.html` a `/health/ready`
- [ ] Attenzione: senza `imagePullPolicy` i nodi tengono `:v2` in cache, e il
  ruolo Ansible gira con `build: policy` — in entrambi i casi il codice nuovo
  può non arrivare mai, senza alcun errore
