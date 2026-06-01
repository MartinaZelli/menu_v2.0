from typing import Optional

from pydantic import BaseModel
from src.enums import Tipologia, Stagione, Proteina


class Piatto(BaseModel):
    id : int
    nome : str
    descrizione : Optional[str] = None
    proteina : Optional[Proteina] = None
    stagione : Stagione = Stagione.GENERICO
    tempo : int
    adatto_al_lavoro : bool
    tipologia : Tipologia = Tipologia.UNICO
    model_config = {"from_attributes": True}
    