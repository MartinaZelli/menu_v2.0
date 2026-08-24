import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src import router
from src.config import CONFIG, stampa_diagnostica, verifica_o_esci

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permette chiamate da qualsiasi indirizzo (perfetto per sviluppo)
    allow_methods=["*"],  # Permette tutti i metodi (GET, POST, ecc.)
    allow_headers=["*"],  # Permette tutti gli header
)
app.include_router(router.router)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

def main() -> None:
    # La diagnostica sta qui e non a livello di modulo perche' verifica_o_esci
    # puo' terminare il processo: eseguirla all'import farebbe fallire anche i
    # test e qualunque strumento che importi main.
    stampa_diagnostica(CONFIG)
    verifica_o_esci(CONFIG)
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
