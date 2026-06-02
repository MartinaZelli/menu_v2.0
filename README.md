# Gestione Menù v.2

Applicazione web basata su FastAPI e MySQL per la generazione automatizzata e il salvataggio di menù settimanali.

## Struttura del Progetto (Tree)
```text  
.
├── docker-compose.yml
├── Dockerfile
├── main.py
├── requirements.txt
├── .env
├── src/
│   ├── init.py
│   ├── database.py       # ORM Models (SQLAlchemy)
│   ├── enums.py          # Definizione Enum (Stagioni, Tipologie, Proteine)
│   ├── piatto.py         # Modello Pydantic Piatto
│   ├── piatto_manuale.py # Modello Pydantic PiattoManuale
│   ├── richiesta_menu.py # Modello Pydantic Richiesta
│   ├── router.py         # FastAPI Endpoints
│   ├── service.py        # Logica di business (Generazione Menù)
│   └── popola_db.py      # Script di inizializzazione DB
└── static/del Progetto (Tree)
text ''
├── index.html
└── piatti.html
```

## 1. Panoramica dell'Architettura
L'applicazione segue un pattern modulare ed è containerizzata tramite Docker.
- **Core (FastAPI):** Gestisce il routing delle API e la logica di business.
- **Data (SQLAlchemy):** Gestisce la persistenza su MySQL.
- **Frontend (HTML/JS):** Interfaccia utente per la configurazione.

## 2. Specifiche Tecniche e Porte
| Servizio | Porta Host | Porta Container | Descrizione |
| :--- | :--- | :--- | :--- |
| **App** | 8000 | 8000 | Endpoint API e frontend |
| **DB** | 3306 | 3306 | Database MySQL |

## 3. Logica di Generazione Menù
L'algoritmo (in `src/service.py`) opera in tre fasi:
1. **Analisi:** Lettura frequenze proteine dal database.
2. **Selezione:** Filtro dei piatti per stagionalità, tempo di preparazione e vincoli.
3. **Binding:** Inserimento dei `pasti_bloccati` (forzature manuali dell'utente).

## 4. Punti Critici e Fragilità
- **Enum Binding:** Modificare `src/enums.py` senza aggiornare il database causa errori di `KeyError`.
- **Sequenza di Boot:** Il container `app` esegue `popola_db.py` all'avvio. Un DB non pronto blocca l'intero processo.
- **Integrità Referenziale:** La cancellazione di un piatto salvato in uno storico menù viola le Foreign Keys.

## 5. Note per Ansible e Automazione
- **Deployment:** Assicurarsi che le variabili d'ambiente nel file `.env` siano correttamente iniettate o gestite via vault.
- **Persistenza:** È necessario mappare il volume `/var/lib/mysql` su un path host permanente prima di andare in produzione.
- **Healthcheck:** Utilizzare l'endpoint `/health` (da implementare) per verificare la disponibilità del servizio prima di concludere il rollout.
