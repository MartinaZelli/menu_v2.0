import sys
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path

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

# --- CONFIGURAZIONE OVERRIDE PER ESECUZIONE DA PC ---
LOCAL_DATABASE_URL = "mysql+pymysql://menu:menu@db:3306/menu_progetto"

engine_local = create_engine(LOCAL_DATABASE_URL)
SessionOverride = sessionmaker(autocommit=False, autoflush=False, bind=engine_local)

def popola():
    print("Inizializzazione database via Localhost...")

    db_connesso = False
    for i in range(10):
        try:
            with engine_local.connect() as connection:
                print("Connessione stabilita.")
                db_connesso = True
                break
        except Exception:
            print(f"Tentativo {i+1}: DB non pronto, attesa...")
            time.sleep(5)

    if not db_connesso:
        sys.exit(1)

    # 1. CANCELLAZIONE TOTALE
    # Questo elimina fisicamente tutte le tabelle definite in 'Base' dal database
    print("Eliminazione di tutte le tabelle esistenti...")
    Base.metadata.drop_all(bind=engine_local)

    # 2. RICREAZIONE SCHEMA
    # Crea nuovamente le tabelle vuote basandosi sui modelli SQLAlchemy
    print("Ricreazione schema database...")
    Base.metadata.create_all(bind=engine_local)

    db = SessionOverride()

    try:

        # --- 2. IMPORTA MACRO ---
        print("Importazione frequenze macro...")
        frequenze = [
            MacroDB(proteina=Proteina.LEGUMI.value, frequenza=3),
            MacroDB(proteina=Proteina.LATTICINI.value, frequenza=4),
            MacroDB(proteina=Proteina.CARNE_BIANCA.value, frequenza=4),
            MacroDB(proteina=Proteina.CARNE_ROSSA.value, frequenza=1),
            MacroDB(proteina=Proteina.PESCE.value, frequenza=3),
            MacroDB(proteina=Proteina.UOVA.value, frequenza=3),
        ]
        db.add_all(frequenze)

        # --- 3. IMPORTA PIATTI ---
        print("Importazione ricettario...")
        lista_piatti = [
            # LATTICINI
            PiattoDB(nome="Pasta al pomodoro e mozzarella", tempo=30, adatto_al_lavoro=False, proteina=Proteina.LATTICINI.value, tipologia=Tipologia.PRIMO.value, stagione=Stagione.GENERICO.value),
            PiattoDB(nome="Tomino alla piastra", tempo=5, adatto_al_lavoro=True, proteina=Proteina.LATTICINI.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.GENERICO.value),
            PiattoDB(nome="Insalata greca", tempo=10, adatto_al_lavoro=True, proteina=Proteina.LATTICINI.value, tipologia=Tipologia.UNICO.value, stagione=Stagione.ESTATE.value),
            PiattoDB(nome="Gnocchi al gorgonzola", tempo=15, adatto_al_lavoro=False, proteina=Proteina.LATTICINI.value, tipologia=Tipologia.PRIMO.value, stagione=Stagione.INVERNO.value),
            PiattoDB(nome="Pasta fredda tricolore", tempo=20, adatto_al_lavoro=True, proteina=Proteina.LATTICINI.value, tipologia=Tipologia.PRIMO.value, stagione=Stagione.ESTATE.value),
            PiattoDB(nome="Ricotta fresca e mieie", tempo=5, adatto_al_lavoro=True, proteina=Proteina.LATTICINI.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.ESTATE.value),

            # LEGUMI
            PiattoDB(nome="Minestrone di verdure", tempo=40, adatto_al_lavoro=False, proteina=Proteina.LEGUMI.value, tipologia=Tipologia.PRIMO.value, stagione=Stagione.INVERNO.value),
            PiattoDB(nome="Insalata di ceci e tonno", tempo=10, adatto_al_lavoro=True, proteina=Proteina.LEGUMI.value, tipologia=Tipologia.UNICO.value, stagione=Stagione.ESTATE.value),
            PiattoDB(nome="Lenticchie in umido", tempo=45, adatto_al_lavoro=True, proteina=Proteina.LEGUMI.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.INVERNO.value),
            PiattoDB(nome="Polpette di soia", tempo=20, adatto_al_lavoro=True, proteina=Proteina.LEGUMI.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.GENERICO.value),
            PiattoDB(nome="Quinoa con verdure", tempo=25, adatto_al_lavoro=True, proteina=Proteina.LEGUMI.value, tipologia=Tipologia.UNICO.value, stagione=Stagione.GENERICO.value),
            PiattoDB(nome="Fagioli all'uccelletto", tempo=30, adatto_al_lavoro=True, proteina=Proteina.LEGUMI.value, tipologia=Tipologia.CONTORNO.value, stagione=Stagione.GENERICO.value),
            PiattoDB(nome="Hummus con cruditè", tempo=15, adatto_al_lavoro=True, proteina=Proteina.LEGUMI.value, tipologia=Tipologia.UNICO.value, stagione=Stagione.GENERICO.value),
            PiattoDB(nome="Zuppa di farro e lenticchie", tempo=40, adatto_al_lavoro=True, proteina=Proteina.LEGUMI.value, tipologia=Tipologia.UNICO.value, stagione=Stagione.INVERNO.value),
            PiattoDB(nome="Zuppa di piselli freschi", tempo=30, adatto_al_lavoro=False, proteina=Proteina.LEGUMI.value, tipologia=Tipologia.PRIMO.value, stagione=Stagione.MEZZA.value),

            # CARNE BIANCA
            PiattoDB(nome="Hamburger di pollo", tempo=10, adatto_al_lavoro=True, proteina=Proteina.CARNE_BIANCA.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.GENERICO.value),
            PiattoDB(nome="Spiedini di tacchino", tempo=15, adatto_al_lavoro=True, proteina=Proteina.CARNE_BIANCA.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.GENERICO.value),
            PiattoDB(nome="Scaloppine al limone", tempo=15, adatto_al_lavoro=True, proteina=Proteina.CARNE_BIANCA.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.GENERICO.value),
            PiattoDB(nome="Insalata di pollo e mele", tempo=15, adatto_al_lavoro=True, proteina=Proteina.CARNE_BIANCA.value, tipologia=Tipologia.UNICO.value, stagione=Stagione.ESTATE.value),
            PiattoDB(nome="Pollo al curry", tempo=25, adatto_al_lavoro=True, proteina=Proteina.CARNE_BIANCA.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.INVERNO.value),
            PiattoDB(nome="Tacchino alle erbe", tempo=15, adatto_al_lavoro=True, proteina=Proteina.CARNE_BIANCA.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.MEZZA.value),
            PiattoDB(nome="Bocconcini di pollo ai funghi", tempo=20, adatto_al_lavoro=True, proteina=Proteina.CARNE_BIANCA.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.INVERNO.value),

            # CARNE ROSSA
            PiattoDB(nome="Spezzatino di manzo", tempo=90, adatto_al_lavoro=False, proteina=Proteina.CARNE_ROSSA.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.INVERNO.value),
            PiattoDB(nome="Straccetti di vitello", tempo=10, adatto_al_lavoro=True, proteina=Proteina.CARNE_ROSSA.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.GENERICO.value),
            PiattoDB(nome="Bistecca ai ferri", tempo=8, adatto_al_lavoro=False, proteina=Proteina.CARNE_ROSSA.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.GENERICO.value),
            PiattoDB(nome="Polpette al sugo", tempo=35, adatto_al_lavoro=False, proteina=Proteina.CARNE_ROSSA.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.INVERNO.value),
            PiattoDB(nome="Carpaccio di bresaola", tempo=5, adatto_al_lavoro=True, proteina=Proteina.CARNE_ROSSA.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.ESTATE.value),
            PiattoDB(nome="Tagliata di manzo e rucola", tempo=12, adatto_al_lavoro=False, proteina=Proteina.CARNE_ROSSA.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.MEZZA.value),

            # PESCE
            PiattoDB(nome="Salmone al vapore", tempo=15, adatto_al_lavoro=True, proteina=Proteina.PESCE.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.GENERICO.value),
            PiattoDB(nome="Baccalà alla livornese", tempo=40, adatto_al_lavoro=False, proteina=Proteina.PESCE.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.GENERICO.value),
            PiattoDB(nome="Branzino al sale", tempo=35, adatto_al_lavoro=False, proteina=Proteina.PESCE.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.GENERICO.value),
            PiattoDB(nome="Cous cous di pesce", tempo=30, adatto_al_lavoro=True, proteina=Proteina.PESCE.value, tipologia=Tipologia.UNICO.value, stagione=Stagione.ESTATE.value),
            # CORREZIONE QUI: Tipologia.SECONDO invece di Tipologia.MEZZA
            PiattoDB(nome="Sogliola alla mugnaia", tempo=10, adatto_al_lavoro=True, proteina=Proteina.PESCE.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.MEZZA.value),
            PiattoDB(nome="Zuppa di pesce", tempo=50, adatto_al_lavoro=False, proteina=Proteina.PESCE.value, tipologia=Tipologia.UNICO.value, stagione=Stagione.INVERNO.value),
            PiattoDB(nome="Filetto di orata al forno", tempo=20, adatto_al_lavoro=False, proteina=Proteina.PESCE.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.GENERICO.value),

            # UOVA
            PiattoDB(nome="Frittata alle erbe", tempo=15, adatto_al_lavoro=True, proteina=Proteina.UOVA.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.GENERICO.value),
            PiattoDB(nome="Pasta alla carbonara", tempo=20, adatto_al_lavoro=False, proteina=Proteina.UOVA.value, tipologia=Tipologia.PRIMO.value, stagione=Stagione.GENERICO.value),
            PiattoDB(nome="Uova in purgatorio", tempo=15, adatto_al_lavoro=False, proteina=Proteina.UOVA.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.GENERICO.value),
            PiattoDB(nome="Omelette al formaggio", tempo=10, adatto_al_lavoro=False, proteina=Proteina.UOVA.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.GENERICO.value),
            PiattoDB(nome="Uova sode e asparagi", tempo=15, adatto_al_lavoro=True, proteina=Proteina.UOVA.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.MEZZA.value),
            PiattoDB(nome="Frittata al forno con verdure", tempo=25, adatto_al_lavoro=True, proteina=Proteina.UOVA.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.GENERICO.value),
            PiattoDB(nome="Uova alla coque con crostini", tempo=8, adatto_al_lavoro=False, proteina=Proteina.UOVA.value, tipologia=Tipologia.SECONDO.value, stagione=Stagione.GENERICO.value),
        ]

        db.add_all(lista_piatti)
        db.commit()
        print(f"Completato! Caricati {len(lista_piatti)} piatti.")

    except Exception as e:
        print(f"Errore durante il popolamento: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    popola()
