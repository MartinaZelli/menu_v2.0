import os
from typing import Iterator

from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker, relationship

# --- CONFIGURAZIONE DINAMICA TRAMITE VARIABILI D'AMBIENTE ---
# Se le variabili d'ambiente non sono presenti nel sistema (es. quando esegui in locale),
# verranno utilizzati i valori di default preesistenti ("db", "menu", "menu", "menu_progetto").
DB_HOST = os.environ.get("DB_HOST", "db")
DB_USER = os.environ.get("DB_USER", "menu")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "menu")
DB_PORT = os.environ.get("DB_PORT", "3306")
DB_NAME = os.environ.get("DB_NAME", "menu_progetto")

# Costruzione dinamica dell'URL di connessione per SQLAlchemy
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

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

# Setup finale dell'engine con l'URL dinamico
engine = create_engine(DATABASE_URL)
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
