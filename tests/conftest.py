"""Fixture condivise dai test.

I test girano su SQLite in memoria invece che su MySQL: non serve un database
avviato, ogni test parte da uno stato pulito e l'esecuzione e' istantanea.

Il prezzo da pagare sono tre dettagli di configurazione senza i quali i test
*sembrano* funzionare ma non verificano nulla. Sono commentati uno per uno
qui sotto, perche' sono esattamente il tipo di cosa che fa perdere un'ora.
"""
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import main
from src.database import Base, get_db


@pytest.fixture
def engine() -> Iterator[Engine]:
    motore = create_engine(
        "sqlite://",  # senza path = database in memoria
        # TRAPPOLA 1: un database SQLite in memoria vive dentro la singola
        # connessione che lo ha creato. Con il pool normale, ogni nuova
        # connessione vedrebbe un database vuoto: crei le tabelle e la query
        # successiva risponde "no such table". StaticPool riusa sempre la
        # stessa connessione, quindi il database persiste per tutto il test.
        poolclass=StaticPool,
        # TRAPPOLA 2: TestClient esegue l'app in un thread diverso da quello
        # del test. SQLite di default rifiuta una connessione usata da piu'
        # thread; qui e' sicuro perche' StaticPool la serializza.
        connect_args={"check_same_thread": False},
    )

    # TRAPPOLA 3: SQLite NON applica le foreign key se non glielo si chiede,
    # a ogni connessione. Senza questo, il test "eliminare un piatto
    # referenziato deve fallire" passerebbe in verde anche con il bug
    # presente: un test che non puo' fallire non e' un test.
    @event.listens_for(motore, "connect")
    def _abilita_foreign_key(dbapi_connection, connection_record) -> None:
        cursore = dbapi_connection.cursor()
        cursore.execute("PRAGMA foreign_keys=ON")
        cursore.close()

    Base.metadata.create_all(motore)
    yield motore
    motore.dispose()


@pytest.fixture
def db(engine: Engine) -> Iterator[Session]:
    """Sessione usata direttamente dai test che non passano dall'API."""
    sessione = sessionmaker(bind=engine)()
    try:
        yield sessione
    finally:
        sessione.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    """Client HTTP che parla con l'app vera, ma sul database di test.

    dependency_overrides sostituisce get_db: l'app continua a usare il suo
    engine MySQL per tutto il resto, ma gli endpoint ricevono questa
    sessione. E' il motivo per cui nella fase 1 la sessione e' diventata una
    dependency invece di essere aperta dentro ogni endpoint.

    La sessione e' la stessa del fixture db, cosi' un test puo' preparare i
    dati direttamente e poi verificarli via HTTP.
    """
    main.app.dependency_overrides[get_db] = lambda: db
    try:
        yield TestClient(main.app)
    finally:
        main.app.dependency_overrides.clear()
