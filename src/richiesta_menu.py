from datetime import date

from pydantic import BaseModel  # <--- Fondamentale

from src.enums import GIORNI_LAVORATIVI_DEFAULT, Giorni_settimana, Stagione
from src.piatto_manuale import PiattoManuale


class Richiesta(BaseModel):  # <--- Eredita da BaseModel
    stagioni: list[Stagione] | None = None
    tempo_massimo: int = 1000
    data_inizio_settimana: date | None = None
    giorni_lavorativi: list[Giorni_settimana] = GIORNI_LAVORATIVI_DEFAULT
    pasti_bloccati: list[PiattoManuale] | None = None
