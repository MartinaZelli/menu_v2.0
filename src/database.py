from collections.abc import Iterator

from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

from src.config import DATABASE_URL

Base = declarative_base()

# --- TABELLA MACRO ---
class MacroDB(Base):
    __tablename__ = "macro"
    id = Column(Integer, primary_key=True, index=True)
    # MySQL richiede una lunghezza per le colonne UNIQUE
    proteina = Column(String(50), unique=True)
    frequenza = Column(Integer)

# --- TABELLA PIATTO ---
class PiattoDB(Base):
    __tablename__ = "piatti"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255))
    proteina = Column(String(50))
    stagione = Column(String(50))
    tempo = Column(Integer)
    adatto_al_lavoro = Column(Boolean)
    tipologia = Column(String(50))

# --- TABELLA TOTALE (Settimana) ---
class SettimanaDB(Base):
    __tablename__ = "settimane"
    id = Column(Integer, primary_key=True, index=True)
    data_inizio = Column(Date, unique=True)
    pasti = relationship("PastoSalvatoDB", back_populates="settimana")

# --- TABELLA PASTI SALVATI ---
class PastoSalvatoDB(Base):
    __tablename__ = "pasti_salvati"
    id = Column(Integer, primary_key=True, index=True)
    settimana_id = Column(Integer, ForeignKey("settimane.id"))
    giorno = Column(String(20))
    momento = Column(String(20))
    piatto_id = Column(Integer, ForeignKey("piatti.id"))
    nome_manuale = Column(String(255), nullable=True)

    settimana = relationship("SettimanaDB", back_populates="pasti")
    piatto = relationship("PiattoDB")

# Setup finale dell'engine con l'URL dinamico.
#
# pool_pre_ping: prima di riusare una connessione dal pool, SQLAlchemy manda un
#   ping. MySQL chiude le connessioni inattive dopo wait_timeout (default 8 ore),
#   quindi senza questo un contenitore fermo tutta la notte risponde
#   "MySQL server has gone away" alla prima richiesta del mattino.
# pool_recycle: ricicla le connessioni piu' vecchie di un'ora, prima che sia il
#   server a chiuderle.
# connect_timeout: senza un limite esplicito, un database irraggiungibile tiene
#   appesa la richiesta per la durata del timeout di sistema. Serve soprattutto
#   all'endpoint di readiness, che deve dare una risposta rapida.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={"connect_timeout": 3},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Iterator[Session]:
    """Fornisce una sessione del database agli endpoint FastAPI.

    E' una "dependency": FastAPI la esegue prima di ogni richiesta, passa il
    valore prodotto da yield all'endpoint, e alla fine della richiesta riprende
    l'esecuzione da dopo lo yield per eseguire il finally.

    Il vantaggio rispetto ad aprire SessionLocal() dentro ogni endpoint e' che
    la chiusura e' garantita in un punto solo, e che nei test si puo'
    sostituire l'intera funzione con app.dependency_overrides[get_db], senza
    toccare ne' l'engine ne' i moduli.

    Regola che ne consegue: chi apre chiude. Gli endpoint e i service ricevono
    una sessione gia' aperta e NON devono chiamare db.close().
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
