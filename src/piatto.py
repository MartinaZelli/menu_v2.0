from typing import Optional

from pydantic import BaseModel

from src.enums import Proteina, Stagione, Tipologia


class PiattoBase(BaseModel):
    """Campi comuni a un piatto, indipendenti dal fatto che esista gia'."""

    nome: str
    descrizione: Optional[str] = None
    proteina: Optional[Proteina] = None
    # stagione e tipologia sono Optional pur avendo un default.
    #
    # In Pydantic il default si applica quando il campo e' ASSENTE, non quando
    # vale None. Le colonne corrispondenti non hanno nullable=False, quindi una
    # riga con stagione NULL e' possibile: senza Optional, model_validate
    # solleverebbe e - dato che l'endpoint dichiara response_model=List[Piatto] -
    # farebbe fallire con un 500 l'INTERA risposta di /menu/elenco-piatti, che
    # e' la verifica end-to-end documentata nei due laboratori.
    stagione: Optional[Stagione] = Stagione.GENERICO
    tempo: int
    adatto_al_lavoro: bool
    tipologia: Optional[Tipologia] = Tipologia.UNICO

    model_config = {"from_attributes": True}


class Piatto(PiattoBase):
    """Piatto gia' presente in archivio, quindi con un id.

    L'id resta obbligatorio: src/service.py lo confronta con il valore
    sentinella 999 per riconoscere i segnaposto, e il frontend lo usa per
    costruire i pasti bloccati.
    """

    id: int


class PiattoCreate(PiattoBase):
    """Piatto da creare: non ha ancora un id, glielo assegna il database.

    Prima l'endpoint di inserimento accettava Piatto, quindi pretendeva un id
    per una riga che ancora non esisteva; il frontend aggirava il vincolo
    inviando id: 0.

    Pydantic ignora i campi in piu', quindi un client che continua a mandare
    "id" non riceve errori: la modifica e' retrocompatibile e non richiede di
    aggiornare frontend e backend insieme.
    """
