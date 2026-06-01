import random
from datetime import date
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from src.database import SessionLocal, PiattoDB, MacroDB, SettimanaDB, PastoSalvatoDB
from src.risposta_menu import Pasti, Pasti_settimana, Risposta
from src.piatto import Piatto
from src.enums import Proteina, Stagione, Tipologia
from src.richiesta_menu import Richiesta

def genera_pool_proteine_dinamico(frequenza: Dict[str, int], totale_target: int) -> List[str]:
    pool = []
    for prot, qta in frequenza.items():
        pool.extend([prot] * qta)
    
    proteine_chiave = list(frequenza.keys())
    if not proteine_chiave:
        proteine_chiave = ["legumi", "carne bianca", "carne rossa", "pesce", "uova", "latticini"]

    while len(pool) < totale_target:
        pool.append(random.choice(proteine_chiave))
    
    random.shuffle(pool)
    return pool[:totale_target]

def genera_menu_ordinato(richiesta: Richiesta) -> Risposta:
    db = SessionLocal()
    try:
        macro = db.query(MacroDB).all()
        frequenza_ideale = {m.proteina: m.frequenza for m in macro}
        tutti_piatti = db.query(PiattoDB).all()

        pasti_bloccati = richiesta.pasti_bloccati or []
        mappa_pasti = {f"{pb.giorno}_{pb.momento}": pb.piatto for pb in pasti_bloccati}
        
        frequenza_residua = frequenza_ideale.copy()
        for pb in pasti_bloccati:
            prot = pb.piatto.proteina.value if hasattr(pb.piatto.proteina, 'value') else pb.piatto.proteina
            if prot in frequenza_residua:
                frequenza_residua[prot] = max(0, frequenza_residua[prot] - 1)

        posti_liberi = 14 - len(pasti_bloccati)
        pool_proteine = genera_pool_proteine_dinamico(frequenza_residua, posti_liberi)

        giorni_nomi = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"]
        # Normalizzazione giorni lavorativi senza accenti
        giorni_lavorativi_nomi = [g.value.replace("ì", "i") for g in richiesta.giorni_lavorativi]
        stagioni_richieste = [s.value for s in richiesta.stagioni] if richiesta.stagioni else []

        # 4. LOGICA "LAZY" - PRANZI LAVORATIVI A RITROSO
        for i in range(4, -1, -1):
            giorno_corr = giorni_nomi[i]
            chiave_pranzo = f"{giorno_corr}_pranzo"

            if chiave_pranzo not in mappa_pasti and pool_proteine:
                prot_scelta = random.choice(list(set(pool_proteine)))
                
                candidati = [p for p in tutti_piatti if 
                            p.proteina == prot_scelta and
                            (not stagioni_richieste or p.stagione in stagioni_richieste) and
                            p.tempo <= richiesta.tempo_massimo and
                            p.adatto_al_lavoro == True]

                if candidati:
                    piatto_db = random.choice(candidati)
                    # Conversione sicura da DB a Pydantic
                    piatto_pydantic = Piatto.model_validate(piatto_db)
                    mappa_pasti[chiave_pranzo] = piatto_pydantic
                    pool_proteine.remove(prot_scelta)

                    # RIPETIZIONE (60%)
                    if random.random() < 0.60 and prot_scelta in pool_proteine:
                        ripetuto = False
                        if i > 0:
                            chiave_prec_p = f"{giorni_nomi[i-1]}_pranzo"
                            if chiave_prec_p not in mappa_pasti:
                                mappa_pasti[chiave_prec_p] = piatto_pydantic
                                pool_proteine.remove(prot_scelta)
                                ripetuto = True
                        
                        if not ripetuto and i > 0:
                            chiave_prec_c = f"{giorni_nomi[i-1]}_cena"
                            if chiave_prec_c not in mappa_pasti:
                                mappa_pasti[chiave_prec_c] = piatto_pydantic
                                pool_proteine.remove(prot_scelta)

        # 5. RIEMPIMENTO RIMANENTI
        for giorno in giorni_nomi:
            for momento in ["pranzo", "cena"]:
                chiave = f"{giorno}_{momento}"
                if chiave not in mappa_pasti and pool_proteine:
                    prot_scelta = random.choice(list(set(pool_proteine)))
                    is_lavoro = (giorno in giorni_lavorativi_nomi and momento == "pranzo")
                    
                    candidati = [p for p in tutti_piatti if 
                                p.proteina == prot_scelta and
                                (not stagioni_richieste or p.stagione in stagioni_richieste) and
                                p.tempo <= richiesta.tempo_massimo and
                                (not is_lavoro or p.adatto_al_lavoro == True)]
                    
                    if candidati:
                        p_db = random.choice(candidati)
                        mappa_pasti[chiave] = Piatto.model_validate(p_db)
                        pool_proteine.remove(prot_scelta)
                    else:
                        mappa_pasti[chiave] = Piatto(id=999, nome=f"Manca {prot_scelta}", tempo=0, adatto_al_lavoro=False)

        # 6. COSTRUZIONE RISPOSTA
        pasti_sett = {}
        for g in giorni_nomi:
            pasti_sett[g] = Pasti(
                pranzo=[mappa_pasti.get(f"{g}_pranzo")] if mappa_pasti.get(f"{g}_pranzo") else [],
                cena=[mappa_pasti.get(f"{g}_cena")] if mappa_pasti.get(f"{g}_cena") else []
            )

        return Risposta(
            data_inizio_settimana=richiesta.data_inizio_settimana or date.today(),
            tabella=Pasti_settimana(**pasti_sett)
        )
    finally:
        db.close()

def salva_menu_settimanale(risposta: Risposta) -> bool:
    db_session = SessionLocal()
    try:
        settimana = db_session.query(SettimanaDB).filter(
            SettimanaDB.data_inizio == risposta.data_inizio_settimana
        ).first()

        if settimana:
            db_session.query(PastoSalvatoDB).filter(PastoSalvatoDB.settimana_id == settimana.id).delete()
        else:
            settimana = SettimanaDB(data_inizio=risposta.data_inizio_settimana)
            db_session.add(settimana)
            db_session.flush()

        giorni = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"]
        for g in giorni:
            pasti_giorno = getattr(risposta.tabella, g)
            for m in ["pranzo", "cena"]:
                lista = getattr(pasti_giorno, m)
                for p in lista:
                    if p:
                        db_session.add(PastoSalvatoDB(
                            settimana_id=settimana.id,
                            giorno=g,
                            momento=m,
                            piatto_id=p.id if p.id != 999 else None,
                            nome_manuale=p.nome if p.id == 999 else None
                        ))
        db_session.commit()
        return True
    except Exception as e:
        db_session.rollback()
        print(f"Errore salvataggio: {e}")
        return False
    finally:
        db_session.close()