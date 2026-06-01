import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Configurazione diretta per MySQL (User: menu, Pass: menu, Host: db)
DATABASE_URL = "mysql+pymysql://menu:menu@db/menu_progetto"
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

# Setup finale
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)