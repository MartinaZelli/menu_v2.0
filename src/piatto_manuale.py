from pydantic import BaseModel
from src.piatto import Piatto

# Definiamo cosa riceve il server per ogni piatto manuale
class PiattoManuale(BaseModel):
    giorno: str  # "lunedi", "martedi", etc.
    momento: str # "pranzo" o "cena"
    piatto: Piatto # L'oggetto piatto completo o creato dall'utente