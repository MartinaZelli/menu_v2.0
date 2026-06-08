import sys
import time
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path
from data_piatti import PIATTI_DATA
from src.database import PastoSalvatoDB

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    # Importiamo le classi e le enumerazioni dai file del progetto
    from src.database import Base, PiattoDB, MacroDB
    from src.enums import Proteina, Stagione, Tipologia
except ImportError as e:
    print(f"Errore: Non riesco a trovare i moduli. Dettaglio: {e}")
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

print(f"Configurazione connessione sul DB remoto -> {DB_HOST}:{DB_PORT}")

engine_local = create_engine(DATABASE_URL)
SessionOverride = sessionmaker(autocommit=False, autoflush=False, bind=engine_local)

def test_connessione_db(engine_local):
    print(f"Inizializzazione database via {DB_HOST}...")

    db_connesso = False
    for i in range(10):
        try:
            with engine_local.connect() as connection:
                print("Connessione stabilita con successo!")
                db_connesso = True
                break
        except Exception as e:
            print(f"Tentativo {i+1}/10: DB su {DB_HOST} non pronto, attesa... (Errore: {e})")
            time.sleep(5)

    if not db_connesso:
        print("Errore critico: Impossibile connettersi al Database dopo 10 tentativi.")
        sys.exit(1)

def popola_db():
    engine = create_engine(DATABASE_URL)

    if not test_connessione_db(engine_local):
        print("Errore critico: Impossibile connettersi al Database dopo 10 tentativi.")
        sys.exit(1)

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    macro_desiderate = [
        {"proteina": Proteina.LEGUMI.value, "frequenza": 3},
        {"proteina": Proteina.LATTICINI.value, "frequenza": 4},
        {"proteina": Proteina.CARNE_BIANCA.value, "frequenza": 4},
        {"proteina": Proteina.CARNE_ROSSA.value, "frequenza": 1},
        {"proteina": Proteina.PESCE.value, "frequenza": 3},
        {"proteina": Proteina.UOVA.value, "frequenza": 3},
    ]
    piatti_desiderati = PIATTI_DATA

    try:
        # 0. PULIZIA TOTALE DEI MENU SALVATI
        # Se vuoi svuotare completamente lo storico dei menu ogni volta che rilanci il popolamento:
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

        # 1. Eliminazione piatti non più presenti
        for nome, piatto_obj in nomi_db.items():
            if nome not in nomi_desiderati:
                print(f"Eliminazione piatto obsoleto: {nome}")
                session.delete(piatto_obj)

        # 2. Inserimento/Aggiornamento
        for p_data in piatti_desiderati:
            if p_data["nome"] in nomi_db:
                # Aggiornamento
                p_db = nomi_db[p_data["nome"]]
                p_db.tempo = p_data["tempo"]
                p_db.adatto_al_lavoro = p_data["adatto_al_lavoro"]
                p_db.proteina = p_data["proteina"]
                p_db.tipologia = p_data["tipologia"]
                p_db.stagione = p_data["stagione"]
            else:
                # Inserimento
                print(f"Aggiunta nuovo piatto: {p_data['nome']}")
                session.add(PiattoDB(**p_data))


        session.commit()
        print("Sincronizzazione database completata.")
    except Exception as e:
        session.rollback()
        print(f"Errore durante il popolamento: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    popola_db()
