"""Verifica del codice di uscita di popola_db.py.

Girano in un sottoprocesso perche' e' l'unico modo di osservare davvero un
sys.exit: e' quello che vedono Docker e un Job Kubernetes.
"""
import os
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent


def _esegui(**variabili: str) -> subprocess.CompletedProcess[str]:
    ambiente = {
        **os.environ,
        "PYTHONPATH": str(RADICE),
        # Porta chiusa su localhost: la connessione viene rifiutata subito,
        # senza attendere un timeout di rete.
        "DB_HOST": "127.0.0.1",
        "DB_PORT": "1",
        "DB_RETRY_TENTATIVI": "1",
        "DB_RETRY_ATTESA": "0",
        **variabili,
    }
    return subprocess.run(
        [sys.executable, str(RADICE / "popola_db.py")],
        capture_output=True, text=True, env=ambiente, timeout=120,
    )


def test_esce_con_codice_non_zero_se_il_database_non_risponde() -> None:
    """Un fallimento deve essere visibile a Docker e a Kubernetes.

    Prima il processo usciva con 0 anche quando il popolamento falliva: il
    deploy risultava riuscito su un database vuoto.
    """
    esito = _esegui()

    assert esito.returncode == 1
    assert "Sincronizzazione database completata." not in esito.stdout


def test_la_diagnostica_mostra_la_configurazione_usata() -> None:
    """La prima cosa nei log deve dire con quale database si sta parlando."""
    esito = _esegui(DB_NAME="banca_dati_di_prova", DB_USER="utente_di_prova",
                    DB_PASSWORD="password-segretissima")

    assert "DB_NAME=banca_dati_di_prova" in esito.stdout
    assert "utente_di_prova" in esito.stdout
    assert "password-segretissima" not in esito.stdout
    assert "password-segretissima" not in esito.stderr


def test_db_strict_termina_se_mancano_le_variabili() -> None:
    ambiente_pulito = {
        chiave: valore for chiave, valore in os.environ.items()
        if not chiave.startswith("DB_")
    }
    esito = subprocess.run(
        [sys.executable, str(RADICE / "popola_db.py")],
        capture_output=True, text=True, timeout=60,
        env={**ambiente_pulito, "PYTHONPATH": str(RADICE), "DB_STRICT": "true"},
    )

    assert esito.returncode == 1
    assert "DB_STRICT" in esito.stdout
