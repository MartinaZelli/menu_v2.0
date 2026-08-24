from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import src.service
from src.database import PiattoDB, get_db
from src.piatto import Piatto, PiattoCreate
from src.richiesta_menu import Richiesta
from src.risposta_menu import Risposta

router = APIRouter(
    prefix="/menu",
    tags=["menu"]
)

# Nota sulle firme: questi endpoint sono "def" e non "async def".
# Le chiamate a SQLAlchemy sono I/O BLOCCANTE: dentro una funzione async
# bloccherebbero l'event loop di uvicorn, e con esso ogni altra richiesta in
# corso, compresi gli endpoint di health. FastAPI esegue automaticamente gli
# endpoint dichiarati "def" in un threadpool separato, dove il blocco e'
# innocuo. L'API esposta e' identica: cambia solo dove viene eseguito il codice.


@router.post("")
def genera_menu(richiesta: Richiesta, db: Session = Depends(get_db)) -> Risposta:
    return src.service.genera_menu_ordinato(db, richiesta)


@router.post("/salva")
def salva_menu(risposta: Risposta, db: Session = Depends(get_db)) -> Dict[str, str]:
    successo = src.service.salva_menu_settimanale(db, risposta)
    if not successo:
        raise HTTPException(status_code=500, detail="Errore nel salvataggio del menu")
    return {"status": "success", "message": "Menu salvato con successo"}


@router.get("/elenco-piatti", response_model=List[Piatto])
def ottieni_piatti(db: Session = Depends(get_db)) -> List[PiattoDB]:
    return db.query(PiattoDB).all()


def _valore(campo: object) -> object:
    """Estrae il valore di un enum, lasciando intatto tutto il resto.

    Le colonne sono String, non Enum SQL: nel database finiscono le stringhe.
    """
    return campo.value if hasattr(campo, "value") else campo


@router.post("/aggiungi-piatto")
def aggiungi_piatto(piatto: PiattoCreate, db: Session = Depends(get_db)) -> Dict[str, str]:
    try:
        nuovo = PiattoDB(
            nome=piatto.nome,
            proteina=_valore(piatto.proteina),
            stagione=_valore(piatto.stagione),
            tempo=piatto.tempo,
            adatto_al_lavoro=piatto.adatto_al_lavoro,
            # La tipologia inviata dal client veniva scartata e sostituita da
            # "primo" fisso: ogni piatto aggiunto dall'interfaccia risultava un
            # primo, qualunque cosa fosse.
            tipologia=_valore(piatto.tipologia),
        )
        db.add(nuovo)
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/elimina-piatto/{id}")
def elimina_piatto(id: int, db: Session = Depends(get_db)) -> Dict[str, str]:
    try:
        righe = db.query(PiattoDB).filter(PiattoDB.id == id).delete()
        # Il valore di ritorno di .delete() veniva ignorato: eliminare un id
        # inesistente rispondeva 200 {"status": "deleted"} senza aver cancellato
        # nulla, e il frontend ricaricava una lista identica senza spiegazioni.
        if righe == 0:
            db.rollback()
            raise HTTPException(status_code=404, detail=f"Nessun piatto con id {id}.")
        db.commit()
    except IntegrityError as e:
        # PastoSalvatoDB.piatto_id e' una foreign key senza ON DELETE: un
        # piatto gia' usato in un menu salvato non e' cancellabile.
        #
        # 409 e non 500: non e' un guasto dell'applicazione, e' una richiesta
        # in conflitto con lo stato attuale dei dati, e il messaggio deve
        # dirlo in modo comprensibile invece di esporre un errore SQL.
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(f"Il piatto {id} compare in uno o piu' menu salvati e non "
                    f"puo' essere eliminato."),
        ) from e

    return {"status": "deleted"}
