"""Test degli endpoint HTTP.

Alcuni descrivono comportamento gia' corretto e servono da rete di sicurezza
per non farlo regredire. Altri descrivono il comportamento *desiderato* di
cose oggi rotte, e falliscono finche' la correzione non arriva.
"""
import random

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from data_piatti import PIATTI_DATA
from popola_db import MACRO_DESIDERATE, sincronizza
from src.database import PastoSalvatoDB, PiattoDB, SettimanaDB


@pytest.fixture
def db_popolato(db: Session) -> Session:
    sincronizza(db, PIATTI_DATA, MACRO_DESIDERATE)
    return db


# --- Vincoli dei due laboratori: se cadono questi, cade il deploy -----------

def test_il_frontend_statico_risponde(client: TestClient) -> None:
    """/piatti.html e' l'healthcheck di HAProxy nel laboratorio Ansible.

    Se smette di rispondere 200, il load balancer marca il backend DOWN e il
    sito va in 503 pur essendo l'applicazione perfettamente viva.
    """
    assert client.get("/piatti.html").status_code == 200
    assert client.get("/").status_code == 200


def test_elenco_piatti_e_la_smoke_test_dei_lab(client: TestClient, db_popolato: Session) -> None:
    """GET /menu/elenco-piatti e' la verifica end-to-end documentata in entrambi i lab."""
    risposta = client.get("/menu/elenco-piatti")

    assert risposta.status_code == 200
    assert len(risposta.json()) == 166


def test_elenco_piatti_regge_una_stagione_nulla(client: TestClient, db_popolato: Session) -> None:
    """Una sola riga malformata non deve far cadere l'intera risposta.

    Le colonne non hanno nullable=False, quindi una stagione NULL e' possibile.
    Nel modello Pydantic il default si applica quando il campo e' *assente*,
    non quando vale None: senza Optional, model_validate solleva e il
    response_model fa fallire tutta la lista con un 500.
    """
    db_popolato.query(PiattoDB).filter(PiattoDB.id == 1).one().stagione = None
    db_popolato.commit()

    assert client.get("/menu/elenco-piatti").status_code == 200


# --- Generazione del menu ---------------------------------------------------

def test_genera_menu_riempie_la_settimana(client: TestClient, db_popolato: Session) -> None:
    random.seed(0)
    risposta = client.post("/menu", json={"tempo_massimo": 1000})

    assert risposta.status_code == 200
    tabella = risposta.json()["tabella"]
    giorni = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"]
    assert sorted(tabella) == sorted(giorni)
    slot = sum(len(tabella[g][m]) for g in giorni for m in ("pranzo", "cena"))
    assert slot == 14


def test_genera_menu_rispetta_i_pasti_bloccati(client: TestClient, db_popolato: Session) -> None:
    random.seed(0)
    piatto = db_popolato.query(PiattoDB).filter(PiattoDB.nome == "Sushi").first()
    bloccato = {
        "giorno": "mercoledi",
        "momento": "cena",
        "piatto": {
            "id": piatto.id, "nome": piatto.nome, "proteina": piatto.proteina,
            "stagione": piatto.stagione, "tempo": piatto.tempo,
            "adatto_al_lavoro": piatto.adatto_al_lavoro, "tipologia": piatto.tipologia,
        },
    }

    risposta = client.post("/menu", json={"pasti_bloccati": [bloccato]})

    assert risposta.status_code == 200
    assert risposta.json()["tabella"]["mercoledi"]["cena"][0]["nome"] == "Sushi"


def test_salva_menu_e_idempotente_sulla_settimana(client: TestClient, db_popolato: Session) -> None:
    """Salvare due volte la stessa settimana sovrascrive, non duplica."""
    random.seed(0)
    menu = client.post("/menu", json={"data_inizio_settimana": "2026-03-02"}).json()

    assert client.post("/menu/salva", json=menu).status_code == 200
    primo_conteggio = db_popolato.query(PastoSalvatoDB).count()
    assert client.post("/menu/salva", json=menu).status_code == 200

    assert db_popolato.query(PastoSalvatoDB).count() == primo_conteggio
    assert db_popolato.query(SettimanaDB).count() == 1


# --- Anagrafica piatti ------------------------------------------------------

def test_aggiungi_piatto_rispetta_la_tipologia(client: TestClient, db: Session) -> None:
    """La tipologia inviata dal client viene oggi scartata e sostituita da "primo"."""
    risposta = client.post("/menu/aggiungi-piatto", json={
        "nome": "Branzino al forno", "proteina": "pesce", "stagione": "generico",
        "tempo": 40, "adatto_al_lavoro": True, "tipologia": "secondo",
    })

    assert risposta.status_code == 200
    salvato = db.query(PiattoDB).filter(PiattoDB.nome == "Branzino al forno").one()
    assert salvato.tipologia == "secondo"


def test_aggiungi_piatto_non_richiede_un_id_fittizio(client: TestClient, db: Session) -> None:
    """Un piatto ancora inesistente non puo' avere un id: lo assegna il database.

    Il frontend aggira oggi il vincolo inviando id: 0.
    """
    risposta = client.post("/menu/aggiungi-piatto", json={
        "nome": "Zuppa di ceci", "proteina": "legumi", "stagione": "inverno",
        "tempo": 50, "adatto_al_lavoro": True, "tipologia": "primo",
    })

    assert risposta.status_code == 200
    assert db.query(PiattoDB).filter(PiattoDB.nome == "Zuppa di ceci").count() == 1


def test_elimina_piatto_inesistente_risponde_404(client: TestClient, db_popolato: Session) -> None:
    """Oggi risponde 200 {"status": "deleted"} senza aver cancellato nulla."""
    assert client.delete("/menu/elimina-piatto/999999").status_code == 404


def test_elimina_piatto_referenziato_risponde_409(client: TestClient, db_popolato: Session) -> None:
    """Un piatto usato in uno storico non e' cancellabile: e' un conflitto, non un errore interno.

    Oggi la violazione di foreign key esce come 500 non gestito.
    """
    settimana = SettimanaDB(data_inizio=None)
    db_popolato.add(settimana)
    db_popolato.flush()
    db_popolato.add(PastoSalvatoDB(settimana_id=settimana.id, giorno="lunedi",
                                   momento="pranzo", piatto_id=1))
    db_popolato.commit()

    risposta = client.delete("/menu/elimina-piatto/1")

    assert risposta.status_code == 409
    assert db_popolato.query(PiattoDB).filter(PiattoDB.id == 1).count() == 1


def test_elimina_piatto_libero_funziona(client: TestClient, db_popolato: Session) -> None:
    assert client.delete("/menu/elimina-piatto/1").status_code == 200
    assert db_popolato.query(PiattoDB).filter(PiattoDB.id == 1).count() == 0
