"""Test delle sonde di salute."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import main
from src.database import get_db


def test_liveness_risponde_senza_database(client: TestClient) -> None:
    """La liveness non deve dipendere dal database.

    Se ne dipendesse, un'indisponibilita' temporanea del database farebbe
    riavviare in ciclo tutte le repliche invece di limitarsi a toglierle dal
    bilanciamento.
    """
    risposta = client.get("/health/live")

    assert risposta.status_code == 200
    assert risposta.json()["status"] == "alive"


def test_readiness_e_verde_con_il_database_raggiungibile(client: TestClient) -> None:
    risposta = client.get("/health/ready")

    assert risposta.status_code == 200
    assert risposta.json()["status"] == "ready"


def test_readiness_risponde_503_se_il_database_non_risponde(db: Session) -> None:
    """Con il database irraggiungibile: 503, non 500 e non 200.

    503 dichiara una non disponibilita' temporanea, ed e' cio' che fa togliere
    il pod dagli endpoint del Service senza ucciderlo.
    """
    class SessioneRotta:
        def execute(self, *args: object, **kwargs: object) -> None:
            raise ConnectionRefusedError("database irraggiungibile")

    main.app.dependency_overrides[get_db] = lambda: SessioneRotta()
    try:
        risposta = TestClient(main.app).get("/health/ready")
    finally:
        main.app.dependency_overrides.clear()

    assert risposta.status_code == 503
    assert risposta.json()["status"] == "unready"


def test_liveness_resta_verde_anche_con_il_database_rotto(db: Session) -> None:
    """E' il comportamento che giustifica l'esistenza di due endpoint separati."""
    class SessioneRotta:
        def execute(self, *args: object, **kwargs: object) -> None:
            raise ConnectionRefusedError("database irraggiungibile")

    main.app.dependency_overrides[get_db] = lambda: SessioneRotta()
    try:
        client = TestClient(main.app)
        assert client.get("/health/ready").status_code == 503
        assert client.get("/health/live").status_code == 200
    finally:
        main.app.dependency_overrides.clear()


def test_le_rotte_non_sono_intercettate_dai_file_statici(client: TestClient) -> None:
    """Le API sono registrate prima del mount su "/", che altrimenti le coprirebbe.

    Se qualcuno spostasse app.mount() sopra gli include_router, questi
    percorsi comincerebbero a rispondere 404 senza alcun errore in avvio,
    mentre /piatti.html continuerebbe a rispondere 200: l'healthcheck di
    HAProxy resterebbe verde su un'applicazione senza piu' API.
    """
    for percorso in ("/health/live", "/health/ready", "/menu/elenco-piatti"):
        assert client.get(percorso).status_code != 404, percorso
