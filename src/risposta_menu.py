from datetime import date
from typing import Dict, List

from pydantic import BaseModel

from src.piatto import Piatto
from src.enums import Giorni_settimana

class Pasti(BaseModel):
    pranzo : List[Piatto] = []
    cena : List[Piatto] = []

class Pasti_settimana(BaseModel):
    lunedi: Pasti
    martedi: Pasti
    mercoledi: Pasti
    giovedi: Pasti
    venerdi: Pasti
    sabato: Pasti
    domenica: Pasti

class Risposta(BaseModel):
    giorno_inizio_settimana : Giorni_settimana = Giorni_settimana.LUNEDI
    data_inizio_settimana : date
    tabella : Pasti_settimana
                  
