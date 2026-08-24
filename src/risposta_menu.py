from datetime import date

from pydantic import BaseModel

from src.enums import Giorni_settimana
from src.piatto import Piatto


class Pasti(BaseModel):
    pranzo : list[Piatto] = []
    cena : list[Piatto] = []

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
                  
