import sys
import time
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path

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

#engine_local = create_engine(DATABASE_URL)
#SessionOverride = sessionmaker(autocommit=False, autoflush=False, bind=engine_local)

def test_connessione_db():
    print(f"Inizializzazione database via {DB_HOST}...")

    db_connesso = False
    for i in range(10):
        try:
            with engine.connect() as connection:
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

    if not test_connessione_db(engine):
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
    piatti_desiderati = [
          # LATTICINI
            {"nome": "Pasta al pomodoro e mozzarella", "tempo": 30, "adatto_al_lavoro": False, "proteina": Proteina.LATTICINI.value, "tipologia": Tipologia.PRIMO.value, "stagione": Stagione.GENERICO.value},
            {"nome": "Tomino alla piastra", "tempo": 5, "adatto_al_lavoro": True, "proteina": Proteina.LATTICINI.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.GENERICO.value},
            {"nome": "Insalata greca", "tempo": 10, "adatto_al_lavoro": True, "proteina": Proteina.LATTICINI.value, "tipologia": Tipologia.UNICO.value, "stagione": Stagione.ESTATE.value},
            {"nome": "Gnocchi al gorgonzola", "tempo": 15, "adatto_al_lavoro": False, "proteina": Proteina.LATTICINI.value, "tipologia": Tipologia.PRIMO.value, "stagione": Stagione.INVERNO.value},
            {"nome": "Pasta fredda tricolore", "tempo": 20, "adatto_al_lavoro": True, "proteina": Proteina.LATTICINI.value, "tipologia": Tipologia.PRIMO.value, "stagione": Stagione.ESTATE.value},
            {"nome": "Ricotta fresca e mieie", "tempo": 5, "adatto_al_lavoro": True, "proteina": Proteina.LATTICINI.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.ESTATE.value},

            # LEGUMI
            {"nome": "Minestrone di verdure", "tempo": 40, "adatto_al_lavoro": False, "proteina": Proteina.LEGUMI.value, "tipologia": Tipologia.PRIMO.value, "stagione": Stagione.INVERNO.value},
            {"nome": "Insalata di ceci e tonno", "tempo": 10, "adatto_al_lavoro": True, "proteina": Proteina.LEGUMI.value, "tipologia": Tipologia.UNICO.value, "stagione": Stagione.ESTATE.value},
            {"nome": "Lenticchie in umido", "tempo": 45, "adatto_al_lavoro": True, "proteina": Proteina.LEGUMI.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.INVERNO.value},
            {"nome": "Polpette di soia", "tempo": 20, "adatto_al_lavoro": True, "proteina": Proteina.LEGUMI.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.GENERICO.value},
            {"nome": "Quinoa con verdure", "tempo": 25, "adatto_al_lavoro": True, "proteina": Proteina.LEGUMI.value, "tipologia": Tipologia.UNICO.value, "stagione": Stagione.GENERICO.value},
            {"nome": "Fagioli all'uccelletto", "tempo": 30, "adatto_al_lavoro": True, "proteina": Proteina.LEGUMI.value, "tipologia": Tipologia.CONTORNO.value, "stagione": Stagione.GENERICO.value},
            {"nome": "Hummus con cruditè", "tempo": 15, "adatto_al_lavoro": True, "proteina": Proteina.LEGUMI.value, "tipologia": Tipologia.UNICO.value, "stagione": Stagione.GENERICO.value},
            {"nome": "Zuppa di farro e lenticchie", "tempo": 40, "adatto_al_lavoro": True, "proteina": Proteina.LEGUMI.value, "tipologia": Tipologia.UNICO.value, "stagione": Stagione.INVERNO.value},
            {"nome": "Zuppa di piselli freschi", "tempo": 30, "adatto_al_lavoro": False, "proteina": Proteina.LEGUMI.value, "tipologia": Tipologia.PRIMO.value, "stagione": Stagione.MEZZA.value},

            # CARNE BIANCA
            {"nome": "Hamburger di pollo", "tempo": 10, "adatto_al_lavoro": True, "proteina": Proteina.CARNE_BIANCA.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.GENERICO.value},
            {"nome": "Spiedini di tacchino", "tempo": 15, "adatto_al_lavoro": True, "proteina": Proteina.CARNE_BIANCA.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.GENERICO.value},
            {"nome": "Scaloppine al limone", "tempo": 15, "adatto_al_lavoro": True, "proteina": Proteina.CARNE_BIANCA.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.GENERICO.value},
            {"nome": "Insalata di pollo e mele", "tempo": 15, "adatto_al_lavoro": True, "proteina": Proteina.CARNE_BIANCA.value, "tipologia": Tipologia.UNICO.value, "stagione": Stagione.ESTATE.value},
            {"nome": "Pollo al curry", "tempo": 25, "adatto_al_lavoro": True, "proteina": Proteina.CARNE_BIANCA.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.INVERNO.value},
            {"nome": "Tacchino alle erbe", "tempo": 15, "adatto_al_lavoro": True, "proteina": Proteina.CARNE_BIANCA.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.MEZZA.value},
            {"nome": "Bocconcini di pollo ai funghi", "tempo": 20, "adatto_al_lavoro": True,"proteina": Proteina.CARNE_BIANCA.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.INVERNO.value},

            # CARNE ROSSA
            {"nome": "Spezzatino di manzo", "tempo": 90, "adatto_al_lavoro": False, "proteina": Proteina.CARNE_ROSSA.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.INVERNO.value},
            {"nome": "Straccetti di vitello", "tempo": 10, "adatto_al_lavoro": True, "proteina": Proteina.CARNE_ROSSA.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.GENERICO.value},
            {"nome": "Bistecca ai ferri", "tempo": 8, "adatto_al_lavoro": False, "proteina": Proteina.CARNE_ROSSA.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.GENERICO.value},
            {"nome": "Polpette al sugo", "tempo": 35, "adatto_al_lavoro": False, "proteina": Proteina.CARNE_ROSSA.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.INVERNO.value},
            {"nome": "Carpaccio di bresaola", "tempo": 5, "adatto_al_lavoro": True, "proteina": Proteina.CARNE_ROSSA.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.ESTATE.value},
            {"nome": "Tagliata di manzo e rucola", "tempo": 12, "adatto_al_lavoro": False, "proteina": Proteina.CARNE_ROSSA.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.MEZZA.value},

            # PESCE
            {"nome": "Salmone al vapore", "tempo": 15, "adatto_al_lavoro": True, "proteina": Proteina.PESCE.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.GENERICO.value},
            {"nome": "Baccalà alla livornese", "tempo": 40, "adatto_al_lavoro": False, "proteina": Proteina.PESCE.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.GENERICO.value},
            {"nome": "Branzino al sale", "tempo": 35, "adatto_al_lavoro": False, "proteina": Proteina.PESCE.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.GENERICO.value},
            {"nome": "Cous cous di pesce", "tempo": 30, "adatto_al_lavoro": True, "proteina": Proteina.PESCE.value, "tipologia": Tipologia.UNICO.value, "stagione": Stagione.ESTATE.value},
            {"nome": "Sogliola alla mugnaia", "tempo": 10, "adatto_al_lavoro": True, "proteina": Proteina.PESCE.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.MEZZA.value},
            {"nome": "Zuppa di pesce", "tempo": 50, "adatto_al_lavoro": False, "proteina": Proteina.PESCE.value, "tipologia": Tipologia.UNICO.value, "stagione": Stagione.INVERNO.value},
            {"nome": "Filetto di orata al forno", "tempo": 20, "adatto_al_lavoro": False, "proteina": Proteina.PESCE.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.GENERICO.value},

            # UOVA
            {"nome": "Frittata alle erbe", "tempo": 15, "adatto_al_lavoro": True, "proteina": Proteina.UOVA.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.GENERICO.value},
            {"nome": "Pasta alla carbonara", "tempo": 20, "adatto_al_lavoro": False, "proteina": Proteina.UOVA.value, "tipologia": Tipologia.PRIMO.value, "stagione": Stagione.GENERICO.value},
            {"nome": "Uova in purgatorio", "tempo": 15, "adatto_al_lavoro": False, "proteina": Proteina.UOVA.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.GENERICO.value},
            {"nome": "Omelette al formaggio", "tempo": 10, "adatto_al_lavoro": False, "proteina": Proteina.UOVA.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.GENERICO.value},
            {"nome": "Uova sode e asparagi", "tempo": 15, "adatto_al_lavoro": True, "proteina": Proteina.UOVA.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.MEZZA.value},
            {"nome": "Frittata al forno con verdure", "tempo": 25, "adatto_al_lavoro": True, "proteina": Proteina.UOVA.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.GENERICO.value},
            {"nome": "Uova alla coque con crostini", "tempo": 8, "adatto_al_lavoro": False, "proteina": Proteina.UOVA.value, "tipologia": Tipologia.SECONDO.value, "stagione": Stagione.GENERICO.value},
        ]

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
