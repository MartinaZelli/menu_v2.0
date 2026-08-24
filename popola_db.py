import sys
import time
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

try:
    # Questi import stanno DENTRO il try di proposito: se PYTHONPATH non
    # include la radice del progetto falliscono, e senza questo blocco
    # l'utente vedrebbe un traceback grezzo invece di un messaggio utile.
    # Nei due laboratori il PYTHONPATH=/app e' proprio cio' che li fa
    # funzionare, dato che lo script viene eseguito da /app/popola_db/.
    from data_piatti import PIATTI_DATA
    from src.config import (
        CONFIG,
        DATABASE_URL,
        leggi_bool,
        leggi_int,
        stampa_diagnostica,
        verifica_o_esci,
    )
    from src.database import Base, MacroDB, PastoSalvatoDB, PiattoDB
    from src.enums import Proteina
except ImportError as e:
    print(f"Errore: Non riesco a trovare i moduli. Dettaglio: {e}")
    print("Suggerimento: esegui con PYTHONPATH puntato alla radice del progetto.")
    sys.exit(1)

# Frequenze settimanali desiderate per proteina.
# Nota: la somma e' 18 su 14 slot settimanali, quindi il pool viene troncato
# dal servizio e non tutte le frequenze sono soddisfatte a ogni generazione.
MACRO_DESIDERATE: list[dict[str, Any]] = [
    {"proteina": Proteina.LEGUMI.value, "frequenza": 3},
    {"proteina": Proteina.LATTICINI.value, "frequenza": 4},
    {"proteina": Proteina.CARNE_BIANCA.value, "frequenza": 4},
    {"proteina": Proteina.CARNE_ROSSA.value, "frequenza": 1},
    {"proteina": Proteina.PESCE.value, "frequenza": 3},
    {"proteina": Proteina.UOVA.value, "frequenza": 3},
]


def attendi_database(engine: Engine, tentativi: int, attesa: int) -> bool:
    """Attende che il database accetti connessioni.

    Il nome conta: chiamandola test_* pytest la raccoglierebbe come test.
    """
    print(f"Inizializzazione database via {CONFIG.host}...")

    for i in range(tentativi):
        try:
            with engine.connect() as connection:
                # Eseguiamo una query di test per verificare la reale operatività
                connection.execute(text("SELECT 1"))
                print("Connessione stabilita con successo!")
                return True
        except Exception as e:  # noqa: BLE001 - qualunque errore qui significa "database non ancora pronto"
            # Si stampa anche la CLASSE dell'eccezione: distingue "il database
            # non e' ancora avviato" (OperationalError di rete, transitorio) da
            # "le credenziali sono sbagliate" o "il database non esiste", che
            # non sono transitori e continueranno a fallire fino all'ultimo
            # tentativo consumando tutto il tempo di attesa.
            print(f"Tentativo {i+1}/{tentativi}: DB su {CONFIG.host} non pronto... "
                  f"({type(e).__name__}: {e})")
            time.sleep(attesa)

    return False


Chiave = tuple[str, str | None]


def _chiave_db(piatto: PiattoDB) -> Chiave:
    return (piatto.nome, piatto.proteina)


def _chiave_dataset(piatto: dict[str, Any]) -> Chiave:
    return (piatto["nome"], piatto["proteina"])


def verifica_chiavi_uniche(piatti_desiderati: list[dict[str, Any]]) -> None:
    """Il dataset non deve contenere due piatti con la stessa (nome, proteina).

    E' la condizione che rende affidabile l'indice usato da sincronizza(): se
    un giorno venisse violata, il difetto delle voci che si sovrascrivono a
    vicenda tornerebbe in silenzio. Meglio accorgersene qui, con un messaggio
    che dice quale coppia e' duplicata.
    """
    viste: set[Chiave] = set()
    duplicate: set[Chiave] = set()
    for piatto in piatti_desiderati:
        chiave = _chiave_dataset(piatto)
        if chiave in viste:
            duplicate.add(chiave)
        viste.add(chiave)

    if duplicate:
        elenco = ", ".join(f"{nome} ({proteina})" for nome, proteina in sorted(
            duplicate, key=lambda c: (c[0], c[1] or "")))
        raise ValueError(
            f"Il dataset contiene {len(duplicate)} coppie (nome, proteina) "
            f"duplicate: {elenco}. Vanno rese distinte, altrimenti la "
            f"sincronizzazione non puo' distinguere le righe fra loro."
        )


