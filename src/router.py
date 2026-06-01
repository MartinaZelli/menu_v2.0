from typing import List
from fastapi import APIRouter, HTTPException
from src.database import SessionLocal, PiattoDB  
from src.risposta_menu import Risposta
from src.richiesta_menu import Richiesta
from src.piatto import Piatto 
import src.service

router = APIRouter(
    prefix="/menu",
    tags=["menu"]
)

@router.post("") 
async def genera_menu(richiesta: Richiesta) -> Risposta: 
    # La logica ora è interamente gestita dentro genera_menu_ordinato
    # che apre e chiude la connessione al database autonomamente
    risultato = src.service.genera_menu_ordinato(richiesta)
    return risultato

@router.post("/salva")
async def salva_menu(risposta: Risposta):
    successo = src.service.salva_menu_settimanale(risposta)
    if not successo:
        raise HTTPException(status_code=500, detail="Errore nel salvataggio del menu")
    return {"status": "success", "message": "Menu salvato con successo"}

# Endpoint per ottenere tutti i piatti
@router.get("/elenco-piatti", response_model=List[Piatto])
async def ottieni_piatti():
    db = SessionLocal()
    try:
        piatti = db.query(PiattoDB).all()
        return piatti
    finally:
        db.close()

# Endpoint per aggiungere un nuovo piatto
@router.post("/aggiungi-piatto")
async def aggiungi_piatto(piatto: Piatto):
    db = SessionLocal()
    try:
        # Stampiamo i dati in console per vedere se arrivano dal frontend
        print(f"Ricevuto piatto: {piatto.nome}") 
        
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
        print(f"Errore aggiunta piatto: {e}") # Questo apparirà nel terminale di Uvicorn
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# Endpoint per eliminare un piatto
@router.delete("/elimina-piatto/{id}")
async def elimina_piatto(id: int):
    db = SessionLocal()
    try:
        db.query(PiattoDB).filter(PiattoDB.id == id).delete()
        db.commit()
        return {"status": "deleted"}
    finally:
        db.close()