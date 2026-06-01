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