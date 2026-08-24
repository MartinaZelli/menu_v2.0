from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database import get_db, PiattoDB
from src.risposta_menu import Risposta
from src.richiesta_menu import Richiesta
from src.piatto import Piatto
import src.service

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


@router.post("/aggiungi-piatto")
def aggiungi_piatto(piatto: Piatto, db: Session = Depends(get_db)) -> Dict[str, str]:
    try:
        nuovo = PiattoDB(
            nome=piatto.nome,
            proteina=piatto.proteina.value if hasattr(piatto.proteina, 'value') else piatto.proteina,
            stagione=piatto.stagione.value if hasattr(piatto.stagione, 'value') else piatto.stagione,
            tempo=piatto.tempo,
            adatto_al_lavoro=piatto.adatto_al_lavoro,
            tipologia="primo" # Assicurati che questo campo esista nel tuo PiattoDB
        )
        db.add(nuovo)
        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        print(f"Errore aggiunta piatto: {e}")  # sostituito da logging nella fase 3
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/elimina-piatto/{id}")
def elimina_piatto(id: int, db: Session = Depends(get_db)) -> Dict[str, str]:
    db.query(PiattoDB).filter(PiattoDB.id == id).delete()
    db.commit()
    return {"status": "deleted"}
