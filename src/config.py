"""Configurazione del collegamento al database, in un punto solo.

Prima esisteva in due copie identiche, in src/database.py e in popola_db.py:
modificarne una e dimenticare l'altra era solo questione di tempo.

Il modulo vive in src/ e non nella radice perche' il Dockerfile elenca i file
uno per uno (ADD src /app/src, ADD main.py /app, ...). Un modulo nella radice
non finirebbe nell'immagine e il container morirebbe all'avvio con
ModuleNotFoundError, pur avendo il build funzionante.

I nomi delle variabili d'ambiente NON vanno cambiati: sono il contratto con i
due laboratori, che le iniettano rispettivamente via file .env (Ansible) e via
Secret con envFrom (Kubernetes).
"""
import os
import sys
from typing import NamedTuple

# I default esistono per retrocompatibilita' con l'esecuzione locale, ma non
# corrispondono a nessuno dei due laboratori: Ansible usa il database
# "progetto" con utente "user_progetto", Kubernetes il database "menu" con
# utente "menu_user". Sono default sbagliati *in modo plausibile*: producono
# un errore di connessione o, peggio, una connessione a un database esistente
# ma diverso da quello atteso. Per questo ogni fallback viene segnalato.
DEFAULT = {
    "DB_HOST": "db",
    "DB_PORT": "3306",
    "DB_NAME": "menu_progetto",
    "DB_USER": "menu",
    "DB_PASSWORD": "menu",
}


class ConfigurazioneDB(NamedTuple):
    host: str
    port: str
    name: str
    user: str
    password: str
    mancanti: tuple[str, ...]

    @property
    def url(self) -> str:
        return (f"mysql+pymysql://{self.user}:{self.password}"
                f"@{self.host}:{self.port}/{self.name}")

    @property
    def url_mascherato(self) -> str:
        """URL con la password nascosta, sicuro da stampare nei log."""
        return (f"mysql+pymysql://{self.user}:***"
                f"@{self.host}:{self.port}/{self.name}")


def leggi_configurazione() -> ConfigurazioneDB:
    valori = {chiave: os.environ.get(chiave, default)
              for chiave, default in DEFAULT.items()}
    mancanti = tuple(chiave for chiave in DEFAULT if chiave not in os.environ)
    return ConfigurazioneDB(
        host=valori["DB_HOST"],
        port=valori["DB_PORT"],
        name=valori["DB_NAME"],
        user=valori["DB_USER"],
        password=valori["DB_PASSWORD"],
        mancanti=mancanti,
    )


def stampa_diagnostica(config: ConfigurazioneDB) -> None:
    """Rende visibile all'avvio a quale database ci si sta collegando.

    Senza questo, una variabile dimenticata produce un fallimento silenzioso:
    l'applicazione parte, cade sui default e cerca un host chiamato "db" che
    in Kubernetes non esiste. La prima riga di `kubectl logs` o `docker logs`
    deve rispondere alla domanda "con chi sta parlando?".
    """
    for chiave in DEFAULT:
        valore = getattr(config, chiave.removeprefix("DB_").lower())
        if chiave == "DB_PASSWORD":
            valore = "***"
        origine = "DEFAULT — nessuna variabile d'ambiente!" if chiave in config.mancanti else "da ambiente"
        print(f"[config] {chiave}={valore}  ({origine})")
    print(f"[config] DSN: {config.url_mascherato}")

    if config.mancanti:
        print(f"[config] ATTENZIONE: {len(config.mancanti)} variabili non impostate, "
              f"si usano i default: {', '.join(config.mancanti)}")


def verifica_o_esci(config: ConfigurazioneDB) -> None:
    """Con DB_STRICT=true un fallback diventa un errore fatale.

    Va chiamata da main() o da popola_db(), MAI eseguita all'import: un
    sys.exit a livello di modulo farebbe fallire "import src.database", quindi
    l'app andrebbe in crashloop e i test non partirebbero nemmeno.

    Il default e' false, cosi' nessuna variabile d'ambiente nuova diventa
    obbligatoria e i due laboratori continuano a funzionare invariati.
    """
    if os.environ.get("DB_STRICT", "false").lower() not in ("1", "true", "yes"):
        return
    if config.mancanti:
        print(f"[config] DB_STRICT attivo e mancano: {', '.join(config.mancanti)}")
        sys.exit(1)


CONFIG = leggi_configurazione()
DATABASE_URL = CONFIG.url
