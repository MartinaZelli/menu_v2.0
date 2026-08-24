import sys
import time
import os
from typing import Any, Dict, List

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

try:
    # Questi import stanno DENTRO il try di proposito: se PYTHONPATH non
    # include la radice del progetto falliscono, e senza questo blocco
    # l'utente vedrebbe un traceback grezzo invece di un messaggio utile.
    # Nei due laboratori il PYTHONPATH=/app e' proprio cio' che li fa
    # funzionare, dato che lo script viene eseguito da /app/popola_db/.
    from data_piatti import PIATTI_DATA
    from src.database import Base, PiattoDB, MacroDB, PastoSalvatoDB
    from src.enums import Proteina
except ImportError as e:
    print(f"Errore: Non riesco a trovare i moduli. Dettaglio: {e}")
    print("Suggerimento: esegui con PYTHONPATH puntato alla radice del progetto.")
    sys.exit(1)

# --- CONFIGURAZIONE DINAMICA TRAMITE VARIABILI D'AMBIENTE ---
# Se le variabili d'ambiente non sono configurate nel sistema,
# l'applicazione userà i vecchi valori di default per retrocompatibilità in locale.
DB_HOST = os.environ.get("DB_HOST", "db")
DB_USER = os.environ.get("DB_USER", "menu")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "menu")
DB_PORT = os.environ.get("DB_PORT", "3306")
DB_NAME = os.environ.get("DB_NAME", "menu_progetto")

# Ricostruiamo l'URL di connessione di SQLAlchemy in modo dinamico
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Frequenze settimanali desiderate per proteina.
# Nota: la somma e' 18 su 14 slot settimanali, quindi il pool viene troncato
# dal servizio e non tutte le frequenze sono soddisfatte a ogni generazione.
MACRO_DESIDERATE: List[Dict[str, Any]] = [
    {"proteina": Proteina.LEGUMI.value, "frequenza": 3},
    {"proteina": Proteina.LATTICINI.value, "frequenza": 4},
    {"proteina": Proteina.CARNE_BIANCA.value, "frequenza": 4},
    {"proteina": Proteina.CARNE_ROSSA.value, "frequenza": 1},
    {"proteina": Proteina.PESCE.value, "frequenza": 3},
    {"proteina": Proteina.UOVA.value, "frequenza": 3},
]


def attendi_database(engine: Engine, tentativi: int = 10, attesa: int = 5) -> bool:
    """Attende che il database accetti connessioni.

    Il nome conta: chiamandola test_* pytest la raccoglierebbe come test.
    """
    print(f"Inizializzazione database via {DB_HOST}...")

    for i in range(tentativi):
        try:
            with engine.connect() as connection:
                # Eseguiamo una query di test per verificare la reale operatività
                connection.execute(text("SELECT 1"))
                print("Connessione stabilita con successo!")
                return True
        except Exception as e:
            print(f"Tentativo {i+1}/{tentativi}: DB su {DB_HOST} non pronto... (Errore: {e})")
            time.sleep(attesa)

    return False


def sincronizza(
    session: Session,
    piatti_desiderati: List[Dict[str, Any]],
    macro_desiderate: List[Dict[str, Any]],
    svuota_storico: bool = True,
) -> None:
    """Allinea il contenuto del database allo stato descritto dal dataset.

    Non e' un semplice "inserisci tutto": aggiorna i record esistenti,
    aggiunge i nuovi e cancella quelli non piu' presenti nel dataset.

    Riceve la sessione dall'esterno e non la chiude: chi apre chiude.
    Non cattura le eccezioni: la gestione (rollback, uscita) spetta al
    chiamante, che e' anche l'unico a sapere se siamo in un test o in
    produzione.
    """
    # 0. PULIZIA TOTALE DEI MENU SALVATI
    if svuota_storico:
        num_deleted = session.query(PastoSalvatoDB).delete()
        if num_deleted > 0:
            print(f"Storico menu salvati ({num_deleted} record) rimosso.")

    # 1. Sincronizzazione Macro
    macro_db = session.query(MacroDB).all()
    nomi_macro_db = {m.proteina: m for m in macro_db}

    for m_data in macro_desiderate:
        if m_data["proteina"] in nomi_macro_db:
            nomi_macro_db[m_data["proteina"]].frequenza = m_data["frequenza"]
        else:
            session.add(MacroDB(**m_data))

    # Carica piatti esistenti
    piatti_db = session.query(PiattoDB).all()
    nomi_db = {p.nome: p for p in piatti_db}
    nomi_desiderati = [p["nome"] for p in piatti_desiderati]

    # 2. Eliminazione piatti non più presenti
    for nome, piatto_obj in nomi_db.items():
        if nome not in nomi_desiderati:
            print(f"Eliminazione piatto obsoleto: {nome}")
            session.delete(piatto_obj)

    # 3. Inserimento/Aggiornamento
    for p_data in piatti_desiderati:
        if p_data["nome"] in nomi_db:
            p_db = nomi_db[p_data["nome"]]
            p_db.tempo = p_data["tempo"]
            p_db.adatto_al_lavoro = p_data["adatto_al_lavoro"]
            p_db.proteina = p_data["proteina"]
            p_db.tipologia = p_data["tipologia"]
            p_db.stagione = p_data["stagione"]
        else:
            print(f"Aggiunta nuovo piatto: {p_data['nome']}")
            session.add(PiattoDB(**p_data))

    session.commit()


def popola_db() -> None:
    print(f"Configurazione connessione sul DB remoto -> {DB_HOST}:{DB_PORT}")
    engine = create_engine(DATABASE_URL)

    if not attendi_database(engine):
        print("Errore critico: Impossibile connettersi al Database dopo 10 tentativi.")
        sys.exit(1)

    Base.metadata.create_all(engine)
    SessionLocale = sessionmaker(bind=engine)
    session = SessionLocale()

    try:
        sincronizza(session, PIATTI_DATA, MACRO_DESIDERATE)
        print("Sincronizzazione database completata.")
    except Exception as e:
        session.rollback()
        print(f"Errore durante il popolamento: {e}")
    finally:
        session.close()


if __name__ == "__main__":
    popola_db()
