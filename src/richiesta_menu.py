from datetime import date
from typing import List, Optional
from pydantic import BaseModel  # <--- Fondamentale
from src.piatto_manuale import PiattoManuale
from src.enums import GIORNI_LAVORATIVI_DEFAULT, Giorni_settimana, Stagione

class Richiesta(BaseModel):  # <--- Eredita da BaseModel
    stagioni: Optional[List[Stagione]] = None
    tempo_massimo: int = 1000
    data_inizio_settimana: Optional[date] = None
    giorni_lavorativi: List[Giorni_settimana] = GIORNI_LAVORATIVI_DEFAULT
    pasti_bloccati: Optional[List[PiattoManuale]] = None
