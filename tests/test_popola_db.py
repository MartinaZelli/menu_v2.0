"""Test della sincronizzazione dell'anagrafica piatti.

Il dataset contiene di proposito piatti con lo stesso nome ma proteine diverse
(Polpettone esiste in 4 versioni: carne bianca, carne rossa, latticini, uova).
sincronizza() indicizza pero' i piatti gia' presenti con il solo nome:

    nomi_db = {p.nome: p for p in piatti_db}

Le 4 righe di Polpettone collassano quindi su una sola voce del dizionario, e
tutte le operazioni destinate alle 4 varianti finiscono sulla stessa riga.

Il conteggio dei record NON cambia: e' questo che rende il bug difficile da
notare. Cambiano i dati dentro le righe. I due test che seguono descrivono i
due sintomi misurati.
"""
from typing import Any

from sqlalchemy.orm import Session

from data_piatti import PIATTI_DATA
from popola_db import MACRO_DESIDERATE, sincronizza
from src.database import MacroDB, PastoSalvatoDB, PiattoDB, SettimanaDB


def _dataset() -> list[dict[str, Any]]:
    """Copia del dataset, per poterlo modificare senza inquinare gli altri test."""
    return [dict(p) for p in PIATTI_DATA]


def test_primo_popolamento_inserisce_tutto(db: Session) -> None:
    sincronizza(db, PIATTI_DATA, MACRO_DESIDERATE)

    assert db.query(PiattoDB).count() == len(PIATTI_DATA) == 166
    assert db.query(MacroDB).count() == 6


def test_popolamenti_ripetuti_restano_stabili(db: Session) -> None:
    """Rieseguire il popolamento a dataset invariato non deve cambiare nulla."""
    sincronizza(db, PIATTI_DATA, MACRO_DESIDERATE)
    prima = {(p.id, p.nome, p.proteina, p.tempo) for p in db.query(PiattoDB)}

    sincronizza(db, PIATTI_DATA, MACRO_DESIDERATE)
    dopo = {(p.id, p.nome, p.proteina, p.tempo) for p in db.query(PiattoDB)}

    assert dopo == prima


def test_modifica_a_piatto_con_nome_duplicato_viene_applicata(db: Session) -> None:
    """Primo sintomo: la modifica finisce sulla riga sbagliata e va persa.

    Correggendo il tempo di preparazione di UNA variante, l'aggiornamento
    viene applicato alla riga che ha vinto il dizionario e poi sovrascritto
    dalle varianti successive. La riga giusta non viene mai toccata.
    """
    sincronizza(db, PIATTI_DATA, MACRO_DESIDERATE)

    dataset = _dataset()
    for piatto in dataset:
        if piatto["nome"] == "Polpettone" and piatto["proteina"] == "carne bianca":
            piatto["tempo"] = 45
    sincronizza(db, dataset, MACRO_DESIDERATE)

    riga = db.query(PiattoDB).filter(
        PiattoDB.nome == "Polpettone",
        PiattoDB.proteina == "carne bianca",
    ).one()
    assert riga.tempo == 45


def test_variante_rimossa_dal_dataset_viene_cancellata(db: Session) -> None:
    """Secondo sintomo: la variante rimossa sopravvive, con dati altrui.

    Togliendo dal dataset il Polpettone di uova, il nome "Polpettone" compare
    ancora fra i desiderati (altre 3 volte), quindi nessuna riga viene
    considerata obsoleta. La riga resta, e per giunta viene sovrascritta con
    i valori di un'altra variante: si finisce con due latticini e nessun uova.
    """
    sincronizza(db, PIATTI_DATA, MACRO_DESIDERATE)

    ridotto = [p for p in _dataset()
               if not (p["nome"] == "Polpettone" and p["proteina"] == "uova")]
    sincronizza(db, ridotto, MACRO_DESIDERATE)

    rimasti = db.query(PiattoDB).filter(PiattoDB.nome == "Polpettone").all()
    assert len(rimasti) == 3
    assert sorted(p.proteina for p in rimasti) == ["carne bianca", "carne rossa", "latticini"]


def test_piatto_rimosso_dal_dataset_viene_cancellato(db: Session) -> None:
    """La cancellazione degli obsoleti e' una funzionalita', non un difetto.

    Su un nome NON duplicato funziona gia' correttamente.
    """
    sincronizza(db, PIATTI_DATA, MACRO_DESIDERATE)

    ridotto = [p for p in _dataset() if p["nome"] != "Insalata"]
    sincronizza(db, ridotto, MACRO_DESIDERATE)

    assert db.query(PiattoDB).filter(PiattoDB.nome == "Insalata").count() == 0


def test_le_frequenze_macro_vengono_aggiornate_non_duplicate(db: Session) -> None:
    sincronizza(db, PIATTI_DATA, MACRO_DESIDERATE)

    macro_modificate = [dict(m) for m in MACRO_DESIDERATE]
    macro_modificate[0]["frequenza"] = 99
    sincronizza(db, PIATTI_DATA, macro_modificate)

    assert db.query(MacroDB).count() == 6
    proteina = macro_modificate[0]["proteina"]
    assert db.query(MacroDB).filter(MacroDB.proteina == proteina).one().frequenza == 99


def test_lo_storico_viene_svuotato_per_impostazione_predefinita(db: Session) -> None:
    """Comportamento voluto: rieseguire il popolamento azzera i menu salvati.

    Non e' un dettaglio innocuo ed e' anche strutturale: PastoSalvatoDB.piatto_id
    e' una foreign key senza ON DELETE, quindi finche' esistono pasti salvati
    che referenziano un piatto, quel piatto non e' cancellabile. Lo svuotamento
    e' cio' che rende possibile la rimozione degli obsoleti.
    """
    sincronizza(db, PIATTI_DATA, MACRO_DESIDERATE)
    settimana = SettimanaDB(data_inizio=None)
    db.add(settimana)
    db.flush()
    db.add(PastoSalvatoDB(settimana_id=settimana.id, giorno="lunedi",
                          momento="pranzo", piatto_id=1))
    db.commit()
    assert db.query(PastoSalvatoDB).count() == 1

    sincronizza(db, PIATTI_DATA, MACRO_DESIDERATE)

    assert db.query(PastoSalvatoDB).count() == 0