def sincronizza(
    session: Session,
    piatti_desiderati: list[dict[str, Any]],
    macro_desiderate: list[dict[str, Any]],
    svuota_storico: bool = True,
) -> None:
    """Allinea il contenuto del database allo stato descritto dal dataset.

    Non e' un semplice "inserisci tutto": aggiorna i record esistenti,
    aggiunge i nuovi e cancella quelli non piu' presenti nel dataset.

    Riceve la sessione dall'esterno e non la chiude: chi apre chiude.
    Non cattura le eccezioni: la gestione (rollback, uscita) spetta al
    chiamante, che e' anche l'unico a sapere se siamo in un test o in
    produzione.
    """
    verifica_chiavi_uniche(piatti_desiderati)

    # 0. PULIZIA TOTALE DEI MENU SALVATI
    if svuota_storico:
        num_deleted = session.query(PastoSalvatoDB).delete()
        if num_deleted > 0:
            print(f"Storico menu salvati ({num_deleted} record) rimosso.")

    # 1. Sincronizzazione Macro
    macro_db = session.query(MacroDB).all()
    nomi_macro_db = {m.proteina: m for m in macro_db}

    for m_data in macro_desiderate:
        if m_data["proteina"] in nomi_macro_db:
            nomi_macro_db[m_data["proteina"]].frequenza = m_data["frequenza"]
        else:
            session.add(MacroDB(**m_data))

    # Carica piatti esistenti.
    #
    # L'indice usa la coppia (nome, proteina) e non il solo nome: il dataset
    # contiene di proposito piatti omonimi con proteine diverse (Polpettone
    # esiste in 4 versioni). Con il solo nome le 4 righe collassavano su una
    # sola voce del dizionario, e tutte le operazioni destinate alle 4
    # varianti finivano sulla stessa riga: le modifiche andavano perse e una
    # variante rimossa dal dataset non veniva mai cancellata.
    piatti_db = session.query(PiattoDB).all()
    esistenti = {_chiave_db(p): p for p in piatti_db}
    desiderate = {_chiave_dataset(p) for p in piatti_desiderati}

    # 2. Eliminazione piatti non più presenti
    for chiave, piatto_obj in esistenti.items():
        if chiave not in desiderate:
            print(f"Eliminazione piatto obsoleto: {chiave[0]} ({chiave[1]})")
            session.delete(piatto_obj)

    # 3. Inserimento/Aggiornamento
    for p_data in piatti_desiderati:
        p_db = esistenti.get(_chiave_dataset(p_data))
        if p_db is not None:
            p_db.tempo = p_data["tempo"]
            p_db.adatto_al_lavoro = p_data["adatto_al_lavoro"]
            p_db.tipologia = p_data["tipologia"]
            p_db.stagione = p_data["stagione"]
        else:
            print(f"Aggiunta nuovo piatto: {p_data['nome']}")
            session.add(PiattoDB(**p_data))

    session.commit()


def popola_db() -> None:
    stampa_diagnostica(CONFIG)
    verifica_o_esci(CONFIG)

    # I tentativi erano 10 a 5 secondi, cioe' 50 secondi in tutto. Un MySQL al
    # PRIMO avvio, quando deve ancora inizializzare il volume dei dati, impiega
    # regolarmente piu' di due minuti: lo script si arrendeva prima che il
    # database fosse pronto. Il default sale quindi a 30 tentativi (150s) e
    # resta configurabile, perche' il tempo giusto dipende dall'ambiente.
    tentativi = leggi_int("DB_RETRY_TENTATIVI", 30)
    attesa = leggi_int("DB_RETRY_ATTESA", 5)

    # Lo svuotamento dello storico e' il comportamento storico e resta il
    # default. Non e' solo una comodita': PastoSalvatoDB.piatto_id e' una
    # foreign key senza ON DELETE, quindi finche' esistono pasti salvati che
    # referenziano un piatto, quel piatto non e' cancellabile. Disattivarlo
    # significa accettare che i piatti tolti dal dataset ma gia' usati in un
    # menu salvato non possano piu' essere rimossi.
    svuota_storico = leggi_bool("POPOLA_DB_SVUOTA_STORICO", default=True)
    if not svuota_storico:
        print("[popola_db] POPOLA_DB_SVUOTA_STORICO=false: lo storico dei menu "
              "viene conservato.")

    engine = create_engine(DATABASE_URL)

    if not attendi_database(engine, tentativi, attesa):
        print(f"Errore critico: impossibile connettersi al database dopo "
              f"{tentativi} tentativi ({tentativi * attesa} secondi).")
        sys.exit(1)

    Base.metadata.create_all(engine)
    SessionLocale = sessionmaker(bind=engine)
    session = SessionLocale()

    try:
        sincronizza(session, PIATTI_DATA, MACRO_DESIDERATE, svuota_storico)
        # Questa riga e' un contratto: la procedura di verifica documentata nel
        # laboratorio Kubernetes la cerca nei log del Job. Non cambiarne il testo.
        print("Sincronizzazione database completata.")
    except Exception as e:  # noqa: BLE001 - confine del processo: ogni errore deve diventare exit(1)
        session.rollback()
        print(f"Errore durante il popolamento: {type(e).__name__}: {e}")
        # Uscire con codice non-zero e' il punto di questa gestione.
        #
        # Prima l'eccezione veniva stampata e basta: il processo terminava con
        # 0, quindi Docker e un Job Kubernetes consideravano il popolamento
        # riuscito. Il risultato era un deploy verde su un database vuoto, e
        # l'unico modo per accorgersene era leggere i log a mano.
        #
        # Con l'uscita a 1, il Job va in Failed dopo i suoi backoffLimit
        # tentativi e il problema diventa visibile.
        sys.exit(1)
    finally:
        # sys.exit solleva SystemExit, che deriva da BaseException e non viene
        # quindi intercettata dall'except qui sopra: il finally viene eseguito
        # comunque e la sessione viene chiusa.
        session.close()


if __name__ == "__main__":
    popola_db()
