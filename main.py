from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from src.router import router as menu_router
from src import router
import uvicorn


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permette chiamate da qualsiasi indirizzo (perfetto per sviluppo)
    allow_methods=["*"],  # Permette tutti i metodi (GET, POST, ecc.)
    allow_headers=["*"],  # Permette tutti gli header
)
app.include_router(router.router)
app.mount("/", StaticFiles(directory="static"), name="static")

def main():
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()


