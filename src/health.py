"""Endpoint di salute, pensati per le sonde di Kubernetes.

Sono due e non uno, perche' rispondono a due domande diverse e Kubernetes
reagisce in modo opposto:

    /health/live   "il processo e' vivo?"        fallisce -> UCCIDE e riavvia
    /health/ready  "posso ricevere traffico?"    fallisce -> toglie dal Service

La distinzione non e' formale. Se il controllo del database stesse nella
liveness, trenta secondi di database irraggiungibile farebbero riavviare in
ciclo tutte le repliche: si aggiunge carico a un database gia' in sofferenza,
e riavviare l'applicazione non ripara il database. Stando nella readiness, i
pod restano vivi, smettono di ricevere richieste e vi rientrano da soli
appena il database torna.

Nota sulle firme: sono "def" e non "async def". Un SELECT 1 bloccante dentro
una funzione async bloccherebbe l'event loop per tutta la durata del timeout
di connessione, e in quella finestra anche /health/live smetterebbe di
rispondere: kubelet ucciderebbe il pod, cioe' esattamente il disastro che la
separazione dei due endpoint serve a evitare.
"""
from typing import Dict

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.database import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def liveness() -> Dict[str, str]:
    """Non tocca il database di proposito: vedi il commento in testa al modulo."""
    return {"status": "alive"}


@router.get("/ready")
def readiness(response: Response, db: Session = Depends(get_db)) -> Dict[str, str]:
    """Verifica che il database risponda davvero.

    Il controllo e' un SELECT 1 e non un conteggio dei piatti: "database
    irraggiungibile" e "database vuoto perche' il popolamento non e' ancora
    stato eseguito" sono due problemi diversi, con due rimedi diversi, e
    confonderli renderebbe la diagnosi piu' difficile.

    Restituisce 503 e non 500: non e' un errore dell'applicazione, e' una
    dichiarazione di non disponibilita' temporanea.
    """
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unready", "dettaglio": type(e).__name__}
    return {"status": "ready"}
