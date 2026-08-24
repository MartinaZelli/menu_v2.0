from enum import Enum


class Stagione(Enum):
    ESTATE = "estate"
    MEZZA = "mezza stagione"
    INVERNO = "inverno"
    GENERICO = "generico"

class Tipologia(Enum):
    PRIMO = "primo" 
    SECONDO = "secondo"
    CONTORNO = "contorno"
    UNICO = "unico"

class Proteina(Enum):
    LEGUMI = "legumi"
    LATTICINI = "latticini"
    CARNE_BIANCA = "carne bianca"
    CARNE_ROSSA = "carne rossa"
    PESCE = "pesce"
    UOVA = "uova"

class Giorni_settimana(Enum):
    LUNEDI = "lunedì"
    MARTEDI = "martedì"
    MERCOLEDI = "mercoledì"
    GIOVEDI = "giovedì"
    VENERDI = "venerdì"
    SABATO = "sabato"
    DOMENICA = "domenica"

GIORNI_LAVORATIVI_DEFAULT = list(Giorni_settimana)[:5]


def valore_enum(campo: object) -> object:
    """Estrae il valore di un enum, lasciando intatto tutto il resto.

    Serve perche' gli enum NON arrivano al database: le colonne sono String e
    sia il dataset sia il servizio confrontano i valori testuali. Lo stesso
    controllo era ripetuto in src/router.py e in src/service.py.
    """
    return campo.value if hasattr(campo, "value") else campo
