"""Test della lettura della configurazione dall'ambiente."""
import pytest

from src.config import DEFAULT, leggi_bool, leggi_configurazione, leggi_int


@pytest.mark.parametrize("valore", ["1", "true", "TRUE", "yes", "si", " True "])
def test_leggi_bool_riconosce_le_forme_affermative(monkeypatch: pytest.MonkeyPatch,
                                                   valore: str) -> None:
    monkeypatch.setenv("PROVA", valore)
    assert leggi_bool("PROVA", default=False) is True


@pytest.mark.parametrize("valore", ["0", "false", "no", "", "qualsiasi"])
def test_leggi_bool_tratta_il_resto_come_falso(monkeypatch: pytest.MonkeyPatch,
                                               valore: str) -> None:
    monkeypatch.setenv("PROVA", valore)
    assert leggi_bool("PROVA", default=True) is False


def test_leggi_bool_usa_il_default_se_la_variabile_manca(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROVA", raising=False)
    assert leggi_bool("PROVA", default=True) is True


def test_leggi_int_ignora_un_valore_non_numerico(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un valore scritto male non deve impedire l'avvio: si segnala e si prosegue."""
    monkeypatch.setenv("PROVA", "trenta")
    assert leggi_int("PROVA", 30) == 30


def test_leggi_int_legge_un_valore_valido(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROVA", "7")
    assert leggi_int("PROVA", 30) == 7


def test_la_configurazione_segnala_le_variabili_mancanti(monkeypatch: pytest.MonkeyPatch) -> None:
    """E' cio' che rende visibile un fallback altrimenti silenzioso."""
    for chiave in DEFAULT:
        monkeypatch.delenv(chiave, raising=False)

    config = leggi_configurazione()

    assert set(config.mancanti) == set(DEFAULT)
    assert config.name == "menu_progetto"


def test_la_password_non_compare_nell_url_mascherato(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_PASSWORD", "password-molto-segreta")

    config = leggi_configurazione()

    assert "password-molto-segreta" in config.url
    assert "password-molto-segreta" not in config.url_mascherato
    assert "***" in config.url_mascherato
