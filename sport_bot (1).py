"""
Sport in TV – genera una pagina web con gli eventi sportivi importanti
(orario italiano, sport, piattaforma dove vederli) e un calendario .ics
a cui iscriversi da iPhone/PC per ricevere i promemoria.

Uso:
    python sport_bot.py               -> prossimi 7 giorni, output in docs/
    python sport_bot.py --giorni 3    -> prossimi 3 giorni

Fonti (tutte gratuite, senza chiave):
    Calcio, F1, NBA, Tennis  -> API pubbliche ESPN
    MotoGP                   -> API ufficiale MotoGP
    Superbike, Volley, altro -> file extra.json (lo compili tu)

Output (pubblicato gratis con GitHub Pages):
    docs/index.html       la pagina
    docs/sport.ics        calendario completo (iscrizione, si aggiorna da solo)
    docs/eventi/*.ics     un file per evento (pulsante 🔔)
"""

import argparse
import hashlib
import html
import json
import re
import shutil
import unicodedata
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Rome")
ESPN = "https://site.api.espn.com/apis/site/v2/sports"
MOTOGP = "https://api.motogp.pulselive.com/motogp/v1"
PROMEMORIA_MINUTI = 30
PASSATI = 7  # giorni passati mostrati nella striscia (con i risultati)
DEMO = False  # True solo per le anteprime con eventi inventati: gli orari seguono il momento in cui apri la pagina

# ---------------------------------------------------------------------------
# SPORT: ordine, emoji, nome, colore e competizioni tra cui l'utente può scegliere
# ---------------------------------------------------------------------------
SPORT = {
    "calcio": {"emoji": "⚽", "nome": "Calcio", "colore": "#22c55e",
               "leghe": ["Serie A", "Serie B", "Coppa Italia", "Champions League", "Europa League",
                         "Conference League", "Nations League", "Premier League", "LaLiga",
                         "Bundesliga", "Ligue 1", "Eredivisie"]},
    "f1": {"emoji": "🏎️", "nome": "F1", "colore": "#ef4444", "leghe": ["Formula 1"]},
    "motogp": {"emoji": "🏍️", "nome": "MotoGP", "colore": "#3b82f6", "leghe": ["MotoGP"]},
    "sbk": {"emoji": "🏁", "nome": "Superbike", "colore": "#a855f7", "leghe": ["Superbike"]},
    "tennis": {"emoji": "🎾", "nome": "Tennis", "colore": "#eab308", "leghe": ["ATP", "WTA"]},
    "basket": {"emoji": "🏀", "nome": "Basket", "colore": "#f97316",
               "leghe": ["NBA", "Serie A Basket", "EuroLeague"]},
    "volley": {"emoji": "🏐", "nome": "Volley", "colore": "#06b6d4",
               "leghe": ["SuperLega", "Serie A1 Femminile"]},
}

SQUADRE_ITALIANE = [
    "Inter", "Milan", "Juventus", "Napoli", "Roma", "Lazio", "Atalanta",
    "Como", "Fiorentina", "Bologna", "Torino",
]
NAZIONALI_TOP = ["Italy", "Spain", "France", "England", "Germany", "Portugal",
                 "Netherlands", "Belgium", "Croatia"]
# Suggerimenti per "squadra del cuore" (si aggiungono in automatico quelle presenti nei dati)
SQUADRE_NOTE = [
    "Atalanta", "Avellino", "Bari", "Bologna", "Brescia", "Cagliari", "Carrarese", "Catanzaro",
    "Cesena", "Cittadella", "Como", "Cremonese", "Empoli", "Entella", "Fiorentina", "Frosinone",
    "Genoa", "Inter", "Juve Stabia", "Juventus", "Lazio", "Lecce", "Mantova", "Milan", "Modena",
    "Monza", "Napoli", "Padova", "Palermo", "Parma", "Pescara", "Pisa", "Reggiana", "Roma",
    "Salernitana", "Sampdoria", "Sassuolo", "Spezia", "Südtirol", "Torino", "Udinese",
    "Venezia", "Verona", "Italia",
]
# Tennis: partite con almeno uno di questi giocatori, più semifinali e finali
TENNISTI = ["Sinner", "Musetti", "Cobolli", "Darderi", "Arnaldi", "Sonego", "Berrettini",
            "Bellucci", "Nardi", "Paolini", "Cocciaretto", "Bronzetti", "Errani"]

# ---------------------------------------------------------------------------
# COMPETIZIONI SU ESPN: cosa seguire e dove si vede.
# I diritti TV cambiano di rado: controlla i canali a inizio stagione.
#   solo_squadre: tiene solo le partite con almeno una di queste squadre
#   canale_se:    canale diverso se gioca una certa squadra
#   Scrivere "(gratis)" nel canale fa comparire l'etichetta GRATIS.
# ---------------------------------------------------------------------------
COMPETIZIONI = [
    {"path": "soccer/ita.1", "nome": "Serie A", "sport": "calcio", "durata": 110, "fd": "serie-a",
     "canale": "DAZN (3 partite a turno anche Sky / NOW)"},
    {"path": "soccer/ita.2", "nome": "Serie B", "sport": "calcio", "durata": 110,
     "canale": "DAZN · Prime Video · LaB Channel"},
    {"path": "soccer/ita.coppa_italia", "nome": "Coppa Italia", "sport": "calcio", "durata": 110,
     "canale": "Mediaset Infinity (gratis)"},
    {"path": "soccer/uefa.champions", "nome": "Champions League", "sport": "calcio", "durata": 110, "fd": "champions-league",
     "canale": "Sky / NOW (1 partita a turno su Prime Video)"},
    {"path": "soccer/uefa.europa", "nome": "Europa League", "sport": "calcio", "durata": 110, "fd": "europa-league",
     "canale": "Sky / NOW", "solo_squadre": SQUADRE_ITALIANE},
    {"path": "soccer/uefa.europa.conf", "nome": "Conference League", "sport": "calcio", "durata": 110, "fd": "conference-league",
     "canale": "Sky / NOW", "solo_squadre": SQUADRE_ITALIANE},
    {"path": "soccer/uefa.nations", "nome": "Nations League", "sport": "calcio", "durata": 110,
     "canale": "Sky / NOW · Mediaset Infinity", "leghe_nl": True,
     "canale_se": {"Italy": "RaiPlay (gratis) · Rai\u00a01"}},
    {"path": "soccer/eng.1", "nome": "Premier League", "sport": "calcio", "durata": 110, "fd": "epl",
     "canale": "Sky / NOW"},
    {"path": "soccer/esp.1", "nome": "LaLiga", "sport": "calcio", "durata": 110, "fd": "la-liga",
     "canale": "DAZN"},
    {"path": "soccer/ger.1", "nome": "Bundesliga", "sport": "calcio", "durata": 110, "fd": "bundesliga",
     "canale": "Sky / NOW"},
    {"path": "soccer/fra.1", "nome": "Ligue 1", "sport": "calcio", "durata": 110, "fd": "ligue-1",
     "canale": "DAZN"},
    {"path": "soccer/ned.1", "nome": "Eredivisie", "sport": "calcio", "durata": 110, "fd": "eredivisie",
     "canale": "Sky / NOW"},
    {"path": "racing/f1", "nome": "Formula 1", "sport": "f1", "durata": 120, "jolpica": True,
     "canale": "Sky / NOW"},
    {"path": "tennis/atp", "nome": "ATP", "sport": "tennis", "durata": 120,
     "canale": "Sky / NOW · SuperTennix"},
    {"path": "tennis/wta", "nome": "WTA", "sport": "tennis", "durata": 110,
     "canale": "Sky / NOW · SuperTennix"},
    {"path": "basketball/nba", "nome": "NBA", "sport": "basket", "durata": 150,
     "canale": "Sky / NOW"},
]

MOTOGP_CANALE = "Sky / NOW"
# Sessioni MotoGP da includere: sigla ufficiale -> (nome, durata in minuti)
MOTOGP_SESSIONI = {"FP1": ("Prove libere 1", 45), "PR": ("Practice", 60), "FP2": ("Prove libere 2", 30),
                   "Q1": ("Qualifiche 1", 15), "Q2": ("Qualifiche 2", 15), "SPR": ("Sprint", 30), "RAC": ("Gara", 45)}
# Sessioni F1 da includere (prove libere escluse)
SESSIONI_F1 = {"qual": ("Qualifiche", 60), "sprint": ("Sprint", 45), "race": ("Gara", 120)}

TRADUZIONI = {
    "Italy": "Italia", "Spain": "Spagna", "France": "Francia", "England": "Inghilterra",
    "Germany": "Germania", "Belgium": "Belgio", "Croatia": "Croazia",
    "Netherlands": "Olanda", "Turkey": "Turchia", "Türkiye": "Turchia", "Portugal": "Portogallo",
    "Czechia": "Rep. Ceca", "Czech Republic": "Rep. Ceca", "Greece": "Grecia", "Norway": "Norvegia",
    "Denmark": "Danimarca", "Serbia": "Serbia", "Switzerland": "Svizzera", "Austria": "Austria",
    "Scotland": "Scozia", "Wales": "Galles", "Northern Ireland": "Irlanda del Nord", "Ireland": "Irlanda",
    "Republic of Ireland": "Irlanda", "Poland": "Polonia", "Sweden": "Svezia", "Finland": "Finlandia",
    "Hungary": "Ungheria", "Romania": "Romania", "Ukraine": "Ucraina", "Slovakia": "Slovacchia",
    "Slovenia": "Slovenia", "Bosnia-Herzegovina": "Bosnia", "Georgia": "Georgia", "Albania": "Albania",
    "Iceland": "Islanda", "Israel": "Israele", "Montenegro": "Montenegro", "Cyprus": "Cipro",
    "Armenia": "Armenia", "Latvia": "Lettonia", "Lithuania": "Lituania", "Estonia": "Estonia",
    "North Macedonia": "Macedonia del Nord", "Bulgaria": "Bulgaria", "Kosovo": "Kosovo",
    "Internazionale": "Inter", "AC Milan": "Milan", "AS Roma": "Roma",
}
TURNI = {"final": "Finale", "semifinal": "Semifinale", "quarterfinal": "Quarti",
         "round 1": "1° turno", "round 2": "2° turno", "round 3": "3° turno", "round 4": "Ottavi",
         "round of 16": "Ottavi", "round of 32": "Sedicesimi"}
GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
MESI = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]


# ---------------------------------------------------------------------------
# Utilità
# ---------------------------------------------------------------------------
ESPN_HOST = ["https://site.api.espn.com", "https://site.web.api.espn.com"]  # il secondo è di riserva
ERRORI = {}  # fonte -> numero di richieste fallite in questa esecuzione


def scarica(url, fonte="altro"):
    """Scarica un JSON. Se una fonte non risponde, avvisa e restituisce {} senza fermare lo script."""
    intestazioni = {"User-Agent": "Mozilla/5.0 (compatible; sport-in-tv/1.0)", "Accept": "application/json"}
    if fonte == "espn":  # ESPN blocca le richieste che non sembrano arrivare da un browser
        intestazioni = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
        }
    try:
        req = urllib.request.Request(url, headers=intestazioni)
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.load(r)
    except Exception as e:
        ERRORI[fonte] = ERRORI.get(fonte, 0) + 1
        print(f"[avviso] {url}: {e}")
        return None


def scarica_espn(percorso):
    """Prova i due indirizzi di ESPN; ricorda quello che funziona per il resto dell'esecuzione."""
    for host in list(ESPN_HOST):
        dati = scarica(f"{host}{percorso}", "espn")
        if dati is not None:
            if ESPN_HOST[0] != host:
                ESPN_HOST.remove(host)
                ESPN_HOST.insert(0, host)
            return dati
    ERRORI["espn_irraggiungibile"] = ERRORI.get("espn_irraggiungibile", 0) + 1
    return {}


def parse_data(s):
    """Accetta 2026-09-25T18:45Z, 2026-09-25T18:45:00+02:00, 2026-09-25T18:45:00+0200."""
    s = s.strip().replace("Z", "+00:00")
    s = re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", s)
    if re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d[+-]", s):
        s = s[:16] + ":00" + s[16:]
    d = datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=TZ)


def it(nome):
    return TRADUZIONI.get(nome, nome)


PAESI = {
    "Japan": "Giappone", "Thailand": "Thailandia", "Malaysia": "Malesia", "Spain": "Spagna",
    "Spanish": "Spagna", "France": "Francia", "French": "Francia", "Italy": "Italia",
    "Italian": "Italia", "Germany": "Germania", "German": "Germania", "Netherlands": "Olanda",
    "Dutch": "Olanda", "Hungary": "Ungheria", "Hungarian": "Ungheria", "Belgium": "Belgio",
    "Belgian": "Belgio", "Portugal": "Portogallo", "Portuguese": "Portogallo", "Brazil": "Brasile",
    "Brazilian": "Brasile", "Great Britain": "Gran Bretagna", "British": "Gran Bretagna",
    "Americas": "Americhe", "United States": "USA", "Mexico": "Messico", "Mexico City": "Città del Messico",
    "Czech Republic": "Rep. Ceca", "Czechia": "Rep. Ceca", "Chinese": "Cina", "China": "Cina",
    "Australian": "Australia", "Austrian": "Austria", "Canadian": "Canada", "Japanese": "Giappone",
    "Saudi Arabian": "Arabia Saudita", "Saudi Arabia": "Arabia Saudita", "Monaco": "Monaco",
    "Azerbaijan": "Azerbaijan", "Singapore": "Singapore", "Qatar": "Qatar", "Abu Dhabi": "Abu Dhabi",
    "Las Vegas": "Las Vegas", "Miami": "Miami", "Emilia Romagna": "Emilia Romagna",
    "San Marino": "San Marino", "Valencia": "Valencia", "Indonesian": "Indonesia",
    "Aragon": "Aragón", "Catalunya": "Catalogna", "Barcelona": "Barcellona",
}


# Parole da tradurre quando la pagina è in inglese (nomi GP, fasi, nazionali, canali)
PAROLE_EN = {
    "Giappone": "Japan", "Thailandia": "Thailand", "Malesia": "Malaysia", "Spagna": "Spain",
    "Francia": "France", "Italia": "Italy", "Germania": "Germany", "Olanda": "Netherlands",
    "Ungheria": "Hungary", "Belgio": "Belgium", "Portogallo": "Portugal", "Brasile": "Brazil",
    "Gran Bretagna": "Great Britain", "Americhe": "Americas", "Messico": "Mexico",
    "Città del Messico": "Mexico City", "Rep. Ceca": "Czechia", "Cina": "China",
    "Arabia Saudita": "Saudi Arabia", "Catalogna": "Catalunya", "Barcellona": "Barcelona",
    "Inghilterra": "England", "Croazia": "Croatia", "Turchia": "Turkey", "Svizzera": "Switzerland",
    "Prove libere": "Practice", "1° set": "Set 1", "2° set": "Set 2", "3° set": "Set 3",
    "4° set": "Set 4", "5° set": "Set 5", "Round di": "Round",
    "Qualifiche": "Qualifying", "Gara": "Race", "Quarti": "Quarterfinal", "Semifinale": "Semifinal",
    "Finale": "Final", "Ottavi": "Round of 16", "Sedicesimi": "Round of 32",
    "1° turno": "Round 1", "2° turno": "Round 2", "3° turno": "Round 3",
    "in differita": "delayed", "Ritirato": "Retired", "giri": "laps", "giro": "lap", "3 partite a turno anche": "3 matches per round also on",
    "1 partita a turno su": "1 match per round on", "Serie A1 Femminile": "Women's Serie A1",
    "Serie A Basket": "Italian Serie A (basket)", "Lega A": "League A", "Lega B": "League B",
    "Lega C": "League C", "Lega D": "League D",
    # nomi propri che non vanno tradotti
    "Coppa Italia": "Coppa Italia", "Rai Sport": "Rai Sport", "Italia 1": "Italia 1",
}


# Nome del paese (inglese o italiano) o nazionalità -> codice ISO, per mostrare la bandiera
_ISO = {
    "it": "italy, italia, italian", "be": "belgium, belgio, belgian", "tr": "türkiye, turkey, turchia, turkish",
    "fr": "france, francia, french", "ge": "georgia, georgian", "gb-nir": "northern ireland, irlanda del nord",
    "am": "armenia, armenian", "lv": "latvia, lettonia, latvian", "pl": "poland, polonia, polish",
    "ba": "bosnia-herzegovina, bosnia and herzegovina, bosnia", "se": "sweden, svezia, swedish",
    "ro": "romania, romanian", "hu": "hungary, ungheria, hungarian", "ua": "ukraine, ucraina, ukrainian",
    "me": "montenegro", "cy": "cyprus, cipro, cypriot", "cz": "czechia, czech republic, rep. ceca, czech",
    "hr": "croatia, croazia, croatian", "gb-eng": "england, inghilterra", "es": "spain, spagna, spanish",
    "rs": "serbia, serbian", "nl": "netherlands, olanda, dutch", "de": "germany, germania, german",
    "gr": "greece, grecia, greek", "no": "norway, norvegia, norwegian", "pt": "portugal, portogallo, portuguese",
    "dk": "denmark, danimarca, danish", "gb-wls": "wales, galles, welsh", "gb-sct": "scotland, scozia, scottish",
    "ch": "switzerland, svizzera, swiss", "at": "austria, austrian", "ie": "ireland, republic of ireland, irlanda, irish",
    "fi": "finland, finlandia, finnish", "sk": "slovakia, slovacchia, slovak", "si": "slovenia, slovenian",
    "al": "albania, albanian", "is": "iceland, islanda, icelandic", "il": "israel, israele, israeli",
    "lt": "lithuania, lituania, lithuanian", "ee": "estonia, estonian", "mk": "north macedonia, macedonia del nord",
    "bg": "bulgaria, bulgarian", "xk": "kosovo", "kz": "kazakhstan, kazakh", "az": "azerbaijan",
    "by": "belarus", "md": "moldova", "lu": "luxembourg, lussemburgo", "mt": "malta", "fo": "faroe islands",
    "ad": "andorra", "sm": "san marino", "li": "liechtenstein", "gi": "gibraltar",
    "gb": "great britain, united kingdom, gran bretagna, british", "us": "usa, united states, stati uniti, american",
    "au": "australia, australian", "ar": "argentina, argentine, argentinian", "br": "brazil, brasile, brazilian",
    "ca": "canada, canadian", "jp": "japan, giappone, japanese", "cn": "china, cina, chinese",
    "mc": "monaco, monegasque", "nz": "new zealand, nuova zelanda, new zealander", "th": "thailand, thai",
    "mx": "mexico, messico, mexican", "za": "south africa, sudafrica, south african", "cl": "chile, cile, chilean",
    "co": "colombia, colombian", "ru": "russia, russian", "in": "india, indian", "id": "indonesia, indonesian",
    "my": "malaysia, malesia, malaysian", "kr": "south korea, korea, corea del sud, korean",
}
PAESI_ISO = {n.strip(): iso for iso, nomi in _ISO.items() for n in nomi.split(",")}


def iso_di(nome):
    """'Italy' / 'Italia' / 'Italian' -> 'it' (None se non è un paese)."""
    n = unicodedata.normalize("NFC", (nome or "").strip().lower())
    return PAESI_ISO.get(n)


def nome_gp(s):
    """'GRAND PRIX OF JAPAN', 'Japanese Grand Prix', 'Japan GP' -> 'GP Giappone'."""
    s = re.sub(r"\s+", " ", s).strip().title()
    s = re.sub(r"(?i)^(formula 1\s+)?(.*?)\b(grand prix|gran premio|gp)\b(\s+(of|de|di|du|do|della|d'))?\s*", r"\2 ", s).strip()
    s = re.sub(r"(?i)\b(formula 1|motogp|\d{4})\b", "", s).strip(" -·")
    for en, it_ in sorted(PAESI.items(), key=lambda x: -len(x[0])):
        if s.lower() == en.lower() or s.lower().endswith(" " + en.lower()) or s.lower().startswith(en.lower() + " "):
            s = it_
            break
    return f"GP {s}" if s else "Gran Premio"


def contiene(nomi, lista):
    return any(s.lower() in (n or "").lower() for n in nomi for s in lista)


def uid_per(*parti):
    return hashlib.sha1("|".join(str(p) for p in parti).encode()).hexdigest()[:16]


def evento(sport, inizio, durata, titolo, competizione, canale, uid, lega=None, squadre=(), risultato=None, live=None,
           gruppo=None, riga=None, turno=None, bandiere=None, loghi=None):
    """lega = competizione per i filtri delle preferenze; squadre = per la squadra del cuore."""
    return {"sport": sport, "inizio": inizio, "fine": inizio + timedelta(minutes=durata),
            "titolo": titolo, "competizione": competizione, "canale": canale, "uid": uid,
            "lega": lega or competizione.split(" · ")[0], "squadre": [q for q in squadre if q],
            "risultato": risultato, "live": live,
            # gruppo = intestazione (es. "Formula 1 · GP Azerbaijan"), riga = cosa c'è scritto sotto
            "gruppo": gruppo or competizione.split(" · ")[0], "riga": riga or titolo, "turno": turno,
            "cronaca": [], "stats": [], "formazioni": None, "classifica": None,
            "bandiere": bandiere or [iso_di(q) for q in squadre if q] or None, "loghi": loghi}


def finito(x):
    """True se ESPN segna la partita/evento come concluso."""
    t = (x.get("status") or {}).get("type") or {}
    return t.get("state") == "post" or bool(t.get("completed"))


def slug(s):
    """'Serie B' -> 'serie-b', 'Südtirol' -> 'sudtirol' (uguale alla funzione della pagina)."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


# ---------------------------------------------------------------------------
# Fonti
# ---------------------------------------------------------------------------
DETTAGLI_MAX = [120]  # al massimo 120 partite con statistiche/formazioni per esecuzione
STATS_CALCIO = ["possessionPct", "totalShots", "shotsOnTarget", "wonCorners", "saves", "foulsCommitted",
                "offsides", "yellowCards", "redCards", "totalPasses", "accuratePasses", "totalTackles", "interceptions"]


def minuto_num(m):
    """"45'+2'" -> 45.02, "67'" -> 67: serve per ordinare la cronaca."""
    n = re.findall(r"\d+", m or "")
    return int(n[0]) + (int(n[1]) / 100 if len(n) > 1 else 0) if n else 999


def cronaca_espn(dettagli, lato_id):
    """Gol, rigori, autogol, rigori sbagliati e cartellini dai 'details' del tabellone ESPN."""
    out = []
    for d in dettagli:
        tipo = ((d.get("type") or {}).get("text") or "").lower()
        atleti = d.get("athletesInvolved") or []
        chi = atleti[0].get("displayName", "") if atleti else ""
        if d.get("redCard") or "red card" in tipo:
            t = "rosso"
        elif d.get("yellowCard") or "yellow card" in tipo:
            t = "giallo"
        elif "penalty" in tipo and ("miss" in tipo or "saved" in tipo):
            t = "rig_sbagliato"
        elif d.get("ownGoal") or "own goal" in tipo:
            t = "autogol"
        elif d.get("scoringPlay") or "goal" in tipo:
            t = "rigore" if d.get("penaltyKick") or "penalty" in tipo else "gol"
        else:
            continue
        out.append({"min": (d.get("clock") or {}).get("displayValue", ""), "tipo": t, "chi": chi, "altro": "",
                    "lato": lato_id.get(str((d.get("team") or {}).get("id")), 0)})
    return sorted(out, key=lambda x: minuto_num(x["min"]))


def dettagli_espn(path, evento_id, lato_id):
    """Statistiche, formazioni e cambi dal riepilogo ESPN della partita."""
    dati = scarica_espn(f"/apis/site/v2/sports/{path}/summary?event={evento_id}") or {}
    stats = {}
    for sq in (dati.get("boxscore") or {}).get("teams", []):
        lato = lato_id.get(str((sq.get("team") or {}).get("id")), 0)
        for st in sq.get("statistics", []):
            if st.get("name") in STATS_CALCIO:
                stats.setdefault(st["name"], ["", ""])[lato] = st.get("displayValue", "")
    formazioni, cambi = [{}, {}], []
    for ro in dati.get("rosters", []):
        lato = 1 if ro.get("homeAway") == "away" else 0
        titolari, panchina = [], []
        for g in ro.get("roster", []):
            a = g.get("athlete") or {}
            voce = [g.get("jersey", ""), a.get("displayName", ""), (g.get("position") or {}).get("abbreviation", "")]
            (titolari if g.get("starter") else panchina).append(voce + [bool(g.get("subbedIn"))])
            if g.get("subbedIn"):
                uscito = ((g.get("subbedInFor") or {}).get("athlete") or {}).get("displayName", "")
                minuto = next(((p.get("clock") or {}).get("displayValue", "") for p in g.get("plays", []) or []
                               if p.get("substitution")), "")
                if minuto:
                    cambi.append({"min": minuto, "tipo": "cambio", "chi": a.get("displayName", ""), "altro": uscito, "lato": lato})
        formazioni[lato] = {"modulo": ro.get("formation", "") or "", "titolari": titolari, "panchina": panchina}
    return {"stats": [[k] + stats[k] for k in STATS_CALCIO if k in stats],
            "formazioni": formazioni if any(f.get("titolari") for f in formazioni) else None, "cambi": cambi}


def da_espn(cfg, inizio, fine):
    # ESPN accetta una sola data per richiesta: si chiede un giorno alla volta
    eventi_espn, visti_id = [], set()
    giorno = inizio.date()
    while giorno <= fine.date():
        dati = scarica_espn(f"/apis/site/v2/sports/{cfg['path']}/scoreboard?dates={giorno:%Y%m%d}&limit=100")
        for ev in dati.get("events", []):
            if ev.get("id") not in visti_id:
                visti_id.add(ev.get("id"))
                eventi_espn.append(ev)
        giorno += timedelta(days=1)
    risultati = []
    for ev in eventi_espn:
        # Formula 1: un evento per GP, con le sessioni dentro
        if cfg["path"] == "racing/f1":
            gp = ev.get("shortName") or ev.get("name", "Gran Premio")
            for sess in ev.get("competitions", []):
                tipo = (sess.get("type", {}).get("abbreviation") or "").lower()
                trovata = next((v for k, v in SESSIONI_F1.items() if k in tipo), None)
                if not trovata and tipo.startswith("fp"):  # FP1, FP2, FP3
                    trovata = (f"Prove libere {tipo[2:]}".strip(), 60)
                if trovata and "date" in sess:
                    nome, durata = trovata
                    risultati.append(evento(cfg["sport"], parse_data(sess["date"]), durata,
                                            nome_gp(gp), f"{cfg['nome']} · {nome}", cfg["canale"],
                                            uid_per(cfg["path"], ev.get("id"), sess.get("id", nome)), cfg["nome"],
                                            gruppo=f"{cfg['nome']} · {nome_gp(gp)}", riga=nome))
            continue

        # Tennis: un evento per torneo, con le partite dentro "groupings"
        if cfg["path"].startswith("tennis/"):
            torneo = ev.get("name", "Torneo")
            for gruppo in ev.get("groupings", []):
                if "single" not in (gruppo.get("grouping", {}).get("displayName", "singles")).lower():
                    continue
                for m in gruppo.get("competitions", []):
                    if not m.get("timeValid", True) or "date" not in m:
                        continue  # orario non ancora deciso
                    giocatori = [c.get("athlete", {}).get("displayName", "") for c in m.get("competitors", [])]
                    paesi = [iso_di((c.get("athlete", {}).get("flag") or {}).get("alt")) for c in m.get("competitors", [])]
                    if len([g for g in giocatori if g and g.upper() != "TBD"]) < 2:
                        continue  # giocatori non ancora noti
                    turno_en = m.get("round", {}).get("displayName", "")
                    turno = TURNI.get(turno_en.lower().rstrip("s"), turno_en)
                    importante = turno_en.lower().rstrip("s") in ("final", "semifinal", "semi-final")
                    titolo = " – ".join(g.split()[-1] for g in giocatori if g) or turno
                    ris = None
                    if finito(m):  # es. "6-4 7-5" dai game di ogni set
                        cc = m.get("competitors", [])
                        if len(cc) == 2:
                            s1 = [int(x.get("value", 0)) for x in cc[0].get("linescores", [])]
                            s2 = [int(x.get("value", 0)) for x in cc[1].get("linescores", [])]
                            ris = " ".join(f"{a}-{b}" for a, b in zip(s1, s2)) or None
                    risultati.append(evento(cfg["sport"], parse_data(m["date"]), cfg["durata"],
                                            titolo, f"{cfg['nome']} {torneo} · {turno}".strip(" ·"),
                                            cfg["canale"], uid_per(cfg["path"], m.get("id", titolo)), cfg["nome"],
                                            giocatori, ris, gruppo=f"{cfg['nome']} · {torneo}", turno=turno,
                                            bandiere=paesi))
            continue

        # Partite a squadre (calcio, basket)
        comp = (ev.get("competitions") or [{}])[0]
        casa = ospite = gol_casa = gol_ospite = None
        lato_id, loghi, nomi_en = {}, [None, None], [None, None]
        for c in comp.get("competitors", []):
            nome = c.get("team", {}).get("displayName")
            lato_id[str(c.get("team", {}).get("id") or c.get("id"))] = 1 if c.get("homeAway") == "away" else 0
            lato = 1 if c.get("homeAway") == "away" else 0
            loghi[lato], nomi_en[lato] = c.get("team", {}).get("logo"), nome
            if c.get("homeAway") == "away":
                ospite, gol_ospite = nome, c.get("score")
            else:
                casa, gol_casa = nome, c.get("score")
        cronaca = cronaca_espn(comp.get("details") or [], lato_id)
        if cfg.get("solo_squadre") and not contiene([casa, ospite], cfg["solo_squadre"]):
            continue
        canale = cfg["canale"]
        for squadra, c in cfg.get("canale_se", {}).items():
            if contiene([casa, ospite], [squadra]):
                canale = c
        titolo = f"{it(casa)} – {it(ospite)}" if casa and ospite else ev.get("name", "?")
        ris = None
        if (finito(comp) or finito(ev)) and gol_casa is not None and gol_ospite is not None:
            ris = f"{gol_casa}–{gol_ospite}"
        gruppo = cfg["nome"]
        if cfg.get("leghe_nl"):
            lega = leghe_nations().get(casa) or leghe_nations().get(ospite)
            gruppo = f"{cfg['nome']} · Lega {lega}" if lega else cfg["nome"]
        risultati.append(evento(cfg["sport"], parse_data(ev["date"]), cfg["durata"], titolo,
                                cfg["nome"], canale, uid_per(cfg["path"], ev.get("id", titolo)), cfg["nome"],
                                [it(casa), it(ospite)], ris, gruppo=gruppo,
                                bandiere=[iso_di(n) for n in nomi_en], loghi=loghi))
        risultati[-1]["cronaca"] = cronaca
        # Partite in corso o finite da poco: statistiche, formazioni e cambi (una richiesta in più ciascuna)
        stato = ((comp.get("status") or ev.get("status") or {}).get("type") or {}).get("state")
        recente = datetime.now(timezone.utc) - parse_data(ev["date"]) < timedelta(hours=36)
        if cfg["sport"] == "calcio" and stato in ("in", "post") and recente and DETTAGLI_MAX[0] > 0:
            DETTAGLI_MAX[0] -= 1
            extra = dettagli_espn(cfg["path"], ev.get("id"), lato_id)
            risultati[-1].update({k: v for k, v in extra.items() if k != "cambi"})
            risultati[-1]["cronaca"] = sorted(cronaca + extra.get("cambi", []), key=lambda x: minuto_num(x["min"]))
    return risultati


_LEGHE_NL = None


def leghe_nations():
    """Squadra -> lettera della lega (A, B, C, D), dalla classifica ESPN della Nations League."""
    global _LEGHE_NL
    if _LEGHE_NL is None:
        _LEGHE_NL = {}
        dati = scarica_espn("/apis/v2/sports/soccer/uefa.nations/standings") or {}
        for girone in dati.get("children", []):
            m = re.search(r"\b([A-D])\d", girone.get("name", "") + " " + girone.get("abbreviation", ""))
            if not m:
                continue
            for voce in (girone.get("standings") or {}).get("entries", []):
                nome = (voce.get("team") or {}).get("displayName")
                if nome:
                    _LEGHE_NL[nome] = m.group(1)
    return _LEGHE_NL


def da_fixturedownload(cfg, inizio, fine):
    """Riserva per il calcio (fixturedownload.com): calendario e risultati, senza chiave."""
    stagione = inizio.year if inizio.month >= 7 else inizio.year - 1
    dati = scarica(f"https://fixturedownload.com/feed/json/{cfg['fd']}-{stagione}", "fixturedownload") or []
    risultati = []
    for m in dati if isinstance(dati, list) else []:
        try:
            quando = datetime.strptime(m["DateUtc"], "%Y-%m-%d %H:%M:%SZ").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        if quando < inizio - timedelta(hours=3) or quando > fine:
            continue
        casa, ospite = it(m.get("HomeTeam") or "?"), it(m.get("AwayTeam") or "?")
        if cfg.get("solo_squadre") and not contiene([casa, ospite], cfg["solo_squadre"]):
            continue
        canale = cfg["canale"]
        for squadra, c in cfg.get("canale_se", {}).items():
            if contiene([casa, ospite], [squadra]):
                canale = c
        gc, go = m.get("HomeTeamScore"), m.get("AwayTeamScore")
        ris = f"{gc}–{go}" if gc is not None and go is not None else None
        risultati.append(evento(cfg["sport"], quando, cfg["durata"], f"{casa} – {ospite}", cfg["nome"], canale,
                                uid_per("fd", cfg["fd"], m.get("MatchNumber"), casa, ospite), cfg["nome"],
                                [casa, ospite], ris, gruppo=cfg["nome"]))
    return risultati


JOLPICA_SESSIONI = [("FirstPractice", "Prove libere 1", 60), ("SecondPractice", "Prove libere 2", 60),
                    ("ThirdPractice", "Prove libere 3", 60), ("SprintQualifying", "Qualifiche Sprint", 45),
                    ("Sprint", "Sprint", 45), ("Qualifying", "Qualifiche", 60)]


def secondi(t):
    """'1:43.615' -> 103.615"""
    try:
        parti = [float(x) for x in t.split(":")]
        return sum(v * 60 ** i for i, v in enumerate(reversed(parti)))
    except (ValueError, AttributeError):
        return None


def classifica_jolpica(stagione, gp_round, tipo):
    """Classifica di qualifiche ('qualifying'), sprint ('sprint') o gara ('results'):
    righe [posizione, pilota, bandiera, scuderia, tempo, distacco]."""
    dati = scarica(f"https://api.jolpi.ca/ergast/f1/{stagione}/{gp_round}/{tipo}/?format=json&limit=40", "jolpica") or {}
    gare = (((dati.get("MRData") or {}).get("RaceTable") or {}).get("Races")) or []
    if not gare:
        return None
    chiave = {"qualifying": "QualifyingResults", "sprint": "SprintResults", "results": "Results"}[tipo]
    righe, migliore, giri_primo = [], None, None
    for x in gare[0].get(chiave, []):
        d = x.get("Driver") or {}
        nome = f"{d.get('givenName', '')} {d.get('familyName', '')}".strip()
        pilota = [x.get("positionText") or x.get("position", ""), nome, iso_di(d.get("nationality")),
                  (x.get("Constructor") or {}).get("name", "")]
        if tipo == "qualifying":
            tempo = next((x.get(q) for q in ("Q3", "Q2", "Q1") if x.get(q) and x.get(q) not in ("—", "-")), "")
            sec = secondi(tempo)
            migliore = migliore if migliore is not None else sec
            distacco = f"+{sec - migliore:.3f}" if sec is not None and migliore is not None and sec > migliore else ""
            righe.append(pilota + [tempo, distacco])
        else:
            giri = int(x.get("laps") or 0)
            giri_primo = giri_primo or giri
            tempo = (x.get("Time") or {}).get("time", "")
            if tempo and not tempo.startswith("+"):
                righe.append(pilota + [tempo, ""])
            elif tempo:
                righe.append(pilota + ["", tempo])
            elif x.get("status", "").lower() in ("lapped", "finished") or x.get("status", "").startswith("+"):
                diff = (giri_primo or giri) - giri
                righe.append(pilota + ["", f"+{diff} {'giro' if diff == 1 else 'giri'}" if diff else ""])
            else:
                righe.append(pilota + ["", "Ritirato"])
    return righe or None


def da_jolpica(cfg, inizio, fine):
    """Formula 1 da Jolpica (successore di Ergast): tutte le sessioni con gli orari."""
    dati = scarica(f"https://api.jolpi.ca/ergast/f1/{inizio.year}/races/?format=json&limit=40", "jolpica") or {}
    gare = (((dati.get("MRData") or {}).get("RaceTable") or {}).get("Races")) or []
    risultati = []
    for g in gare:
        gp = nome_gp(g.get("raceName", "Gran Premio"))
        sessioni = [(g.get(k), nome, dur, k) for k, nome, dur in JOLPICA_SESSIONI]
        sessioni.append(({"date": g.get("date"), "time": g.get("time")}, "Gara", 120, "Race"))
        for info, nome, durata, chiave in sessioni:
            if not info or not info.get("date") or not info.get("time"):
                continue
            quando = parse_data(f"{info['date']}T{info['time']}")
            if quando < inizio - timedelta(hours=3) or quando > fine:
                continue
            risultati.append(evento("f1", quando, durata, gp, f"{cfg['nome']} · {nome}", cfg["canale"],
                                    uid_per("jolpica", g.get("season"), g.get("round"), chiave), cfg["nome"],
                                    gruppo=f"{cfg['nome']} · {gp}", riga=nome))
            tipo = {"Qualifying": "qualifying", "Sprint": "sprint", "Race": "results"}.get(chiave)
            if tipo and quando + timedelta(minutes=durata) < datetime.now(timezone.utc):
                risultati[-1]["classifica"] = classifica_jolpica(g.get("season"), g.get("round"), tipo)
    return risultati


def da_motogp(inizio, fine):
    dati = scarica(f"{MOTOGP}/events?seasonYear={inizio.year}&isFinished=false", "motogp") or []
    risultati = []
    for ev in dati if isinstance(dati, list) else []:
        try:
            if parse_data(ev["date_end"]) < inizio or parse_data(ev["date_start"]) > fine + timedelta(days=4):
                continue
        except (KeyError, ValueError):
            continue
        gp = nome_gp(ev.get("name") or "Gran Premio")
        for b in ev.get("broadcasts", []):
            if (b.get("category") or {}).get("name") != "MotoGP":
                continue
            sessione = MOTOGP_SESSIONI.get((b.get("shortname") or "").upper())
            if not sessione or not b.get("date_start"):
                continue
            nome, durata = sessione
            risultati.append(evento("motogp", parse_data(b["date_start"]), durata, gp,
                                    f"MotoGP · {nome}", MOTOGP_CANALE, uid_per("motogp", ev.get("id"), b.get("shortname")),
                                    gruppo=f"MotoGP · {gp}", riga=nome))
    return risultati


def da_extra(percorso):
    """Eventi scritti a mano in extra.json (orari in ora italiana)."""
    p = Path(percorso)
    if not p.exists():
        return []
    try:
        voci = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[avviso] extra.json non valido: {e}")
        return []
    risultati = []
    for v in voci:
        try:
            inizio = datetime.strptime(v["inizio"], "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
            sport = v["sport"] if v["sport"] in SPORT else "calcio"
            comp = v.get("competizione", SPORT[sport]["nome"])
            base, _, fase = comp.partition(" · ")
            gruppo = v.get("gruppo") or (f"{base} · {v['titolo']}" if fase else comp)
            riga = v.get("riga") or (fase or v["titolo"])
            if " – " in v["titolo"] and not v.get("squadre"):
                v["squadre"] = [x.strip() for x in v["titolo"].split(" – ")]
            risultati.append(evento(sport, inizio, int(v.get("durata", 90)), v["titolo"], comp, v.get("canale", ""),
                                    lega=v.get("lega"), squadre=v.get("squadre", []), live=v.get("live"),
                                    risultato=v.get("risultato"), gruppo=gruppo, riga=riga, turno=v.get("turno"), uid=
                                    uid_per("extra", v["titolo"], v["inizio"])))
            for k in ("cronaca", "stats", "formazioni", "classifica", "bandiere", "loghi"):
                if v.get(k):
                    risultati[-1][k] = v[k]
        except (KeyError, ValueError) as e:
            print(f"[avviso] voce extra.json ignorata ({e}): {v}")
    return risultati


# ---------------------------------------------------------------------------
# Calendario .ics
# ---------------------------------------------------------------------------
def ics_testo(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def ics_piega(riga):
    """Le righe .ics non devono superare 75 byte: quelle lunghe vanno spezzate."""
    if len(riga.encode()) <= 75:
        return riga
    pezzi, corrente = [], ""
    for ch in riga:
        if len((corrente + ch).encode()) > (75 if not pezzi else 74):
            pezzi.append(corrente)
            corrente = ch
        else:
            corrente += ch
    pezzi.append(corrente)
    return "\r\n ".join(pezzi)


def ics_calendario(eventi, adesso, nome="Sport in TV"):
    fmt = "%Y%m%dT%H%M%SZ"
    righe = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Sport in TV//IT", "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH", f"X-WR-CALNAME:{ics_testo(nome)}", "X-WR-TIMEZONE:Europe/Rome",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H", "X-PUBLISHED-TTL:PT6H",
    ]
    for e in eventi:
        emoji = SPORT[e["sport"]]["emoji"]
        righe += [
            "BEGIN:VEVENT",
            f"UID:{e['uid']}@sport-in-tv",
            f"DTSTAMP:{adesso.astimezone(timezone.utc):{fmt}}",
            f"DTSTART:{e['inizio'].astimezone(timezone.utc):{fmt}}",
            f"DTEND:{e['fine'].astimezone(timezone.utc):{fmt}}",
            f"SUMMARY:{ics_testo(emoji + ' ' + e['titolo'])}",
            f"DESCRIPTION:{ics_testo(e['competizione'] + chr(10) + 'Dove vederlo: ' + e['canale'])}",
            f"LOCATION:{ics_testo('📺 ' + e['canale'])}",
            "BEGIN:VALARM", "ACTION:DISPLAY",
            f"DESCRIPTION:{ics_testo(e['titolo'])}",
            f"TRIGGER:-PT{PROMEMORIA_MINUTI}M",
            "END:VALARM", "END:VEVENT",
        ]
    righe.append("END:VCALENDAR")
    return "\r\n".join(ics_piega(r) for r in righe) + "\r\n"


# ---------------------------------------------------------------------------
# Pagina HTML: i dati vengono inseriti come JSON e disegnati dal browser,
# così la stessa pagina può mostrare la vista "Per giorno" e "Per sport".
# ---------------------------------------------------------------------------
def pagina(eventi, adesso):
    dati = [{
        "id": e["uid"], "sport": e["sport"], "titolo": e["titolo"], "comp": e["competizione"],
        "canale": e["canale"], "gratis": "(gratis)" in e["canale"].lower(),
        "inizio": e["inizio"].isoformat(), "fine": e["fine"].isoformat(),
        "lega": e["lega"], "squadre": e["squadre"], "ris": e["risultato"], "live": e.get("live"),
        "gruppo": e["gruppo"], "riga": e["riga"], "turno": e.get("turno"),
        "cronaca": e.get("cronaca") or [], "stats": e.get("stats") or [], "formazioni": e.get("formazioni"),
        "classifica": e.get("classifica"), "bandiere": e.get("bandiere"), "loghi": e.get("loghi"),
    } for e in eventi]
    aggiornato = adesso.astimezone(TZ)
    json_sicuro = lambda x: json.dumps(x, ensure_ascii=False).replace("</", "<\\/")
    return (MODELLO
            .replace("{{DATI}}", json_sicuro(dati))
            .replace("{{SPORT}}", json_sicuro(SPORT))
            .replace("{{SQUADRE}}", json_sicuro(sorted(
                set(SQUADRE_NOTE) | set(TENNISTI) | {q for e in eventi for q in e["squadre"] if " " not in q or q in SQUADRE_NOTE},
                key=lambda x: x.lower())))
            .replace("{{AGGIORNATO_ISO}}", aggiornato.isoformat())
            .replace("{{DEMO}}", "true" if DEMO else "false")
            .replace("{{PASSATI}}", str(PASSATI))
            .replace("{{EN}}", json_sicuro(PAROLE_EN))
            .replace("{{PROMEMORIA}}", str(PROMEMORIA_MINUTI)))


MODELLO = r"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Sport in TV</title>
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Sport in TV">
<meta name="theme-color" content="#0b0d12">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='22' fill='%230b0d12'/><text x='50' y='68' font-size='56' text-anchor='middle'>📺</text></svg>">
<link rel="apple-touch-icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 180 180'><rect width='180' height='180' fill='%230b0d12'/><text x='90' y='122' font-size='100' text-anchor='middle'>📺</text></svg>">
<script>
  // Applica subito tema e lingua salvati, prima di disegnare la pagina (niente "lampo" di colore)
  try {
    const s = JSON.parse(localStorage.getItem("sport-in-tv:aspetto")) || {};
    if (s.tema) document.documentElement.dataset.tema = s.tema;
    if (s.lingua) document.documentElement.lang = s.lingua;
  } catch {}
</script>
<style>
  /* ---------- Colori: scuro di base, chiaro se scelto o se il telefono è in modalità chiara ---------- */
  :root {
    --bg: #0b0d12; --superficie: #151821; --superficie-2: #1e222d; --bordo: #262b38;
    --testo: #f3f4f7; --tenue: #9aa1b2; --debole: #626a7c;
    --accento: #ff5b3a; --accento-2: #ff9a3a; --gratis: #34d399; --live: #ff3b5c; --ombra: rgb(0 0 0 / .35);
    color-scheme: dark;
  }
  :root[data-tema="chiaro"] {
    --bg: #f2f3f6; --superficie: #ffffff; --superficie-2: #eceef3; --bordo: #e0e3ea;
    --testo: #10131a; --tenue: #586072; --debole: #99a0ad;
    --accento: #e8431f; --accento-2: #f97316; --gratis: #059669; --live: #e11d48; --ombra: rgb(16 19 26 / .10);
    color-scheme: light;
  }
  @media (prefers-color-scheme: light) {
    :root:not([data-tema]) {
      --bg: #f2f3f6; --superficie: #ffffff; --superficie-2: #eceef3; --bordo: #e0e3ea;
      --testo: #10131a; --tenue: #586072; --debole: #99a0ad;
      --accento: #e8431f; --accento-2: #f97316; --gratis: #059669; --live: #e11d48; --ombra: rgb(16 19 26 / .10);
      color-scheme: light;
    }
  }
  * { box-sizing: border-box; }
  [hidden] { display: none !important; }
  html { -webkit-text-size-adjust: 100%; }
  body {
    margin: 0; background: var(--bg); color: var(--testo); transition: background .2s, color .2s;
    font: 16px/1.4 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "Segoe UI", Roboto, sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  button { font: inherit; color: inherit; }
  .app { max-width: 720px; margin: 0 auto; padding: calc(env(safe-area-inset-top) + 18px) 16px 56px; }
  .emoji { font-family: "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif; line-height: 1; }

  /* ---------- Controlli rapidi: lingua e tema ---------- */
  .rapidi { display: flex; align-items: center; gap: 6px; }
  .lingua { display: flex; padding: 3px; border-radius: 10px; background: var(--superficie-2); border: 1px solid var(--bordo); }
  .lingua button { border: 0; background: transparent; padding: 5px 7px; border-radius: 7px; font-size: 11.5px; font-weight: 800; letter-spacing: .04em; color: var(--debole); cursor: pointer; }
  .lingua button.on { background: var(--superficie); color: var(--testo); box-shadow: 0 1px 3px var(--ombra); }
  .btn-icona {
    width: 36px; height: 36px; display: grid; place-items: center; border-radius: 11px; cursor: pointer; flex: none;
    background: var(--superficie); border: 1px solid var(--bordo); font-size: 17px; text-decoration: none; color: var(--testo);
  }
  .angolo { position: absolute; top: calc(env(safe-area-inset-top) + 14px); right: 16px; }

  /* ---------- Intestazione ---------- */
  .testata { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
  .logo { font-size: 25px; font-weight: 800; letter-spacing: -0.03em; margin: 0; white-space: nowrap; }
  .logo span { color: var(--accento); }
  .aggiornato { color: var(--debole); font-size: 11.5px; margin: 1px 0 0; }

  /* ---------- Sezioni: Oggi in TV / I miei eventi ---------- */
  .sezioni { position: sticky; top: 0; z-index: 6; background: var(--bg); margin: 12px -16px 0; padding: 8px 16px 10px; }
  .sezioni .interno {
    position: relative; display: grid; grid-template-columns: 1fr 1fr; padding: 5px; border-radius: 18px;
    background: var(--superficie); border: 1px solid var(--bordo); box-shadow: 0 4px 18px var(--ombra);
  }
  .sezioni .cursore {
    position: absolute; top: 5px; bottom: 5px; left: 5px; width: calc(50% - 5px); border-radius: 13px;
    background: linear-gradient(135deg, var(--accento), var(--accento-2));
    box-shadow: 0 6px 18px color-mix(in srgb, var(--accento) 40%, transparent);
    transition: transform .28s cubic-bezier(.3, .7, .2, 1);
  }
  .sezioni .interno[data-attiva="miei"] .cursore { transform: translateX(100%); }
  .sezioni button {
    position: relative; z-index: 1; display: flex; align-items: center; justify-content: center; gap: 8px;
    border: 0; background: transparent; padding: 10px 6px; border-radius: 13px; cursor: pointer;
    font-weight: 800; font-size: 14.5px; letter-spacing: -0.01em; color: var(--tenue); transition: color .2s;
  }
  .sezioni button .emoji { font-size: 17px; }
  .sezioni button .quanti { font-size: 11px; font-weight: 800; padding: 1px 7px; border-radius: 999px; background: var(--superficie-2); color: var(--tenue); }
  .sezioni button.on { color: #fff; }
  .sezioni button.on .quanti { background: rgb(255 255 255 / .25); color: #fff; }

  /* ---------- Prossimo evento ---------- */
  .hero {
    display: flex; align-items: center; gap: 12px; margin: 8px 0 4px; padding: 11px 14px;
    border-radius: 20px; border: 1px solid var(--bordo);
    background: radial-gradient(130% 150% at 0% 0%, color-mix(in srgb, var(--c) 30%, transparent), transparent 62%), var(--superficie);
  }
  .hero .icona { width: 46px; height: 46px; font-size: 26px; border-radius: 14px; }
  .hero .h-grande { font-size: 28px; font-weight: 800; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; line-height: 1.05; }
  .hero .h-grande small { font-size: 16px; color: var(--tenue); }
  .hero .h-grande.live { color: var(--live); }
  .hero .h-sotto { font-size: 12.5px; font-weight: 800; color: var(--c); margin-top: 2px; }
  .hero .h-sotto.live { color: var(--live); }
  .hero .testo { flex: 1; min-width: 0; }
  .hero .etichetta { font-size: 10.5px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; color: var(--c); }
  .hero .tit { font-size: 18px; font-weight: 800; letter-spacing: -0.02em; line-height: 1.2; margin: 2px 0 1px; }
  .hero .meta { color: var(--tenue); font-size: 13px; }
  .hero .quando { text-align: right; flex: none; }
  .hero .ora { font-size: 25px; font-weight: 800; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }
  .hero .tra { font-size: 12px; font-weight: 700; color: var(--c); }

  .icona {
    flex: none; display: grid; place-items: center; width: 50px; height: 50px; font-size: 28px; border-radius: 16px;
    background: color-mix(in srgb, var(--c) 18%, transparent); border: 1px solid color-mix(in srgb, var(--c) 35%, transparent);
  }

  /* ---------- Quadratini sport (Oggi e I miei) ---------- */
  .quadri { display: flex; gap: 6px; overflow-x: auto; scrollbar-width: none; margin: 0 -16px; padding: 6px 16px; }
  .quadri::-webkit-scrollbar { display: none; }
  .quadro {
    flex: none; position: relative; display: grid; place-items: center; width: 40px; height: 40px; border-radius: 12px;
    border: 1.5px solid var(--bordo); background: var(--superficie); cursor: pointer; font-size: 19px; padding: 0;
    transition: transform .12s, background .15s, border-color .15s;
  }
  .quadro:active { transform: scale(.93); }
  .quadro.on { border-color: var(--c, var(--accento)); background: color-mix(in srgb, var(--c, var(--accento)) 20%, var(--superficie)); }
  .quadro .n {
    position: absolute; top: -5px; right: -5px; min-width: 17px; height: 17px; padding: 0 4px; border-radius: 999px;
    display: grid; place-items: center; font: 800 10px/1 -apple-system, sans-serif; color: var(--tenue);
    background: var(--superficie-2); border: 1.5px solid var(--bg);
  }
  .quadro.on .n { background: var(--c, var(--accento)); color: #fff; }
  .quadro.spento { opacity: .35; filter: grayscale(1); cursor: default; }
  .quadro.spento:active { transform: none; }
  .quadro.tutti { width: auto; padding: 0 11px; font-size: 12.5px; font-weight: 800; color: var(--tenue); }
  .quadro.tutti.on { color: var(--testo); }
  .quadro.fil { width: auto; gap: 6px; padding: 0 11px; display: inline-flex; font-size: 13px; font-weight: 800; color: var(--testo); margin-left: auto; }
  /* Filtri resta sempre visibile a destra, anche se i quadratini scorrono */
  .quadro.fil { position: sticky; right: 0; z-index: 1; box-shadow: -14px 0 12px -2px var(--bg); }
  .quadro.fil .n { position: static; border: 0; background: var(--accento); color: #fff; }
  .separa { flex: none; width: 1px; margin: 6px 2px; background: var(--bordo); }

  /* ---------- Striscia dei giorni (compatta) ---------- */
  .striscia { display: flex; gap: 5px; overflow-x: auto; scrollbar-width: none; margin: 2px -16px 0; padding: 4px 16px 2px; }
  .striscia::-webkit-scrollbar { display: none; }
  .giorno-btn {
    flex: none; width: 45px; display: flex; flex-direction: column; align-items: center; gap: 1px;
    padding: 6px 0 5px; border-radius: 13px; border: 1px solid var(--bordo); background: var(--superficie); cursor: pointer;
  }
  .giorno-btn .gs { font-size: 9px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; color: var(--debole); }
  .giorno-btn .gn { font-size: 16.5px; font-weight: 800; letter-spacing: -0.02em; line-height: 1.1; }
  .giorno-btn .punti { display: flex; gap: 2.5px; height: 5px; margin-top: 2px; }
  .giorno-btn .punti i { width: 4px; height: 4px; border-radius: 50%; background: var(--c); }
  .giorno-btn.vuoto-g { opacity: .4; }
  .giorno-btn.on { background: var(--accento); border-color: var(--accento); color: #fff; }
  .giorno-btn.on .gs { color: rgb(255 255 255 / .85); }
  .giorno-btn.on .punti i { box-shadow: 0 0 0 1px rgb(255 255 255 / .7); }
  .giorno-btn.tutti .gn { font-size: 15px; line-height: 1.2; }
  .riassunto { font-size: 12.5px; color: var(--tenue); margin: 2px 2px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  /* ---------- Titoli ---------- */
  .giorno-tit { display: flex; align-items: baseline; gap: 8px; margin: 18px 2px 10px; }
  .giorno-tit b { font-size: 19px; font-weight: 800; letter-spacing: -0.02em; }
  .giorno-tit span { color: var(--debole); font-size: 13.5px; }
  .fascia { display: flex; align-items: center; gap: 8px; margin: 18px 2px 10px; font-size: 12.5px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: var(--tenue); }
  .fascia::after { content: ""; flex: 1; height: 1px; background: var(--bordo); }
  .fascia .emoji { font-size: 15px; }
  .fascia.live-ora { color: var(--live); }
  .pallino-live { width: 9px; height: 9px; border-radius: 50%; background: var(--live); box-shadow: 0 0 0 4px color-mix(in srgb, var(--live) 25%, transparent); animation: pulsa 1.6s ease-in-out infinite; }

  /* ---------- Card evento ---------- */
  .card {
    display: grid; grid-template-columns: 38px minmax(0, 1.15fr) minmax(0, 1fr) auto;
    align-items: start; gap: 10px; padding: 11px 12px 11px 11px; margin-bottom: 8px;
    background: var(--superficie); border: 1px solid var(--bordo); border-radius: 14px;
  }
  .card.in-corso { border-color: color-mix(in srgb, var(--live) 65%, var(--bordo)); }
  .card.cuore { border-color: color-mix(in srgb, #facc15 60%, var(--bordo)); }
  .card .icona { width: 38px; height: 38px; font-size: 22px; border-radius: 11px; align-self: center; }
  .card .info { min-width: 0; }
  .card .comp { font-size: 11.5px; font-weight: 700; color: var(--c); line-height: 1.25; }
  .card .stella { color: #eab308; font-size: 12px; margin-left: 3px; }
  .card h3 { margin: 1px 0 0; font-size: 15px; font-weight: 800; line-height: 1.22; letter-spacing: -0.01em; }
  .card .dove { border-left: 1px solid var(--bordo); padding-left: 10px; min-width: 0; }
  .card .dove small { display: block; font-size: 9.5px; font-weight: 800; letter-spacing: .1em; color: var(--debole); text-transform: uppercase; margin-bottom: 2px; }
  .card .dove ul { margin: 0; padding: 0; list-style: none; }
  .card .dove li { position: relative; padding-left: 10px; font-size: 12px; line-height: 1.35; }
  .card .dove li::before { content: ""; position: absolute; left: 0; top: .55em; width: 4px; height: 4px; border-radius: 50%; background: var(--c); }
  .card .dove li .free { color: var(--gratis); font-weight: 700; }
  .card .lato { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
  .card .ora { font-size: 17px; font-weight: 800; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; line-height: 1.1; }
  .avvisami { display: grid; place-items: center; width: 30px; height: 30px; border-radius: 9px; background: var(--superficie-2); text-decoration: none; font-size: 15px; }
  .avvisami:active { transform: scale(.92); }
  .badge.live { font-size: 9px; font-weight: 800; letter-spacing: .06em; padding: 2px 6px; border-radius: 5px; color: #fff; background: var(--live); animation: pulsa 1.6s ease-in-out infinite; }
  @keyframes pulsa { 50% { opacity: .55; } }
  .vuoto { text-align: center; color: var(--tenue); padding: 48px 16px; }
  .vuoto .emoji { font-size: 44px; display: block; margin-bottom: 10px; }
  footer { margin-top: 30px; text-align: center; font-size: 12.5px; color: var(--debole); line-height: 1.7; }

  /* ---------- Accesso ---------- */
  .schermo { position: relative; min-height: calc(100dvh - 40px); display: flex; flex-direction: column; }
  .accesso { justify-content: center; text-align: center; padding: 64px 0 30px; }
  .accesso .marchio {
    width: 80px; height: 80px; margin: 0 auto 16px; display: grid; place-items: center; font-size: 42px; border-radius: 25px;
    background: linear-gradient(145deg, var(--accento), var(--accento-2)); box-shadow: 0 12px 40px color-mix(in srgb, var(--accento) 40%, transparent);
  }
  .accesso h1 { font-size: 33px; font-weight: 800; letter-spacing: -0.03em; margin: 0; }
  .accesso h1 span { color: var(--accento); }
  .accesso .slogan { color: var(--tenue); margin: 8px auto 26px; max-width: 320px; font-size: 15.5px; }
  .bottoni { display: grid; gap: 10px; max-width: 360px; width: 100%; margin: 0 auto; }
  .btn {
    display: flex; align-items: center; justify-content: center; gap: 10px; width: 100%; padding: 14px 18px;
    border-radius: 14px; border: 1px solid var(--bordo); cursor: pointer; background: var(--superficie);
    color: var(--testo); font-size: 15.5px; font-weight: 700; text-decoration: none;
  }
  .btn.primario { background: linear-gradient(135deg, var(--accento), var(--accento-2)); border-color: transparent; color: #fff; }
  .btn.testo { background: transparent; border-color: transparent; color: var(--tenue); font-weight: 600; }
  .btn:disabled { opacity: .45; cursor: default; }
  .tabs-accesso { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; padding: 4px; border-radius: 14px; background: var(--superficie-2); margin-bottom: 4px; }
  .tabs-accesso button { border: 0; background: transparent; padding: 10px; border-radius: 10px; font-weight: 700; font-size: 14.5px; color: var(--tenue); cursor: pointer; }
  .tabs-accesso button.on { background: var(--superficie); color: var(--testo); box-shadow: 0 1px 3px var(--ombra); }
  .etichetta-campo { display: block; text-align: left; font-size: 12.5px; font-weight: 700; color: var(--tenue); margin: 4px 2px -4px; }
  .campo { width: 100%; padding: 13px 14px; border-radius: 12px; border: 1px solid var(--bordo); background: var(--superficie); color: var(--testo); font: inherit; font-size: 15.5px; }
  .campo:focus { outline: 2px solid color-mix(in srgb, var(--accento) 60%, transparent); outline-offset: 1px; }
  .errore { color: var(--live); font-size: 13.5px; font-weight: 600; min-height: 18px; margin: 2px 0 0; text-align: left; }
  .separatore { display: flex; align-items: center; gap: 12px; color: var(--debole); font-size: 12px; margin: 2px 0; }
  .separatore::before, .separatore::after { content: ""; flex: 1; height: 1px; background: var(--bordo); }
  .nota { margin: 18px auto 0; max-width: 360px; font-size: 12.5px; color: var(--tenue); line-height: 1.5; background: var(--superficie-2); border-radius: 12px; padding: 10px 12px; }

  /* ---------- Preferenze ---------- */
  .testata-pref { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
  .passo { font-size: 12px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; color: var(--accento); }
  .preferenze h2 { font-size: 26px; font-weight: 800; letter-spacing: -0.02em; margin: 6px 0 4px; }
  .preferenze .sottotitolo { color: var(--tenue); margin: 0 0 16px; font-size: 14.5px; }
  .preferenze h4 { font-size: 12.5px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: var(--debole); margin: 24px 0 10px; }
  .griglia-sport { display: grid; grid-template-columns: repeat(auto-fill, minmax(96px, 1fr)); gap: 9px; }
  .scelta-sport {
    position: relative; display: flex; flex-direction: column; align-items: center; gap: 7px; padding: 14px 6px 12px;
    border-radius: 16px; border: 1.5px solid var(--bordo); background: var(--superficie); cursor: pointer;
    font-size: 13.5px; font-weight: 700; color: var(--tenue);
  }
  .scelta-sport .emoji { font-size: 30px; }
  .scelta-sport.on { border-color: var(--c); color: var(--testo); background: color-mix(in srgb, var(--c) 14%, var(--superficie)); }
  .scelta-sport.on::after { content: "✓"; position: absolute; top: 7px; right: 8px; width: 18px; height: 18px; border-radius: 50%; display: grid; place-items: center; font-size: 11px; font-weight: 900; color: #fff; background: var(--c); }
  .blocco-leghe { margin-top: 12px; padding: 12px; border-radius: 14px; background: var(--superficie); border: 1px solid var(--bordo); }
  .blocco-leghe .tit { display: flex; align-items: center; gap: 8px; font-weight: 800; font-size: 14px; margin-bottom: 10px; }
  .blocco-leghe .tit .emoji { font-size: 20px; }
  .leghe, .scelte { display: flex; flex-wrap: wrap; gap: 7px; }
  .lega { padding: 7px 12px; border-radius: 999px; border: 1px solid var(--bordo); background: transparent; font-size: 13.5px; font-weight: 600; color: var(--tenue); cursor: pointer; }
  .lega.on { color: var(--testo); border-color: var(--c); background: color-mix(in srgb, var(--c) 16%, transparent); }
  .lega.on::before { content: "✓ "; color: var(--c); font-weight: 900; }
  .cerca-squadra { position: relative; }
  .suggerimenti { position: absolute; left: 0; right: 0; top: calc(100% + 4px); z-index: 10; max-height: 220px; overflow: auto; background: var(--superficie); border: 1px solid var(--bordo); border-radius: 12px; box-shadow: 0 12px 30px var(--ombra); }
  .suggerimenti button { display: block; width: 100%; text-align: left; padding: 11px 14px; border: 0; background: transparent; font-size: 15px; cursor: pointer; border-bottom: 1px solid var(--bordo); }
  .suggerimenti button:last-child { border-bottom: 0; }
  .suggerimenti button:hover, .suggerimenti button:focus { background: var(--superficie-2); outline: none; }
  .mie-squadre { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
  .squadra-tag { display: inline-flex; align-items: center; gap: 6px; padding: 7px 8px 7px 12px; border-radius: 999px; background: color-mix(in srgb, #facc15 16%, var(--superficie)); border: 1px solid color-mix(in srgb, #facc15 55%, var(--bordo)); font-size: 14px; font-weight: 700; }
  .squadra-tag button { border: 0; background: var(--superficie-2); width: 20px; height: 20px; border-radius: 50%; cursor: pointer; font-size: 11px; line-height: 1; }
  .barra-salva.due { display: grid; grid-template-columns: 1fr 2fr; gap: 10px; }
  .barra-salva { position: sticky; bottom: 0; margin: 24px -16px 0; padding: 12px 16px calc(12px + env(safe-area-inset-bottom)); background: linear-gradient(transparent, var(--bg) 30%); }
  .account-riga { display: flex; align-items: center; gap: 10px; padding: 12px; border-radius: 14px; background: var(--superficie); border: 1px solid var(--bordo); }
  .account-riga .avatar { width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; background: var(--accento); color: #fff; font-weight: 800; }
  .account-riga .chi { flex: 1; min-width: 0; font-size: 14px; }
  .account-riga .chi small { display: block; color: var(--debole); font-size: 12px; }
  .account-riga button { border: 1px solid var(--bordo); background: transparent; border-radius: 10px; padding: 7px 10px; font-size: 13px; font-weight: 700; cursor: pointer; color: var(--tenue); }

  /* ---------- Stato live dentro la card ---------- */
  .live-riga { display: flex; align-items: center; gap: 7px; margin-top: 6px; flex-wrap: wrap; }
  .punteggio {
    font-size: 15px; font-weight: 800; font-variant-numeric: tabular-nums; letter-spacing: .01em;
    padding: 2px 8px; border-radius: 7px; color: #fff; background: var(--live);
  }
  .minuto { font-size: 12.5px; font-weight: 800; color: var(--live); font-variant-numeric: tabular-nums; }
  .minuto .tick { animation: pulsa 1.2s steps(2, jump-none) infinite; }
  .fase {
    font-size: 12px; font-weight: 800; letter-spacing: .04em; padding: 2px 7px; border-radius: 6px;
    color: var(--c); background: color-mix(in srgb, var(--c) 18%, transparent); border: 1px solid color-mix(in srgb, var(--c) 45%, transparent);
  }
  .conto { font-size: 13px; font-weight: 700; color: var(--tenue); font-variant-numeric: tabular-nums; white-space: nowrap; }
  .conto b { color: var(--testo); }
  .giri { display: flex; align-items: center; gap: 8px; width: 100%; }
  .giri .num { font-size: 13px; font-weight: 800; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .giri .num small { font-weight: 600; color: var(--tenue); font-size: 12px; }
  .barra-giri { flex: 1; min-width: 40px; height: 5px; border-radius: 3px; background: var(--superficie-2); overflow: hidden; }
  .barra-giri i { display: block; height: 100%; border-radius: 3px; background: var(--c); }
  .hero .live-riga { margin-top: 8px; }

  /* ---------- Eventi conclusi ---------- */
  .card.finito { opacity: .78; }
  .card.finito .icona { filter: grayscale(.5); }
  .risultato {
    display: inline-block; margin-top: 5px; padding: 2px 8px; border-radius: 7px; font-size: 13.5px; font-weight: 800;
    font-variant-numeric: tabular-nums; letter-spacing: .01em; background: var(--superficie-2); color: var(--testo);
  }
  .badge.fine { font-size: 9px; font-weight: 800; letter-spacing: .06em; padding: 2px 6px; border-radius: 5px; color: var(--tenue); background: var(--superficie-2); }

  /* ---------- Google ---------- */
  .btn.google { background: #fff; color: #1f1f1f; border-color: #dadce0; }

  /* ---------- Pannello calendario ---------- */
  .pannello .spiega { color: var(--tenue); font-size: 14px; margin: 0 0 6px; line-height: 1.45; }
  .riga-cal {
    display: flex; align-items: center; gap: 10px; padding: 8px 8px 8px 12px; margin-bottom: 6px;
    background: var(--superficie); border: 1px solid var(--bordo); border-radius: 13px;
  }
  .riga-cal .emoji { font-size: 20px; width: 26px; text-align: center; }
  .riga-cal .nome { flex: 1; min-width: 0; font-weight: 700; font-size: 14.5px; line-height: 1.25; }
  .riga-cal .nome small { display: block; font-weight: 500; font-size: 12px; color: var(--debole); }
  .btn-iscr {
    flex: none; padding: 7px 12px; border-radius: 10px; font-size: 13px; font-weight: 800; text-decoration: none;
    color: #fff; background: linear-gradient(135deg, var(--accento), var(--accento-2));
  }
  .nota-cal { font-size: 12.5px; color: var(--tenue); background: var(--superficie-2); border-radius: 12px; padding: 10px 12px; margin-top: 14px; line-height: 1.5; }

  /* ---------- Gruppi per competizione ---------- */
  .gruppo { background: var(--superficie); border: 1px solid var(--bordo); border-radius: 14px; margin-bottom: 10px; overflow: hidden; }
  .g-testa {
    display: flex; align-items: center; gap: 9px; width: 100%; padding: 9px 12px; border: 0; text-align: left;
    background: color-mix(in srgb, var(--c) 11%, var(--superficie)); border-bottom: 1px solid var(--bordo); color: var(--testo);
  }
  .g-testa.apribile { cursor: pointer; }
  .g-ico { flex: none; width: 26px; height: 26px; display: grid; place-items: center; font-size: 16px; border-radius: 8px;
    background: color-mix(in srgb, var(--c) 22%, transparent); }
  .g-testo { flex: 1; min-width: 0; }
  .g-nome { display: flex; align-items: baseline; gap: 6px; flex-wrap: wrap; line-height: 1.25; }
  .g-nome b { font-size: 14px; font-weight: 800; letter-spacing: -0.01em; }
  .g-nome span { font-size: 12.5px; color: var(--tenue); font-weight: 600; }
  .g-canale { font-size: 11.5px; color: var(--tenue); line-height: 1.3; }
  .g-canale .free, .r-extra .free { color: var(--gratis); font-weight: 800; }
  .g-live { flex: none; font-size: 10px; font-weight: 800; letter-spacing: .05em; color: #fff; background: var(--live); padding: 2px 6px; border-radius: 5px; }
  .g-conta { flex: none; font-size: 12.5px; font-weight: 800; color: var(--tenue); display: flex; align-items: center; gap: 6px; }
  .g-conta .freccia { font-size: 13px; }
  .g-mostra { display: block; width: 100%; border: 0; border-top: 1px solid var(--bordo); background: transparent; padding: 9px 12px;
    font-size: 12.5px; font-weight: 700; color: var(--tenue); text-align: left; cursor: pointer; }
  .riga-ev {
    display: grid; grid-template-columns: 44px minmax(0, 1fr) auto 28px; align-items: center; gap: 8px; cursor: pointer;
    padding: 8px 10px 8px 12px; border-top: 1px solid var(--bordo);
  }
  .g-testa + .riga-ev { border-top: 0; }
  .riga-ev.cuore { background: color-mix(in srgb, #facc15 8%, transparent); }
  .riga-ev.live { background: color-mix(in srgb, var(--live) 7%, transparent); }
  .r-tempo { font-size: 13px; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--tenue); }
  .t-live { color: var(--live); font-weight: 800; }
  .t-fine { font-size: 11px; font-weight: 800; letter-spacing: .04em; color: var(--debole); }
  .t-data, .t-ora { display: block; line-height: 1.25; }
  .t-data { font-weight: 800; color: var(--testo); }
  .con-data { grid-template-columns: 48px minmax(0, 1fr) auto 28px; }
  .riga-ev:hover { background: color-mix(in srgb, var(--testo) 4%, transparent); }
  .riga-ev:focus-visible { outline: 2px solid var(--accento); outline-offset: -2px; }
  .r-tv { display: flex; flex-direction: column; align-items: flex-end; text-align: right; max-width: 38vw;
    font-size: 12px; line-height: 1.35; color: var(--tenue); }
  .r-tv span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
  .r-tv span.free { color: var(--gratis); font-weight: 700; }
  .r-tv span.free small { font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; }
  .r-punti:empty { min-width: 0; }
  .hero .meta.tv { font-size: 12.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .squadra { display: block; max-width: 100%; border: 0; background: none; padding: 0; margin: 0; text-align: left; cursor: pointer;
    font-size: 14.5px; line-height: 1.4; color: var(--testo); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  .squadra.vince { font-weight: 800; }
  .squadra.perde { color: var(--tenue); }
  .r-nome { font-size: 14.5px; font-weight: 600; }
  .r-extra { font-size: 11.5px; color: var(--tenue); margin-top: 1px; line-height: 1.35; }
  .r-extra b { color: var(--testo); font-variant-numeric: tabular-nums; }
  .r-punti { display: grid; text-align: right; font-size: 14.5px; font-weight: 800; line-height: 1.4; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .r-punti.live { color: var(--live); }
  .riga-ev .avvisami { width: 28px; height: 28px; font-size: 13px; border-radius: 8px; }
  .barra-giri.mini { display: inline-block; width: 48px; height: 4px; vertical-align: middle; }
  .sep { color: var(--debole); }
  .quadro.live-q { width: auto; gap: 6px; padding: 0 10px; display: inline-flex; font-size: 12px; font-weight: 800; color: var(--live); border-color: color-mix(in srgb, var(--live) 50%, var(--bordo)); }
  .quadro.live-q.on { --c: var(--live); color: #fff; background: var(--live); }
  .quadro.live-q .n { position: static; border: 0; }
  .quadro.live-q.on .pallino-live { background: #fff; }
  .giorno-btn.passato .gn { color: var(--tenue); }
  .giorno-btn.passato.on .gn { color: #fff; }
  #titolo-giorno { margin: 14px 2px 10px; align-items: center; }
  .mini-comp { font-size: 11px; font-weight: 700; color: var(--debole); padding: 7px 12px 0; letter-spacing: .02em; }
  .lista-squadra .mini-comp + .riga-ev { border-top: 0; padding-top: 3px; }
  .lista-squadra .riga-ev + .mini-comp { border-top: 1px solid var(--bordo); }
  .sq-testa { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 6px; }
  .sq-testa h3 { margin: 0; }
  .btn-segui { border: 1px solid var(--bordo); background: var(--superficie); border-radius: 999px; padding: 7px 13px; font-size: 13.5px; font-weight: 800; cursor: pointer; }
  .btn-segui.on { border-color: #eab308; background: color-mix(in srgb, #facc15 16%, var(--superficie)); }

  /* ---------- Bandiere e loghi ---------- */
  .squadra { display: flex; align-items: center; gap: 7px; }
  .sq-nome { overflow: hidden; text-overflow: ellipsis; }
  .band { flex: none; font-size: 16px; line-height: 1; }
  .logo { flex: none; width: 18px; height: 18px; display: inline-grid; place-items: center; border-radius: 50%; overflow: hidden; }
  .logo img { width: 100%; height: 100%; object-fit: contain; }
  .logo.ini { background: color-mix(in srgb, var(--c, var(--accento)) 24%, var(--superficie-2)); font-size: 10px; font-weight: 800; color: var(--testo); }
  .podio b { color: var(--testo); }
  .p-squadra { display: flex; flex-direction: column; align-items: center; gap: 6px; text-align: center !important; }
  .p-squadra .band { font-size: 30px; }
  .p-squadra .logo { width: 34px; height: 34px; font-size: 15px; }
  /* Classifica F1 / MotoGP */
  .classifica { border: 1px solid var(--bordo); border-radius: 14px; overflow: hidden; background: var(--superficie); }
  .cl-riga { display: grid; grid-template-columns: 30px 24px minmax(0, 1fr) auto; align-items: center; gap: 8px; padding: 7px 12px; border-top: 1px solid var(--bordo); }
  .cl-testa { border-top: 0; font-size: 10.5px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; color: var(--debole); background: var(--superficie-2); }
  .cl-pos { font-weight: 800; font-variant-numeric: tabular-nums; color: var(--tenue); text-align: center; }
  .podio-1 .cl-pos { color: #eab308; } .podio-2 .cl-pos { color: #94a3b8; } .podio-3 .cl-pos { color: #d97706; }
  .cl-pil { min-width: 0; }
  .cl-pil b { display: block; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .cl-pil small { display: block; font-size: 11.5px; color: var(--tenue); }
  .cl-tempo { text-align: right; font-variant-numeric: tabular-nums; }
  .cl-tempo b { display: block; font-size: 13.5px; }
  .cl-tempo small { display: block; font-size: 12px; color: var(--tenue); font-weight: 700; }

  /* ---------- Scheda partita ---------- */
  .p-testa { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
  .p-testa b { display: block; font-size: 15px; }
  .p-testa small { display: block; font-size: 12.5px; color: var(--tenue); margin-top: 1px; }
  .p-tabellone { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 10px;
    padding: 16px 10px; border-radius: 16px; background: var(--superficie); border: 1px solid var(--bordo); }
  .p-squadra { border: 0; background: none; font-size: 17px; font-weight: 800; color: var(--testo); cursor: pointer; line-height: 1.25; }
  .p-squadra:first-child { text-align: right; }
  .p-squadra:last-child { text-align: left; }
  .p-squadra:hover { text-decoration: underline; text-underline-offset: 3px; }
  .p-centro { display: flex; flex-direction: column; align-items: center; gap: 4px; min-width: 88px; }
  .p-ris { font-size: 38px; font-weight: 800; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; line-height: 1; display: flex; gap: 8px; }
  .p-ris span { color: var(--debole); font-weight: 600; }
  .p-ris.live { color: var(--live); }
  .p-ris.vs { font-size: 26px; color: var(--tenue); }
  .p-set { display: flex; gap: 6px; }
  .p-set span { display: flex; flex-direction: column; font-size: 20px; font-variant-numeric: tabular-nums; background: var(--superficie-2); border-radius: 8px; padding: 4px 8px; text-align: center; }
  .p-stato { font-size: 13px; font-weight: 800; color: var(--tenue); }
  .p-stato.live { color: var(--live); }
  .p-gol { display: grid; gap: 4px; }
  .gol { display: flex; align-items: center; gap: 8px; padding: 7px 10px; border-radius: 10px; background: var(--superficie); font-size: 14px; }
  .gol.lato-1 { flex-direction: row-reverse; text-align: right; }
  .g-min { font-weight: 800; color: var(--tenue); font-variant-numeric: tabular-nums; min-width: 34px; }
  .gol.lato-1 .g-min { text-align: right; }
  .g-chi small { color: var(--tenue); }
  .p-nota { color: var(--tenue); font-size: 13.5px; margin: 10px 2px 0; }
  .p-dove { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 8px; margin: 10px 2px 0; font-size: 14px; font-weight: 700; }
  .p-dove-tit { color: var(--tenue); font-weight: 600; font-size: 13px; }
  .p-dove .free { color: var(--gratis); }
  .p-dove small { font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; }
  .p-schede { display: flex; gap: 6px; overflow-x: auto; scrollbar-width: none; margin: 14px 0 8px; }
  .p-scheda { flex: none; border: 0; border-radius: 9px; padding: 8px 12px; font-size: 12.5px; font-weight: 800; letter-spacing: .03em;
    text-transform: uppercase; background: var(--superficie-2); color: var(--tenue); cursor: pointer; }
  .p-scheda.on { background: var(--accento); color: #fff; }
  .p-contenuto { min-height: 120px; }
  .tempo-testa { display: flex; justify-content: space-between; padding: 8px 12px; margin: 6px 0 4px; border-radius: 9px;
    background: var(--superficie-2); font-size: 12px; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; color: var(--tenue); }
  .tempo-testa b { color: var(--testo); }
  .ev { display: flex; align-items: center; gap: 9px; padding: 7px 4px; font-size: 14px; }
  .ev.lato-1 { flex-direction: row-reverse; text-align: right; }
  .ev-min { flex: none; width: 42px; font-weight: 800; color: var(--tenue); font-variant-numeric: tabular-nums; font-size: 13px; }
  .ev.lato-1 .ev-min { text-align: right; }
  .ev-altro { color: var(--tenue); font-weight: 500; }
  .ev-vuoto { text-align: center; color: var(--debole); padding: 6px; }
  .ico-ev { flex: none; width: 28px; height: 28px; display: grid; place-items: center; border-radius: 8px; background: var(--superficie); font-size: 14px; }
  .ico-ev.aut { filter: hue-rotate(140deg) saturate(3); }
  .ico-ev.sbagliato { color: var(--live); font-weight: 900; font-size: 15px; }
  .ico-ev.cart::after { content: ""; width: 10px; height: 14px; border-radius: 2px; background: #facc15; }
  .ico-ev.cart.rosso::after { background: #ef4444; }
  .stat { margin: 4px 0 12px; }
  .stat-num { display: flex; justify-content: space-between; align-items: baseline; font-size: 13px; margin-bottom: 5px; }
  .stat-num span { color: var(--tenue); font-weight: 600; }
  .stat-num b { font-size: 14.5px; font-variant-numeric: tabular-nums; min-width: 40px; }
  .stat-num b:last-child { text-align: right; }
  .stat-num b.piu { color: var(--accento); }
  .stat-barre { display: flex; gap: 4px; height: 6px; }
  .stat-barre i { display: block; height: 100%; border-radius: 3px; background: var(--superficie-2); }
  .stat-barre i.sx { margin-left: auto; background: color-mix(in srgb, var(--accento) 75%, transparent); }
  .stat-barre i.dx { background: color-mix(in srgb, var(--testo) 45%, transparent); }
  .form { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .form-nome { font-weight: 800; font-size: 14px; margin-bottom: 6px; }
  .form-nome span { color: var(--tenue); font-weight: 600; }
  .gioc { display: flex; align-items: center; gap: 6px; font-size: 13px; padding: 4px 0; border-bottom: 1px solid var(--bordo); }
  .gioc .num { width: 22px; font-weight: 800; color: var(--tenue); font-variant-numeric: tabular-nums; }
  .gioc .ruolo { margin-left: auto; font-size: 10.5px; color: var(--debole); }
  .gioc.panca { color: var(--tenue); }
  .gioc.entrato::after { content: "↑"; margin-left: auto; color: #22c55e; font-weight: 900; }
  .form-sub { font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: .06em; color: var(--debole); margin: 10px 0 2px; }
  .p-tvs { display: grid; gap: 6px; }
  .p-tv { display: flex; align-items: center; justify-content: space-between; padding: 11px 13px; border-radius: 12px;
    background: var(--superficie); border: 1px solid var(--bordo); font-size: 15px; font-weight: 700; }
  .p-tv.free { border-color: color-mix(in srgb, var(--gratis) 55%, var(--bordo)); }
  .p-tv b { font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: var(--gratis); }
  .p-avvisa { margin-top: 14px; }
  .p-motori { padding: 16px; border-radius: 16px; background: var(--superficie); border: 1px solid var(--bordo); text-align: center; }
  .p-sessione { font-size: 20px; font-weight: 800; margin-bottom: 6px; }
  .p-grande { font-size: 30px; font-weight: 800; font-variant-numeric: tabular-nums; }
  .p-grande.live { color: var(--live); }
  .p-grande small { font-size: 17px; color: var(--tenue); }
  .p-motori .barra-giri { height: 6px; margin: 8px auto 0; max-width: 220px; }

  /* ---------- Frecce della striscia dei giorni ---------- */
  .giorni-nav { display: flex; align-items: center; gap: 6px; margin-top: 2px; }
  .giorni-nav .striscia { flex: 1; min-width: 0; margin: 0; padding: 4px 0 2px; overflow: hidden; gap: 4px; }
  .giorni-nav .giorno-btn { flex: 1 1 0; width: auto; min-width: 0; }
  .giorni-nav .giorno-btn .gs { font-size: 8.5px; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .freccia-g { flex: none; width: 26px; height: 54px; border-radius: 11px; border: 1px solid var(--bordo); background: var(--superficie);
    font-size: 18px; font-weight: 800; color: var(--tenue); cursor: pointer; }
  .freccia-g:active { transform: scale(.94); }
  .torna-oggi { margin-left: auto; border: 1px solid var(--bordo); background: var(--superficie); border-radius: 999px;
    padding: 5px 11px; font-size: 12.5px; font-weight: 800; color: var(--accento); cursor: pointer; }

  /* ---------- Pannello filtri ---------- */
  .velo { position: fixed; inset: 0; z-index: 20; background: rgb(0 0 0 / .5); backdrop-filter: blur(2px); }
  .pannello {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 21; max-height: 82dvh; overflow: auto; max-width: 720px; margin: 0 auto;
    background: var(--bg); border-radius: 24px 24px 0 0; border: 1px solid var(--bordo); border-bottom: 0;
    padding: 10px 16px calc(16px + env(safe-area-inset-bottom)); box-shadow: 0 -12px 40px var(--ombra);
  }
  .pannello .maniglia { width: 40px; height: 5px; border-radius: 3px; background: var(--bordo); margin: 0 auto 12px; }
  .pannello h3 { margin: 0 0 12px; font-size: 20px; font-weight: 800; }
  .pannello h4 { margin: 18px 0 9px; font-size: 12px; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; color: var(--debole); }
  .interruttore { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 13px 14px; border-radius: 14px; background: var(--superficie); border: 1px solid var(--bordo); font-weight: 700; font-size: 14.5px; cursor: pointer; }
  .interruttore .sw { width: 46px; height: 28px; border-radius: 999px; background: var(--superficie-2); position: relative; flex: none; transition: background .15s; }
  .interruttore .sw::after { content: ""; position: absolute; top: 3px; left: 3px; width: 22px; height: 22px; border-radius: 50%; background: #fff; transition: transform .15s; box-shadow: 0 1px 3px rgb(0 0 0 / .3); }
  .interruttore.on .sw { background: #eab308; }
  .interruttore.on .sw::after { transform: translateX(18px); }
  .pannello .azioni-pannello { display: grid; grid-template-columns: 1fr 2fr; gap: 10px; margin-top: 22px; }

  @media (max-width: 370px) {
    .card { grid-template-columns: 32px minmax(0, 1.1fr) minmax(0, 1fr) auto; gap: 8px; padding: 10px; }
    .card .icona { width: 32px; height: 32px; font-size: 19px; }
    .card h3 { font-size: 14px; }
    .card .dove { padding-left: 8px; }
    .logo { font-size: 22px; }
    .sezioni button { font-size: 13.5px; gap: 6px; }
  }
  @media (prefers-reduced-motion: reduce) { .badge.live { animation: none; } .sezioni .cursore { transition: none; } }
</style>
</head>
<body>
<div class="app">

  <!-- 1. ACCESSO -->
  <section class="schermo accesso" id="s-accesso" hidden>
    <div class="rapidi angolo" data-rapidi></div>
    <div class="marchio emoji">📺</div>
    <h1>Sport in <span>TV</span></h1>
    <p class="slogan" data-t="slogan"></p>
    <form class="bottoni" id="form-accesso" autocomplete="on">
      <button type="button" class="btn google" id="google">
        <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>
        <span data-t="google"></span>
      </button>
      <div class="separatore" data-t="oppureUtente"></div>
      <div class="tabs-accesso">
        <button type="button" data-modo="accedi" class="on" data-t="accedi"></button>
        <button type="button" data-modo="crea" data-t="crea"></button>
      </div>
      <label class="etichetta-campo" for="utente" data-t="utente"></label>
      <input class="campo" id="utente" autocomplete="username" autocapitalize="none" spellcheck="false" data-tp="esUtente" required>
      <label class="etichetta-campo" for="password">Password</label>
      <input class="campo" id="password" type="password" autocomplete="current-password" data-tp="minPw" minlength="4" required>
      <p class="errore" id="errore-accesso"></p>
      <button class="btn primario" type="submit" id="invia-accesso"></button>
      <div class="separatore" data-t="oppure"></div>
      <button class="btn testo" type="button" id="ospite" data-t="ospite"></button>
    </form>
    <p class="nota" id="nota-accesso"></p>
  </section>

  <!-- 2. PREFERENZE -->
  <section class="preferenze" id="s-pref" hidden>
    <div class="testata-pref">
      <div style="display:flex;align-items:center;gap:10px">
        <button class="btn-icona" id="indietro" hidden aria-label="Indietro"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg></button>
        <div class="passo" id="pref-passo"></div>
      </div>
      <div class="rapidi" data-rapidi></div>
    </div>
    <h2 id="pref-titolo"></h2>
    <p class="sottotitolo" data-t="prefSotto"></p>
    <div id="pref-account"></div>
    <h4 data-t="sport"></h4>
    <div class="griglia-sport" id="griglia-sport"></div>
    <div id="leghe-scelte"></div>
    <h4 data-t="cuore"></h4>
    <div class="cerca-squadra">
      <input class="campo" id="cerca" type="search" data-tp="esCerca" autocomplete="off" enterkeyhint="done">
      <div class="suggerimenti" id="suggerimenti" hidden></div>
    </div>
    <div class="mie-squadre" id="mie-squadre"></div>
    <p class="sottotitolo" style="margin-top:10px;font-size:13px" data-t="cuoreNota"></p>
    <div class="barra-salva" id="barra-salva"><button class="btn" id="annulla" hidden></button><button class="btn primario" id="salva"></button></div>
  </section>

  <!-- 3. HOME -->
  <section id="s-home" hidden>
    <header class="testata">
      <div style="min-width:0">
        <h1 class="logo">Sport in <span>TV</span></h1>
        <p class="aggiornato" id="aggiornato"></p>
      </div>
      <div class="rapidi">
        <div data-rapidi class="rapidi"></div>
        <button class="btn-icona emoji" id="apri-cal" data-ta="iscriviti">📅</button>
        <button class="btn-icona emoji" id="apri-impostazioni" data-ta="impostazioni">⚙️</button>
      </div>
    </header>

    <nav class="sezioni">
      <div class="interno" data-attiva="oggi">
        <span class="cursore" aria-hidden="true"></span>
        <button data-sezione="oggi" class="on"><span class="emoji">📺</span><span data-t="oggiTv"></span><span class="quanti" id="n-oggi"></span></button>
        <button data-sezione="miei"><span class="emoji">⭐</span><span data-t="miei"></span><span class="quanti" id="n-miei"></span></button>
      </div>
    </nav>

    <div id="v-oggi">
      <section class="hero" id="hero" hidden></section>
      <div class="quadri" id="sport-oggi"></div>
      <main id="lista-oggi"></main>
    </div>

    <div id="v-miei" hidden>
      <div class="giorni-nav">
        <button class="freccia-g" id="sett-prec" data-ta="settPrec">‹</button>
        <div class="striscia" id="striscia"></div>
        <button class="freccia-g" id="sett-succ" data-ta="settSucc">›</button>
      </div>
      <div class="quadri" id="sport-miei"></div>
      <div class="riassunto" id="riassunto" hidden></div>
      <div class="giorno-tit" id="titolo-giorno"></div>
      <main id="lista-miei"></main>
    </div>

    <footer id="piede"></footer>
  </section>

  <div class="velo" id="velo" hidden></div>
  <section class="pannello" id="pannello-cal" hidden>
    <div class="maniglia"></div>
    <h3 data-t="calTitolo"></h3>
    <p class="spiega" id="cal-spiega"></p>
    <div id="cal-righe"></div>
    <p class="nota-cal" id="cal-nota"></p>
    <div class="azioni-pannello" style="grid-template-columns:1fr"><button class="btn" id="chiudi-cal" data-t="chiudi"></button></div>
  </section>
  <section class="pannello" id="pannello-partita" hidden>
    <div class="maniglia"></div>
    <div class="p-testa" id="p-testa"></div>
    <div id="p-corpo"></div>
    <div class="azioni-pannello" style="grid-template-columns:1fr"><button class="btn" id="chiudi-partita" data-t="chiudi"></button></div>
  </section>
  <section class="pannello" id="pannello-squadra" hidden>
    <div class="maniglia"></div>
    <div class="sq-testa"><h3 id="sq-nome"></h3><button class="btn-segui" id="sq-segui"></button></div>
    <div id="sq-lista"></div>
    <div class="azioni-pannello" style="grid-template-columns:1fr"><button class="btn" id="chiudi-squadra" data-t="chiudi"></button></div>
  </section>
  <section class="pannello" id="pannello" hidden>
    <div class="maniglia"></div>
    <h3 data-t="filtri"></h3>
    <div class="interruttore" id="solo-cuore"><span data-t="soloCuore"></span><span class="sw"></span></div>
    <h4 data-t="sport"></h4>
    <div class="scelte" id="f-sport"></div>
    <h4 data-t="competizioni"></h4>
    <div class="scelte" id="f-leghe"></div>
    <div class="azioni-pannello">
      <button class="btn" id="azzera" data-t="azzera"></button>
      <button class="btn primario" id="applica"></button>
    </div>
  </section>
</div>

<script>
const AGGIORNATO = new Date("{{AGGIORNATO_ISO}}");
const DEMO = {{DEMO}};
// Nelle anteprime con eventi inventati gli orari seguono il momento in cui apri la pagina
const SPOSTA = DEMO ? Date.now() - AGGIORNATO.getTime() : 0;
const sposta = iso => new Date(new Date(iso).getTime() + SPOSTA);
const EVENTI = {{DATI}}.map(e => ({
  ...e, inizio: sposta(e.inizio), fine: sposta(e.fine),
  live: e.live && { ...e.live, fineFase: e.live.fineFase && sposta(e.live.fineFase) },
}));
const SPORT = {{SPORT}};
const SQUADRE_NOTE = {{SQUADRE}};
const PAROLE_EN = {{EN}};
const ORDINE = Object.keys(SPORT);
const ANTEPRIMA = DEMO;            // anteprima con eventi inventati
const LOGIN_ONLINE = false;        // diventa true quando colleghiamo Firebase (login Google e sincronizzazione)

/* ================= Lingua ================= */
const TESTI = {
  it: {
    slogan: "Cosa c'è oggi in TV e i tuoi eventi della settimana, con dove vederli.",
    accedi: "Accedi", crea: "Crea account", creaEntra: "Crea account ed entra", utente: "Nome utente",
    esUtente: "es. gaetano", minPw: "almeno 4 caratteri", oppure: "oppure", ospite: "Entra senza account",
    notaLocale: "Per ora account e preferenze restano salvati su questo dispositivo e browser.",
    nota: "Con un account ritrovi le tue preferenze su PC e iPhone. Senza account restano solo su questo dispositivo.",
    notaAnteprima: "<b>Anteprima:</b> gli account funzionano ma restano in questo browser. Alla pubblicazione li colleghiamo a Firebase per usarli su più dispositivi.",
    errNome: "Nome utente: 3-20 caratteri, solo lettere, numeri, . _ -", errPw: "La password deve avere almeno 4 caratteri.",
    errEsiste: "Questo nome utente esiste già: scegline un altro o accedi.", errNonTrovato: "Nome utente non trovato. Vuoi creare un account?",
    errPwSbagliata: "Password sbagliata.",
    passo: "Passo 2 di 2", impostazioni: "Impostazioni", prefTitolo: "Cosa ti interessa?", prefTitolo2: "I tuoi preferiti",
    prefSotto: "Scegli sport e competizioni per la sezione \"I miei eventi\".", sport: "Sport",
    cuore: "Squadre e giocatori del cuore", esCerca: "Es. Palermo, Sinner…",
    cuoreNota: "Le loro partite compaiono sempre, anche nelle competizioni che non hai scelto, e sono segnate con ⭐.",
    mostrami: "Mostrami i miei eventi", salva: "Salva", quali: "quali competizioni?", aggiungi: "Aggiungi",
    senzaAccount: "Senza account · salvato su questo dispositivo", conAccount: "Account · preferenze sincronizzate", esci: "Esci",
    aggiornato: "Aggiornato", iscriviti: "Iscriviti al calendario", oggiTv: "Oggi in TV", miei: "I miei eventi",
    prossimo: "Il prossimo", inOnda: "🔴 In onda ora", oggi: "Oggi", domani: "Domani", tutti: "Tutti", dove: "Dove vederlo",
    notte: "Notte", mattina: "Mattina", pomeriggio: "Pomeriggio", sera: "Sera", gratis: "gratis", avvisami: "Avvisami",
    vuotoOggi: "Per oggi non c'è più niente in programma.<br>Dai un'occhiata a \"I miei eventi\" per i prossimi giorni.",
    vuotoMiei: "Nessun evento con questi filtri.", mostraTutto: "Mostra tutto",
    filtri: "Filtri", soloCuore: "⭐ Solo squadre e giocatori del cuore", competizioni: "Competizioni", nessuna: "Nessuna",
    azzera: "Azzera", mostra: n => `Mostra ${n} ${n === 1 ? "evento" : "eventi"}`, soloDelCuore: "⭐ solo del cuore",
    piede: m => `📅 in alto: tutti gli eventi nel calendario del telefono, con avviso ${m} minuti prima.<br>🔔 aggiunge solo quell'evento · ⚙️ cambia i tuoi preferiti.`,
    tema: "Cambia tema", nomeOspite: "Ospite", locale: "it-IT",
    annulla: "Annulla", indietro: "Indietro",
    google: "Continua con Google", oppureUtente: "oppure con nome utente", accountGoogle: "Account Google",
    griglia: "Griglia di partenza", classifica: "Classifica", pos: "Pos", pilota: "Pilota", tempoMigliore: "Tempo",
    tempo: "Tempo / distacco", classificaNd: "Classifica non disponibile per questa sessione.",
    gol: "Gol", golNonDisponibili: "Marcatori non ancora disponibili.", riassunto: "Riassunto", statistiche: "Statistiche",
    formazioni: "Formazioni", tempo1: "1° tempo", tempo2: "2° tempo", tempo3: "Supplementari", tempo4: "Rigori",
    rig: "rigore", aut: "autogol", rigSbagliato: "rigore sbagliato", panchina: "Panchina",
    cronacaVuota: "Cronaca non ancora disponibile.", cronacaDopo: "La cronaca comparirà quando inizia la partita.",
    statsVuote: "Statistiche non ancora disponibili.", formVuote: "Formazioni non ancora disponibili: di solito escono un'ora prima.", settPrec: "Settimana precedente", settSucc: "Settimana successiva",
    fin: "FIN", mostraPartite: n => `Mostra ${n} partite`, vuotoLive: "Nessun evento in onda in questo momento.",
    vuotoGiorno: "Nessun evento dei tuoi preferiti in questo giorno.", segui: "Segui", seguita: "Seguita",
    prossime: "Prossime partite", risultati: "Risultati", nessunaPartita: "Nessuna partita in archivio.",
    inOndaSez: "In onda ora", finale: "FINALE", giro: "Giro", finisceTra: "finisce tra", inChiusura: "in chiusura", finiti: "Già finiti", terminato: "Terminato",
    calTitolo: "📅 Il tuo calendario", chiudi: "Chiudi", iscr: "Iscriviti",
    calSpiega: m => `Aggiungi al calendario del telefono solo quello che segui. Gli eventi si aggiornano da soli e ti avvisano ${m} minuti prima.`,
    calCuore: "Squadre e giocatori del cuore", calLeghe: "Le tue competizioni", calTutto: "Tutto",
    calTuttoNome: "Tutti gli eventi", calTuttoSub: "ogni sport, anche quelli che non segui", calSub: "calendario separato",
    calNota: "Su iPhone, dopo l'iscrizione: Impostazioni → Calendario → Account → calendario scelto → disattiva “Rimuovi avvisi”, altrimenti iOS toglie i promemoria.",
    calAnteprima: "<b>Anteprima:</b> i pulsanti non funzionano ancora, i calendari esistono solo nella versione pubblicata.",
  },
  en: {
    slogan: "What's on TV today and your events of the week, with where to watch them.",
    accedi: "Log in", crea: "Sign up", creaEntra: "Create account", utente: "Username",
    esUtente: "e.g. gaetano", minPw: "at least 4 characters", oppure: "or", ospite: "Continue without an account",
    notaLocale: "For now accounts and preferences are saved on this device and browser only.",
    nota: "With an account you get your preferences on PC and iPhone. Without one they stay on this device only.",
    notaAnteprima: "<b>Preview:</b> accounts work but stay in this browser. When we publish, we connect them to Firebase to use them on multiple devices.",
    errNome: "Username: 3-20 characters, only letters, numbers, . _ -", errPw: "Password must be at least 4 characters.",
    errEsiste: "This username already exists: pick another or log in.", errNonTrovato: "Username not found. Want to create an account?",
    errPwSbagliata: "Wrong password.",
    passo: "Step 2 of 2", impostazioni: "Settings", prefTitolo: "What are you into?", prefTitolo2: "Your favourites",
    prefSotto: "Choose sports and competitions for \"My events\".", sport: "Sports",
    cuore: "Favourite teams and players", esCerca: "E.g. Palermo, Sinner…",
    cuoreNota: "Their matches always show up, even in competitions you didn't pick, and are marked with ⭐.",
    mostrami: "Show my events", salva: "Save", quali: "which competitions?", aggiungi: "Add",
    senzaAccount: "No account · saved on this device", conAccount: "Account · preferences synced", esci: "Log out",
    aggiornato: "Updated", iscriviti: "Subscribe to calendar", oggiTv: "On TV today", miei: "My events",
    prossimo: "Up next", inOnda: "🔴 Live now", oggi: "Today", domani: "Tomorrow", tutti: "All", dove: "Watch on",
    notte: "Night", mattina: "Morning", pomeriggio: "Afternoon", sera: "Evening", gratis: "free", avvisami: "Remind me",
    vuotoOggi: "Nothing else on today.<br>Check \"My events\" for the next days.",
    vuotoMiei: "No events with these filters.", mostraTutto: "Show all",
    filtri: "Filters", soloCuore: "⭐ Only favourite teams and players", competizioni: "Competitions", nessuna: "None",
    azzera: "Reset", mostra: n => `Show ${n} ${n === 1 ? "event" : "events"}`, soloDelCuore: "⭐ favourites only",
    piede: m => `📅 at the top: all events in your phone calendar, with a reminder ${m} minutes before.<br>🔔 adds just that event · ⚙️ changes your favourites.`,
    tema: "Change theme", nomeOspite: "Guest", locale: "en-GB",
    annulla: "Cancel", indietro: "Back",
    google: "Continue with Google", oppureUtente: "or with a username", accountGoogle: "Google account",
    griglia: "Starting grid", classifica: "Classification", pos: "Pos", pilota: "Driver", tempoMigliore: "Time",
    tempo: "Time / gap", classificaNd: "No classification available for this session.",
    gol: "Goals", golNonDisponibili: "Scorers not available yet.", riassunto: "Summary", statistiche: "Stats",
    formazioni: "Line-ups", tempo1: "1st half", tempo2: "2nd half", tempo3: "Extra time", tempo4: "Penalties",
    rig: "penalty", aut: "own goal", rigSbagliato: "missed penalty", panchina: "Bench",
    cronacaVuota: "Match events not available yet.", cronacaDopo: "Match events will appear once the game starts.",
    statsVuote: "Stats not available yet.", formVuote: "Line-ups not available yet: usually out an hour before kick-off.", settPrec: "Previous week", settSucc: "Next week",
    fin: "FT", mostraPartite: n => `Show ${n} matches`, vuotoLive: "Nothing live right now.",
    vuotoGiorno: "None of your favourites on this day.", segui: "Follow", seguita: "Following",
    prossime: "Upcoming", risultati: "Results", nessunaPartita: "No matches in the archive.",
    inOndaSez: "Live now", finale: "FINAL", giro: "Lap", finisceTra: "ends in", inChiusura: "ending", finiti: "Already over", terminato: "Finished",
    calTitolo: "📅 Your calendar", chiudi: "Close", iscr: "Subscribe",
    calSpiega: m => `Add only what you follow to your phone calendar. Events update by themselves and remind you ${m} minutes before.`,
    calCuore: "Favourite teams and players", calLeghe: "Your competitions", calTutto: "Everything",
    calTuttoNome: "All events", calTuttoSub: "every sport, even ones you don't follow", calSub: "separate calendar",
    calNota: "On iPhone, after subscribing: Settings → Calendar → Accounts → the calendar → turn off “Remove Alerts”, otherwise iOS drops the reminders.",
    calAnteprima: "<b>Preview:</b> the buttons don't work yet, the calendars only exist in the published version.",
  },
};
const NOMI_SPORT_EN = { calcio: "Football", f1: "F1", motogp: "MotoGP", sbk: "Superbike", tennis: "Tennis", basket: "Basketball", volley: "Volleyball" };

function leggiAspetto() { try { return JSON.parse(localStorage.getItem("sport-in-tv:aspetto")) || {}; } catch { return {}; } }
let aspetto = leggiAspetto();
let lingua = aspetto.lingua || "it";
function salvaAspetto() { try { localStorage.setItem("sport-in-tv:aspetto", JSON.stringify(aspetto)); } catch {} }
const T = (k, ...a) => { const v = TESTI[lingua][k] ?? TESTI.it[k]; return typeof v === "function" ? v(...a) : v; };
const nomeSport = k => lingua === "en" ? NOMI_SPORT_EN[k] : SPORT[k].nome;

// Traduce i testi degli eventi (nomi GP, fasi, squadre nazionali, canali) parola per parola
const PAROLE_ORDINATE = Object.entries(PAROLE_EN).sort((a, b) => b[0].length - a[0].length);
const regexEsc = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const RE_EN = PAROLE_ORDINATE.length ? new RegExp("(?<![\\p{L}])(" + PAROLE_ORDINATE.map(([k]) => regexEsc(k)).join("|") + ")(?![\\p{L}])", "gu") : null;
function tr(s) {
  if (lingua !== "en" || !RE_EN) return s;
  return s.replace(RE_EN, m => PAROLE_EN[m]).replace(/^GP (.+)$/, "$1 GP").replace(/^Round di (.+)$/, "$1 Round");
}

/* ================= Tema ================= */
function temaAttuale() { return document.documentElement.dataset.tema || (matchMedia("(prefers-color-scheme: light)").matches ? "chiaro" : "scuro"); }
function cambiaTema() {
  const nuovo = temaAttuale() === "scuro" ? "chiaro" : "scuro";
  document.documentElement.dataset.tema = nuovo;
  aspetto.tema = nuovo; salvaAspetto(); disegnaRapidi();
}
function cambiaLingua(l) {
  lingua = l; aspetto.lingua = l; salvaAspetto();
  document.documentElement.lang = l;
  applicaTesti(); ridisegnaSchermo();
}
function disegnaRapidi() {
  const icona = temaAttuale() === "scuro" ? "☀️" : "🌙";
  document.querySelectorAll("[data-rapidi]").forEach(el => el.innerHTML = `
    <div class="lingua" role="group" aria-label="Lingua / Language">
      <button data-lingua="it" class="${lingua === "it" ? "on" : ""}">IT</button>
      <button data-lingua="en" class="${lingua === "en" ? "on" : ""}">EN</button>
    </div>
    <button class="btn-icona emoji" data-cambia-tema title="${esc(T("tema"))}" aria-label="${esc(T("tema"))}">${icona}</button>`);
}
document.addEventListener("click", ev => {
  const l = ev.target.closest("[data-lingua]"); if (l) return cambiaLingua(l.dataset.lingua);
  if (ev.target.closest("[data-cambia-tema]")) cambiaTema();
});

function applicaTesti() {
  document.querySelectorAll("[data-t]").forEach(el => el.innerHTML = T(el.dataset.t));
  document.querySelectorAll("[data-tp]").forEach(el => el.placeholder = T(el.dataset.tp));
  document.querySelectorAll("[data-ta]").forEach(el => { el.title = T(el.dataset.ta); el.setAttribute("aria-label", T(el.dataset.ta)); });
  document.getElementById("invia-accesso").textContent = modo === "accedi" ? T("accedi") : T("creaEntra");
  document.getElementById("nota-accesso").innerHTML = ANTEPRIMA ? T("nota") + "<br>" + T("notaAnteprima")
    : LOGIN_ONLINE ? T("nota") : T("notaLocale");
  document.getElementById("piede").innerHTML = T("piede", {{PROMEMORIA}});
  document.getElementById("aggiornato").textContent = T("aggiornato") + " " +
    new Intl.DateTimeFormat(T("locale"), { timeZone: "Europe/Rome", weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(AGGIORNATO);
  disegnaRapidi();
}

/* ================= Archivio account e preferenze =================
   Anteprima: salvati in questo browser. Versione pubblicata: su Firebase (gratuito),
   così con nome utente e password li ritrovi su ogni dispositivo. */
const CHIAVE = "sport-in-tv:v2";
function leggi() { try { return JSON.parse(localStorage.getItem(CHIAVE)) || {}; } catch { return {}; } }
let archivio = leggi();
archivio.utenti ||= {};
function salvaArchivio() { try { localStorage.setItem(CHIAVE, JSON.stringify(archivio)); } catch {} }
async function hashPassword(nome, pw) {
  const testo = nome + ":" + pw + ":sport-in-tv";
  try {
    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(testo));
    return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
  } catch { let h = 0; for (const c of testo) h = (h * 31 + c.charCodeAt(0)) | 0; return "x" + h; }
}
const sessione = () => archivio.sessione;
const prefsCorrenti = () => {
  const s = sessione(); if (!s) return null;
  return s.tipo === "utente" ? archivio.utenti[s.nome]?.prefs || null : archivio.ospite?.prefs || null;
};
function salvaPrefs(p) {
  const s = sessione();
  if (s.tipo === "utente") archivio.utenti[s.nome].prefs = p; else archivio.ospite = { prefs: p };
  salvaArchivio();
}

/* ================= Accesso ================= */
let modo = "accedi";
const fAcc = document.getElementById("form-accesso"), err = document.getElementById("errore-accesso");
fAcc.querySelector(".tabs-accesso").addEventListener("click", ev => {
  const b = ev.target.closest("button"); if (!b) return;
  modo = b.dataset.modo;
  fAcc.querySelectorAll(".tabs-accesso button").forEach(x => x.classList.toggle("on", x === b));
  document.getElementById("invia-accesso").textContent = modo === "accedi" ? T("accedi") : T("creaEntra");
  document.getElementById("password").autocomplete = modo === "accedi" ? "current-password" : "new-password";
  err.textContent = "";
});
fAcc.addEventListener("submit", async ev => {
  ev.preventDefault();
  const nome = document.getElementById("utente").value.trim().toLowerCase();
  const pw = document.getElementById("password").value;
  if (!/^[a-z0-9._-]{3,20}$/.test(nome)) { err.textContent = T("errNome"); return; }
  if (pw.length < 4) { err.textContent = T("errPw"); return; }
  const h = await hashPassword(nome, pw), u = archivio.utenti[nome];
  if (modo === "crea") {
    if (u) { err.textContent = T("errEsiste"); return; }
    archivio.utenti[nome] = { hash: h, prefs: null };
  } else {
    if (!u) { err.textContent = T("errNonTrovato"); return; }
    if (u.hash !== h) { err.textContent = T("errPwSbagliata"); return; }
  }
  archivio.sessione = { tipo: "utente", nome }; archivio.ultimo = nome;
  salvaArchivio();
  apri(prefsCorrenti() ? "home" : "pref");
});
if (!ANTEPRIMA && !LOGIN_ONLINE) {
  document.getElementById("google").hidden = true;
  document.querySelector('[data-t="oppureUtente"]').hidden = true;
}
document.getElementById("google").addEventListener("click", () => {
  // Versione pubblicata: login Google vero tramite Firebase. Anteprima: account Google simulato.
  archivio.utenti["@google"] ||= { hash: null, prefs: null };
  archivio.sessione = { tipo: "utente", nome: "@google" };
  salvaArchivio();
  apri(prefsCorrenti() ? "home" : "pref");
});
document.getElementById("ospite").addEventListener("click", () => {
  archivio.sessione = { tipo: "ospite", nome: "Ospite" }; salvaArchivio();
  apri(prefsCorrenti() ? "home" : "pref");
});

/* ================= Preferenze ================= */
let bozza;
const norm = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
function disegnaPreferenze() {
  const primaVolta = !prefsCorrenti();
  document.getElementById("pref-passo").textContent = primaVolta ? T("passo") : T("impostazioni");
  document.getElementById("pref-titolo").textContent = primaVolta ? T("prefTitolo") : T("prefTitolo2");
  document.getElementById("salva").textContent = primaVolta ? T("mostrami") : T("salva");
  document.getElementById("indietro").hidden = primaVolta;
  document.getElementById("annulla").hidden = primaVolta;
  document.getElementById("annulla").textContent = T("annulla");
  document.getElementById("indietro").setAttribute("aria-label", T("indietro"));
  document.getElementById("barra-salva").classList.toggle("due", !primaVolta);
  const s = sessione() || {};
  document.getElementById("pref-account").innerHTML = `
    <div class="account-riga">
      <div class="avatar">${s.nome === "@google" ? "G" : esc((s.nome || "?").charAt(0).toUpperCase())}</div>
      <div class="chi">${esc(s.tipo === "ospite" ? T("nomeOspite") : s.nome === "@google" ? T("accountGoogle") : s.nome || "")}<small>${s.tipo === "ospite" ? T("senzaAccount") : LOGIN_ONLINE || ANTEPRIMA ? T("conAccount") : T("senzaAccount").replace(/^[^·]*· /, "")}</small></div>
      <button id="esci">${s.tipo === "ospite" ? T("accedi") : T("esci")}</button>
    </div>`;
  document.getElementById("griglia-sport").innerHTML = ORDINE.map(k => `
    <button class="scelta-sport${bozza.sport.includes(k) ? " on" : ""}" data-sport="${k}" style="--c:${SPORT[k].colore}">
      <span class="emoji">${SPORT[k].emoji}</span>${esc(nomeSport(k))}
    </button>`).join("");
  document.getElementById("leghe-scelte").innerHTML = ORDINE
    .filter(k => bozza.sport.includes(k) && SPORT[k].leghe.length > 1)
    .map(k => `
    <div class="blocco-leghe" style="--c:${SPORT[k].colore}">
      <div class="tit"><span class="emoji">${SPORT[k].emoji}</span>${esc(nomeSport(k))}: ${esc(T("quali"))}</div>
      <div class="leghe">${SPORT[k].leghe.map(l =>
        `<button class="lega${(bozza.leghe[k] || []).includes(l) ? " on" : ""}" data-sport="${k}" data-lega="${esc(l)}">${esc(tr(l))}</button>`).join("")}</div>
    </div>`).join("");
  document.getElementById("mie-squadre").innerHTML = bozza.squadre.map((q, i) =>
    `<span class="squadra-tag">⭐ ${esc(q)} <button data-togli="${i}" aria-label="✕ ${esc(q)}">✕</button></span>`).join("");
  document.getElementById("salva").disabled = !bozza.sport.length && !bozza.squadre.length;
}
document.getElementById("s-pref").addEventListener("click", ev => {
  const t = ev.target;
  const sp = t.closest(".scelta-sport");
  if (sp) {
    const k = sp.dataset.sport, i = bozza.sport.indexOf(k);
    if (i >= 0) bozza.sport.splice(i, 1);
    else { bozza.sport.push(k); if (!bozza.leghe[k]?.length) bozza.leghe[k] = [...SPORT[k].leghe]; }
    return disegnaPreferenze();
  }
  const lg = t.closest(".lega");
  if (lg) {
    const k = lg.dataset.sport, l = lg.dataset.lega, lista = bozza.leghe[k] ||= [];
    lista.includes(l) ? lista.splice(lista.indexOf(l), 1) : lista.push(l);
    return disegnaPreferenze();
  }
  const togli = t.closest("[data-togli]");
  if (togli) { bozza.squadre.splice(+togli.dataset.togli, 1); return disegnaPreferenze(); }
  if (t.id === "esci") { delete archivio.sessione; salvaArchivio(); return apri("accesso"); }
});
const cerca = document.getElementById("cerca"), sugg = document.getElementById("suggerimenti");
function aggiungiSquadra(nome) {
  nome = (nome || "").trim();
  if (nome && !bozza.squadre.some(q => norm(q) === norm(nome))) bozza.squadre.push(nome);
  cerca.value = ""; sugg.hidden = true; disegnaPreferenze();
}
cerca.addEventListener("input", () => {
  const q = norm(cerca.value.trim());
  if (!q) { sugg.hidden = true; return; }
  const trovate = SQUADRE_NOTE.filter(s => norm(s).includes(q) && !bozza.squadre.includes(s)).slice(0, 8);
  sugg.innerHTML = trovate.map(s => `<button data-nome="${esc(s)}">⭐ ${esc(s)}</button>`).join("") +
    (trovate.some(s => norm(s) === q) ? "" : `<button data-nome="${esc(cerca.value.trim())}">＋ ${esc(T("aggiungi"))} “${esc(cerca.value.trim())}”</button>`);
  sugg.hidden = false;
});
cerca.addEventListener("keydown", ev => { if (ev.key === "Enter") { ev.preventDefault(); aggiungiSquadra(sugg.querySelector("button")?.dataset.nome || cerca.value); } });
sugg.addEventListener("click", ev => { const b = ev.target.closest("button"); if (b) aggiungiSquadra(b.dataset.nome); });
document.addEventListener("click", ev => { if (!ev.target.closest(".cerca-squadra")) sugg.hidden = true; });
document.getElementById("salva").addEventListener("click", () => {
  salvaPrefs(JSON.parse(JSON.stringify(bozza)));
  filtri = filtriVuoti(); sezione = "miei";
  apri("home");
});
document.getElementById("apri-impostazioni").addEventListener("click", () => apri("pref"));
// Torna agli eventi senza salvare le modifiche
for (const id of ["indietro", "annulla"])
  document.getElementById(id).addEventListener("click", () => apri("home"));

let schermoAttuale = "accesso";
function apri(nome) {
  schermoAttuale = nome;
  for (const [id, n] of [["s-accesso", "accesso"], ["s-pref", "pref"], ["s-home", "home"]])
    document.getElementById(id).hidden = nome !== n;
  if (nome === "accesso") {
    fAcc.querySelector('[data-modo="accedi"]').click();
    document.getElementById("password").value = "";
    if (archivio.ultimo) document.getElementById("utente").value = archivio.ultimo;
  }
  if (nome === "pref") {
    const p = prefsCorrenti();
    bozza = p ? JSON.parse(JSON.stringify(p)) : { sport: [], leghe: {}, squadre: [] };
    disegnaPreferenze();
  }
  if (nome === "home") disegna();
  window.scrollTo(0, 0);
}
function ridisegnaSchermo() {
  if (schermoAttuale === "pref") disegnaPreferenze();
  if (schermoAttuale === "home") disegna();
}

/* ================= Date ================= */
const linkCal = file => location.protocol.startsWith("http")
  ? "webcal://" + location.host + location.pathname.replace(/[^/]*$/, "") + file : file;
const slug = s => norm(s).replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
const fmt = (opz) => new Intl.DateTimeFormat(T("locale"), { timeZone: "Europe/Rome", ...opz });
const fOra = d => fmt({ hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
const fGiorno = d => fmt({ weekday: "long", day: "numeric", month: "long" }).format(d);
const fSett = d => fmt({ weekday: "short" }).format(d).replace(".", "");
const fNum = d => fmt({ day: "numeric" }).format(d);
const oraRoma = d => +new Intl.DateTimeFormat("it-IT", { timeZone: "Europe/Rome", hour: "numeric", hour12: false }).format(d) % 24;
const fBreveData = d => fmt({ day: "2-digit", month: "2-digit" }).format(d);
const chiave = d => d.toLocaleDateString("sv-SE", { timeZone: "Europe/Rome" });
const maiusc = s => s.charAt(0).toUpperCase() + s.slice(1);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function relativo(d, ora) {
  const k = chiave(d);
  if (k === chiave(ora)) return T("oggi");
  if (k === chiave(new Date(ora.getTime() + 864e5))) return T("domani");
  return null;
}

/* ================= Preferiti ================= */
function delCuore(e) {
  const p = prefsCorrenti(); if (!p || !p.squadre.length) return false;
  const dove = [e.titolo, ...(e.squadre || [])].map(norm);
  return p.squadre.some(q => dove.some(d => d.includes(norm(q))));
}
function interessa(e) {
  const p = prefsCorrenti(); if (!p) return true;
  return delCuore(e) || (p.sport.includes(e.sport) && (p.leghe[e.sport] || SPORT[e.sport].leghe).includes(e.lega));
}

/* ================= Righe e gruppi per competizione ================= */
const pezziCanale = testo => (testo || "").split(/\s+·\s+|\s+o\s+/).filter(Boolean);
function canaliHTML(testo) {
  return pezziCanale(testo).map(c => {
    const free = /\(gratis\)/i.test(c);
    return `${esc(tr(c.replace(/\s*\(gratis\)/i, "")))}${free ? ` <span class="free">${esc(T("gratis"))}</span>` : ""}`;
  }).join('<span class="sep"> · </span>');
}
const mmss = ms => { const t = Math.max(0, Math.round(ms / 1000)); return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`; };
function liveRiga(e, ora) {  // usata nel riquadro "Il prossimo" in alto
  const l = e.live;
  if (!l || e.inizio > ora || e.fine < ora) return "";
  if (l.giro) {
    const pct = Math.min(100, Math.round(l.giro / l.giri * 100));
    return `<div class="live-riga giri"><span class="num">${esc(T("giro"))} ${l.giro}<small>/${l.giri}</small></span>
      <span class="barra-giri"><i style="width:${pct}%"></i></span></div>`;
  }
  if (l.fase) return `<div class="live-riga"><span class="fase">${esc(l.fase)}</span>
      ${l.fineFase ? `<span class="conto">⏱ <b data-fine-fase="${l.fineFase.getTime()}">${mmss(l.fineFase - ora)}</b></span>` : ""}</div>`;
  if (l.punteggio) return `<div class="live-riga"><span class="punteggio">${esc(l.punteggio)}</span><span class="minuto">${esc(l.minuto || tr(l.dettaglio || ""))}</span></div>`;
  return "";
}
setInterval(() => {  // conti alla rovescia di qualifiche e prove
  const ora = Date.now();
  document.querySelectorAll("[data-fine-fase]").forEach(el => {
    const resto = +el.dataset.fineFase - ora;
    el.textContent = resto > 0 ? mmss(resto) : T("inChiusura");
  });
}, 1000);

const inOnda = (e, ora) => e.inizio <= ora && ora <= e.fine;
const MOTORI = ["f1", "motogp", "sbk"];
// Punteggio diviso per lato: "2–1" -> ["2","1"]; tennis "6-4 7-5" -> ["6 7","4 5"]
function puntiPerLato(e, ora) {
  // Finita: risultato ufficiale, oppure l'ultimo punteggio live finché non arriva quello ufficiale
  const src = inOnda(e, ora) && e.live?.punteggio ? e.live.punteggio : e.fine < ora ? (e.ris || e.live?.punteggio) : null;
  if (!src) return null;
  const set = src.trim().split(/\s+/).map(x => x.split(/[–-]/));
  if (set.every(x => x.length === 2)) return [set.map(x => x[0]).join(" "), set.map(x => x[1]).join(" ")];
  return null;
}
// Bandiera emoji da codice ISO ("it" -> 🇮🇹; Inghilterra/Scozia/Galles hanno emoji proprie)
const SPECIALI = { "gb-eng": "🏴\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}",
  "gb-sct": "🏴\u{E0067}\u{E0062}\u{E0073}\u{E0063}\u{E0074}\u{E007F}", "gb-wls": "🏴\u{E0067}\u{E0062}\u{E0077}\u{E006C}\u{E0073}\u{E007F}", "gb-nir": "🇬🇧", "xk": "🇽🇰" };
function bandiera(iso) {
  if (!iso) return "";
  if (SPECIALI[iso]) return SPECIALI[iso];
  return iso.length === 2 ? String.fromCodePoint(...[...iso.toUpperCase()].map(c => 0x1F1E6 + c.charCodeAt(0) - 65)) : "";
}
// Simbolo accanto al nome: bandiera per nazionali/giocatori/piloti, logo per i club (con iniziale se non si carica)
function stemma(e, i, nome) {
  const iso = e.bandiere?.[i];
  if (iso) return `<span class="band emoji">${bandiera(iso)}</span>`;
  const logo = e.loghi?.[i], ini = esc((nome || "?").trim().charAt(0).toUpperCase());
  if (logo) return `<span class="logo"><img src="${esc(logo)}" alt="" loading="lazy" onerror="this.parentNode.classList.add('ini');this.parentNode.textContent='${ini}'"></span>`;
  return e.sport === "calcio" || e.sport === "basket" || e.sport === "volley" ? `<span class="logo ini">${ini}</span>` : "";
}
function squadraBtn(nome, classe = "", e = null, i = 0) {
  return `<span class="squadra ${classe}">${e ? stemma(e, i, nome) : ""}<span class="sq-nome">${esc(tr(nome))}</span></span>`;
}
const cognome = n => (n || "").trim().split(/\s+/).slice(-1)[0];
function riga(e, ora, canaleGruppo, conData = false) {
  const live = inOnda(e, ora), fine = e.fine < ora, cuore = delCuore(e);
  const l = e.live || {};
  let tempo;
  if (live) tempo = `<span class="t-live">${esc(l.minuto || (l.fase ? l.fase : "LIVE"))}</span>`;
  else if (fine) tempo = `<span class="t-fine">${esc(T("fin"))}</span>`;
  else tempo = fOra(e.inizio);
  if (conData) tempo = `<span class="t-data">${esc(fBreveData(e.inizio))}</span>${fine ? "" : `<span class="t-ora">${fOra(e.inizio)}</span>`}`;

  const due = e.squadre?.length === 2 && !MOTORI.includes(e.sport);
  const punti = due ? puntiPerLato(e, ora) : null;
  const vince = punti && fine && !isNaN(+punti[0]) && !isNaN(+punti[1]) ? (+punti[0] > +punti[1] ? 0 : +punti[0] < +punti[1] ? 1 : -1) : -1;
  let corpo = due
    ? squadraBtn(e.squadre[0], vince === 0 ? "vince" : vince === 1 ? "perde" : "", e, 0) + squadraBtn(e.squadre[1], vince === 1 ? "vince" : vince === 0 ? "perde" : "", e, 1)
    : `<div class="r-nome">${esc(tr(e.riga))}</div>`;
  const extra = [];
  if (e.turno) extra.push(esc(tr(e.turno)));
  if (fine && e.classifica?.length) {
    const p1 = e.classifica[0];
    extra.push(`<span class="podio">🥇 ${bandiera(p1[2])} <b>${esc(cognome(p1[1]))}</b>${e.classifica[1] ? ` · 🥈 ${bandiera(e.classifica[1][2])} ${esc(cognome(e.classifica[1][1]))}` : ""}</span>`);
  }
  if (live && l.fase && l.fineFase) extra.push(`⏱ <b data-fine-fase="${l.fineFase.getTime()}">${mmss(l.fineFase - ora)}</b>`);
  if (live && l.giro) extra.push(`${esc(T("giro"))} <b>${l.giro}</b>/${l.giri} <span class="barra-giri mini"><i style="width:${Math.min(100, Math.round(l.giro / l.giri * 100))}%"></i></span>`);
  if (live && l.dettaglio) extra.push(esc(tr(l.dettaglio)));
  if (extra.length) corpo += `<div class="r-extra">${extra.join('<span class="sep"> · </span>')}</div>`;

  const destra = punti ? `<div class="r-punti${live ? " live" : ""}"><span>${esc(punti[0])}</span><span>${esc(punti[1])}</span></div>`
    : `<div class="r-punti"></div>`;
  const tv = pezziCanale(e.canale).map(c => {
    const free = /\(gratis\)/i.test(c);
    return `<span${free ? ' class="free"' : ""}>${esc(tr(c.replace(/\s*\(gratis\)/i, "")))}${free ? ` <small>${esc(T("gratis"))}</small>` : ""}</span>`;
  }).join("");
  const colTv = `<div class="r-tv">${tv}</div>`;
  const azione = !fine && !live
    ? `<a class="avvisami emoji" href="eventi/${e.id}.ics" title="${esc(T("avvisami"))}" aria-label="${esc(T("avvisami"))}">🔔</a>` : "";
  return `<div class="riga-ev${live ? " live" : ""}${fine ? " fine" : ""}${cuore ? " cuore" : ""}${conData ? " con-data" : ""}" data-evento="${e.id}" role="button" tabindex="0">
    <div class="r-tempo">${tempo}</div><div class="r-corpo">${corpo}</div>${destra}<div class="r-azione">${azione}</div></div>`;
}

const tennisAperti = new Set();
function canalePrevalente(lista) {
  // Si conta su tutta la competizione, così un canale "speciale" (es. l'Italia su Rai) resta sulla sua riga
  const conta = {};
  EVENTI.filter(e => e.lega === lista[0].lega).forEach(e => conta[e.canale] = (conta[e.canale] || 0) + 1);
  return Object.entries(conta).sort((a, b) => b[1] - a[1])[0]?.[0] || "";
}
function gruppoHTML(nome, lista, ora) {
  const s = SPORT[lista[0].sport], tennis = lista[0].sport === "tennis";
  const [base, ...resto] = nome.split(" · ");
  const canale = canalePrevalente(lista);
  const aperto = !tennis || tennisAperti.has(nome);
  const visibili = aperto ? lista : lista.filter(e => delCuore(e) || inOnda(e, ora));
  const nLive = lista.filter(e => inOnda(e, ora)).length;
  const testa = `
    <${tennis ? "button" : "div"} class="g-testa${tennis ? " apribile" : ""}" ${tennis ? `data-apri="${esc(nome)}" aria-expanded="${aperto}"` : ""}>
      <span class="g-ico emoji">${s.emoji}</span>
      <span class="g-testo">
        <span class="g-nome"><b>${esc(tr(base))}</b>${resto.length ? `<span>${esc(tr(resto.join(" · ")))}</span>` : ""}</span>
      </span>
      ${nLive ? `<span class="g-live">${nLive} LIVE</span>` : ""}
      ${tennis ? `<span class="g-conta">${lista.length}<span class="freccia">${aperto ? "▾" : "▸"}</span></span>` : ""}
    </${tennis ? "button" : "div"}>`;
  const corpo = visibili.map(e => riga(e, ora, canale)).join("");
  const nota = tennis && !aperto ? `<button class="g-mostra" data-apri="${esc(nome)}">${esc(T("mostraPartite", lista.length))} ▾</button>` : "";
  return `<section class="gruppo" style="--c:${s.colore}">${testa}${corpo}${nota}</section>`;
}
function gruppiHTML(lista, ora) {
  const mappa = new Map();
  lista.forEach(e => { mappa.has(e.gruppo) || mappa.set(e.gruppo, []); mappa.get(e.gruppo).push(e); });
  const pos = e => { const i = SPORT[e.sport].leghe.indexOf(e.lega); return i < 0 ? 99 : i; };
  const ordinati = [...mappa.entries()].sort(([, a], [, b]) =>
    (b.some(delCuore) - a.some(delCuore)) || (ORDINE.indexOf(a[0].sport) - ORDINE.indexOf(b[0].sport)) ||
    (pos(a[0]) - pos(b[0])) || a[0].gruppo.localeCompare(b[0].gruppo) || (a[0].inizio - b[0].inizio));
  return ordinati.map(([nome, ev]) => gruppoHTML(nome, ev.sort((x, y) => x.inizio - y.inizio || x.titolo.localeCompare(y.titolo)), ora)).join("");
}

/* Quadratini: 🔴 LIVE (solo se c'è qualcosa in onda) + Tutti + sport */
// Mostra sempre tutti gli sport seguiti: quelli senza eventi nel giorno restano grigi e non cliccabili
function quadriSport(lista, attivi, soloLive, ora, extra = "", sportFissi = ORDINE) {
  const nLive = lista.filter(e => inOnda(e, ora)).length;
  const elenco = ORDINE.filter(k => sportFissi.includes(k) || lista.some(e => e.sport === k));
  return (nLive ? `<button class="quadro live-q${soloLive ? " on" : ""}" data-q="live" aria-label="LIVE"><span class="pallino-live"></span>LIVE<span class="n">${nLive}</span></button>` : "") +
    `<button class="quadro tutti${!attivi.length && !soloLive ? " on" : ""}" data-q="tutti">${esc(T("tutti"))}</button>` +
    elenco.map(k => {
      const n = lista.filter(e => e.sport === k).length, spento = !n && !attivi.includes(k);
      return `<button class="quadro emoji${attivi.includes(k) ? " on" : ""}${spento ? " spento" : ""}" data-q="${k}"${spento ? " disabled" : ""} style="--c:${SPORT[k].colore}" title="${esc(nomeSport(k))}" aria-label="${esc(nomeSport(k))}">${SPORT[k].emoji}${n ? `<span class="n">${n}</span>` : ""}</button>`;
    }).join("") + extra;
}
function mantieniScorrimento(el, html, centra) {
  const x = el.scrollLeft; el.innerHTML = html; el.scrollLeft = x;
  const att = el.querySelector(centra || ".on:not(.tutti)");
  if (att && (att.offsetLeft < el.scrollLeft || att.offsetLeft + att.offsetWidth > el.scrollLeft + el.clientWidth))
    el.scrollLeft = centra ? att.offsetLeft - el.clientWidth / 2 + att.offsetWidth / 2 : att.offsetLeft - 16;
}
const cliccaQuadro = (stato, k) => {
  if (k === "live") stato.live = !stato.live;
  else if (k === "tutti") { stato.sport = []; stato.live = false; }
  else stato.sport = stato.sport.includes(k) ? stato.sport.filter(x => x !== k) : [...stato.sport, k];
};

/* ================= Oggi in TV ================= */
let sezione = "oggi";
const statoOggi = { sport: [], live: false };
function eventiOggi(ora) { return EVENTI.filter(e => chiave(e.inizio) === chiave(ora)); }
function disegnaOggi(ora) {
  const oggi = eventiOggi(ora);
  statoOggi.sport = statoOggi.sport.filter(k => oggi.some(e => e.sport === k));
  if (!oggi.some(e => inOnda(e, ora))) statoOggi.live = false;
  mantieniScorrimento(document.getElementById("sport-oggi"), quadriSport(oggi, statoOggi.sport, statoOggi.live, ora));
  const vis = oggi.filter(e => (!statoOggi.sport.length || statoOggi.sport.includes(e.sport)) && (!statoOggi.live || inOnda(e, ora)));

  const prossimi = vis.filter(e => e.fine >= ora);
  // Priorità: in onda del cuore > in onda > prossimo del cuore > prossimo
  const hero = document.getElementById("hero");
  const p = prossimi.find(e => inOnda(e, ora) && delCuore(e)) || prossimi.find(e => inOnda(e, ora)) ||
            prossimi.find(delCuore) || prossimi[0];
  if (p && !statoOggi.live) {
    const s = SPORT[p.sport], live = inOnda(p, ora), l = p.live || {};
    const nLive = prossimi.filter(e => inOnda(e, ora)).length;
    let destra = `<div class="h-grande">${fOra(p.inizio)}</div><div class="h-sotto">${esc(T("oggi"))}</div>`;
    if (live && l.punteggio) destra = `<div class="h-grande live">${esc(l.punteggio)}</div><div class="h-sotto live">${esc(l.minuto || tr(l.dettaglio || "LIVE"))}</div>`;
    else if (live && l.giro) destra = `<div class="h-grande live">${l.giro}<small>/${l.giri}</small></div><div class="h-sotto live">${esc(T("giro"))}</div>`;
    else if (live && l.fase) destra = `<div class="h-grande live">${esc(l.fase)}</div><div class="h-sotto live">${l.fineFase ? `⏱ <b data-fine-fase="${l.fineFase.getTime()}">${mmss(l.fineFase - ora)}</b>` : "LIVE"}</div>`;
    else if (live) destra = `<div class="h-grande live">LIVE</div>`;
    hero.hidden = false; hero.style.setProperty("--c", s.colore);
    hero.innerHTML = `
      <div class="icona emoji">${s.emoji}</div>
      <div class="testo">
        <div class="etichetta">${live ? T("inOnda") + (nLive > 1 ? ` · +${nLive - 1}` : "") : T("prossimo")}</div>
        <div class="tit">${esc(tr(p.squadre?.length === 2 && !MOTORI.includes(p.sport) ? p.titolo : p.riga))}</div>
        <div class="meta">${esc(tr(p.gruppo))}</div>
        <div class="meta tv">📺 ${pezziCanale(p.canale).map(c => esc(tr(c.replace(/\s*\(gratis\)/i, "")))).join(" · ")}</div>
      </div>
      <div class="quando">${destra}</div>`;
  } else hero.hidden = true;

  document.getElementById("lista-oggi").innerHTML = gruppiHTML(vis, ora) ||
    `<div class="vuoto"><span class="emoji">🛋️</span>${T(statoOggi.live ? "vuotoLive" : "vuotoOggi")}</div>`;
}
document.getElementById("sport-oggi").addEventListener("click", ev => {
  const b = ev.target.closest(".quadro"); if (b) { cliccaQuadro(statoOggi, b.dataset.q); disegna(); }
});

/* ================= I miei eventi ================= */
const filtriVuoti = () => ({ giorno: chiave(new Date()), sport: [], leghe: [], soloCuore: false, live: false });
let filtri = filtriVuoti(), bozzaFiltri;
const passaFiltri = (e, f, conGiorno = true, conSport = true) =>
  (!conGiorno || chiave(e.inizio) === f.giorno) &&
  (!conSport || !f.sport.length || f.sport.includes(e.sport)) &&
  (!f.leghe.length || f.leghe.includes(e.lega)) &&
  (!f.soloCuore || delCuore(e));
const eventiMiei = () => EVENTI.filter(interessa);
const GIORNI_INDIETRO = {{PASSATI}}, GIORNI_AVANTI = 7;

function disegnaMiei(ora) {
  const miei = eventiMiei();
  // 7 giorni attorno al giorno scelto; le frecce spostano di una settimana
  const scelto = new Date(filtri.giorno + "T12:00:00");
  const giorni = [];
  for (let i = -3; i <= 3; i++) giorni.push(new Date(scelto.getTime() + i * 864e5));
  mantieniScorrimento(document.getElementById("striscia"), giorni.map(d => {
    const k = chiave(d), ev = miei.filter(e => chiave(e.inizio) === k && passaFiltri(e, filtri, false));
    const colori = [...new Set(ev.map(e => SPORT[e.sport].colore))].slice(0, 4);
    const passato = k < chiave(ora);
    return `<button class="giorno-btn${filtri.giorno === k ? " on" : ""}${ev.length ? "" : " vuoto-g"}${passato ? " passato" : ""}" data-g="${k}">
      <span class="gs">${esc(k === chiave(ora) ? T("oggi") : fSett(d))}</span><span class="gn">${fNum(d)}</span>
      <span class="punti">${colori.map(c => `<i style="--c:${c}"></i>`).join("")}</span></button>`;
  }).join(""), ".giorno-btn.on");

  const delGiorno = miei.filter(e => passaFiltri(e, filtri, true, false));
  if (!delGiorno.some(e => inOnda(e, ora))) filtri.live = false;
  const nExtra = filtri.leghe.length + (filtri.soloCuore ? 1 : 0);
  const btnFiltri = `<span class="separa"></span><button class="quadro fil" id="apri-filtri"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/></svg>${esc(T("filtri"))}${nExtra ? `<span class="n">${nExtra}</span>` : ""}</button>`;
  mantieniScorrimento(document.getElementById("sport-miei"), quadriSport(delGiorno, filtri.sport, filtri.live, ora, btnFiltri, prefsCorrenti()?.sport || ORDINE));

  const parti = [];
  if (filtri.soloCuore) parti.push(T("soloDelCuore"));
  filtri.leghe.forEach(l => parti.push(tr(l)));
  const rias = document.getElementById("riassunto");
  rias.hidden = !parti.length; rias.textContent = parti.join(" · ");

  const vis = delGiorno.filter(e => passaFiltri(e, filtri) && (!filtri.live || inOnda(e, ora)));
  const d = new Date(filtri.giorno + "T12:00:00"), rel = relativo(d, ora);
  document.getElementById("titolo-giorno").innerHTML = `<b>${esc(rel || maiusc(fGiorno(d)))}</b>${rel ? `<span>${esc(fGiorno(d))}</span>` : ""}` +
    (filtri.giorno !== chiave(ora) ? `<button class="torna-oggi" id="torna-oggi">${esc(T("oggi"))} ↩</button>` : "");
  document.getElementById("lista-miei").innerHTML = gruppiHTML(vis, ora) ||
    `<div class="vuoto"><span class="emoji">🗓️</span>${T("vuotoGiorno")}</div>`;
}
const spostaGiorno = n => { const d = new Date(filtri.giorno + "T12:00:00"); d.setDate(d.getDate() + n); filtri.giorno = chiave(d); disegna(); };
document.getElementById("sett-prec").addEventListener("click", () => spostaGiorno(-7));
document.getElementById("sett-succ").addEventListener("click", () => spostaGiorno(7));
document.getElementById("titolo-giorno").addEventListener("click", ev => {
  if (ev.target.id === "torna-oggi") { filtri.giorno = chiave(new Date()); disegna(); }
});
document.getElementById("striscia").addEventListener("click", ev => {
  const b = ev.target.closest(".giorno-btn"); if (b) { filtri.giorno = b.dataset.g; disegna(); }
});
document.getElementById("v-miei").addEventListener("click", ev => {
  if (ev.target.closest("#apri-filtri")) return pannello(true);
  const q = ev.target.closest("#sport-miei .quadro[data-q]"); if (!q) return;
  cliccaQuadro(filtri, q.dataset.q); disegna();
});

/* Tennis: apri/chiudi torneo · Squadra: apri la sua pagina */
document.getElementById("s-home").addEventListener("click", ev => {
  const a = ev.target.closest("[data-apri]");
  if (a) { const n = a.dataset.apri; tennisAperti.has(n) ? tennisAperti.delete(n) : tennisAperti.add(n); return disegna(); }
  if (ev.target.closest(".avvisami")) return;  // la campanella scarica solo il promemoria
  const r = ev.target.closest("[data-evento]");
  if (r) apriPartita(r.dataset.evento);
});
document.getElementById("s-home").addEventListener("keydown", ev => {
  const r = ev.target.closest?.("[data-evento]");
  if (r && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); apriPartita(r.dataset.evento); }
});

/* ================= Pagina squadra / giocatore ================= */
let squadraAperta = null;
function apriSquadra(nome) {
  squadraAperta = nome;
  const ora = new Date(), n = norm(nome);
  const sue = EVENTI.filter(e => (e.squadre || []).some(q => norm(q) === n)).sort((a, b) => a.inizio - b.inizio);
  const passate = sue.filter(e => e.fine < ora).reverse(), prossime = sue.filter(e => e.fine >= ora);
  const segui = (prefsCorrenti()?.squadre || []).some(q => norm(q) === n);
  const blocco = (tit, lista) => lista.length ? `<h4>${esc(tit)}</h4><div class="gruppo lista-squadra">${lista.map(e =>
    `<div class="mini-comp">${SPORT[e.sport].emoji} ${esc(tr(e.gruppo))}</div>` + riga(e, ora, "", true)).join("")}</div>` : "";
  const conBand = sue.find(e => e.bandiere?.[(e.squadre || []).findIndex(q => norm(q) === n)]);
  const iso = conBand ? conBand.bandiere[conBand.squadre.findIndex(q => norm(q) === n)] : null;
  document.getElementById("sq-nome").textContent = (iso ? bandiera(iso) + " " : "") + tr(nome);
  document.getElementById("sq-segui").textContent = segui ? "⭐ " + T("seguita") : "☆ " + T("segui");
  document.getElementById("sq-segui").classList.toggle("on", segui);
  document.getElementById("sq-lista").innerHTML =
    blocco(T("prossime"), prossime) + blocco(T("risultati"), passate) ||
    `<p class="spiega">${esc(T("nessunaPartita"))}</p>`;
  document.getElementById("pannello-squadra").hidden = false;
  document.getElementById("velo").hidden = false;
}
function chiudiSquadra() {
  document.getElementById("pannello-squadra").hidden = true;
  document.getElementById("velo").hidden = true;
  squadraAperta = null;
}
document.getElementById("chiudi-squadra").addEventListener("click", chiudiSquadra);
document.getElementById("sq-segui").addEventListener("click", () => {
  const s = sessione(); if (!s) return;
  const p = prefsCorrenti() || { sport: [], leghe: {}, squadre: [] }, n = norm(squadraAperta);
  const i = p.squadre.findIndex(q => norm(q) === n);
  i >= 0 ? p.squadre.splice(i, 1) : p.squadre.push(squadraAperta);
  salvaPrefs(p); apriSquadra(squadraAperta); disegna();
});
document.getElementById("sq-lista").addEventListener("click", ev => {
  if (ev.target.closest(".avvisami")) return;
  const r = ev.target.closest("[data-evento]"); if (r) { chiudiSquadra(); apriPartita(r.dataset.evento); }
});

/* ================= Scheda partita ================= */
let partitaAperta = null, schedaPartita = "riassunto";
const STAT_NOMI = {
  it: { possessionPct: "Possesso palla", totalShots: "Tiri", shotsOnTarget: "Tiri in porta", wonCorners: "Calci d'angolo",
        saves: "Parate", foulsCommitted: "Falli", offsides: "Fuorigioco", yellowCards: "Cartellini gialli", redCards: "Cartellini rossi",
        totalPasses: "Passaggi", accuratePasses: "Passaggi riusciti", totalTackles: "Contrasti", interceptions: "Intercetti" },
  en: { possessionPct: "Possession", totalShots: "Shots", shotsOnTarget: "Shots on target", wonCorners: "Corners",
        saves: "Saves", foulsCommitted: "Fouls", offsides: "Offsides", yellowCards: "Yellow cards", redCards: "Red cards",
        totalPasses: "Passes", accuratePasses: "Accurate passes", totalTackles: "Tackles", interceptions: "Interceptions" },
};
const ICONE = {
  gol: '<span class="ico-ev emoji">⚽</span>', rigore: '<span class="ico-ev emoji">⚽</span>', autogol: '<span class="ico-ev emoji aut">⚽</span>',
  rig_sbagliato: '<span class="ico-ev sbagliato">✕</span>', giallo: '<span class="ico-ev cart giallo"></span>',
  rosso: '<span class="ico-ev cart rosso"></span>',
  cambio: '<span class="ico-ev cambio"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8h13l-3-3" stroke="#22c55e"/><path d="M20 16H7l3 3" stroke="#ef4444"/></svg></span>',
};
const tempoDi = m => { const n = minuto_num(m); return n <= 45.99 ? 1 : n <= 90.99 ? 2 : n <= 120.99 ? 3 : 4; };
function minuto_num(m) { const n = (m || "").match(/\d+/g) || []; return n.length ? +n[0] + (n[1] ? +n[1] / 100 : 0) : 999; }

function riassuntoHTML(e, ora) {
  const cr = e.cronaca || [];
  if (!cr.length) return `<p class="p-nota">${esc(T(e.fine < ora || inOnda(e, ora) ? "cronacaVuota" : "cronacaDopo"))}</p>`;
  const segna = x => ["gol", "rigore", "autogol"].includes(x.tipo);
  let html = "";
  for (const t of [1, 2, 3, 4]) {
    const ev = cr.filter(x => tempoDi(x.min) === t);
    if (!ev.length && !(t <= 2 && (inOnda(e, ora) || e.fine < ora) && (t === 1 || cr.some(x => tempoDi(x.min) >= 2)))) continue;
    const g0 = ev.filter(x => segna(x) && x.lato === 0).length, g1 = ev.filter(x => segna(x) && x.lato === 1).length;
    html += `<div class="tempo-testa"><span>${esc(T("tempo" + t))}</span><b>${g0} - ${g1}</b></div>`;
    html += ev.length ? ev.map(x => {
      const nota = { rigore: T("rig"), autogol: T("aut"), rig_sbagliato: T("rigSbagliato") }[x.tipo];
      const testo = `<span class="ev-chi"><b>${esc(x.chi)}</b>${x.altro ? ` <span class="ev-altro">${esc(x.altro)}</span>` : ""}${nota ? ` <span class="ev-altro">(${esc(nota)})</span>` : ""}</span>`;
      return `<div class="ev lato-${x.lato}"><span class="ev-min">${esc(x.min)}</span>${ICONE[x.tipo] || ""}${testo}</div>`;
    }).join("") : `<div class="ev-vuoto">–</div>`;
  }
  return html;
}
function statsHTML(e) {
  if (!e.stats?.length) return `<p class="p-nota">${esc(T("statsVuote"))}</p>`;
  return e.stats.map(([k, a, b]) => {
    const pct = k === "possessionPct", va = parseFloat(a) || 0, vb = parseFloat(b) || 0, tot = va + vb || 1;
    const fa = pct ? `${Math.round(va)}%` : a, fb = pct ? `${Math.round(vb)}%` : b;
    return `<div class="stat"><div class="stat-num"><b class="${va > vb ? "piu" : ""}">${esc(fa)}</b><span>${esc(STAT_NOMI[lingua][k] || k)}</span><b class="${vb > va ? "piu" : ""}">${esc(fb)}</b></div>
      <div class="stat-barre"><i class="sx" style="width:${va / tot * 100}%"></i><i class="dx" style="width:${vb / tot * 100}%"></i></div></div>`;
  }).join("");
}
function formazioniHTML(e) {
  const f = e.formazioni;
  if (!f) return `<p class="p-nota">${esc(T("formVuote"))}</p>`;
  const col = (x, nome) => !x?.titolari ? "" : `<div class="form-col"><div class="form-nome">${esc(tr(nome))}${x.modulo ? ` <span>${esc(x.modulo)}</span>` : ""}</div>
    ${x.titolari.map(g => `<div class="gioc"><span class="num">${esc(g[0])}</span>${esc(g[1])}<span class="ruolo">${esc(g[2])}</span></div>`).join("")}
    ${x.panchina?.length ? `<div class="form-sub">${esc(T("panchina"))}</div>` + x.panchina.map(g => `<div class="gioc panca${g[3] ? " entrato" : ""}"><span class="num">${esc(g[0])}</span>${esc(g[1])}</div>`).join("") : ""}</div>`;
  return `<div class="form">${col(f[0], e.squadre[0])}${col(f[1], e.squadre[1])}</div>`;
}

function apriPartita(id) {
  const e = EVENTI.find(x => x.id === id); if (!e) return;
  if (partitaAperta !== id) schedaPartita = "riassunto";
  partitaAperta = id;
  const ora = new Date(), live = inOnda(e, ora), fine = e.fine < ora, l = e.live || {}, s = SPORT[e.sport];
  const due = e.squadre?.length === 2 && !MOTORI.includes(e.sport);
  const d = e.inizio;
  const stato = live ? `<span class="p-stato live">${esc(l.minuto || l.fase || "LIVE")}</span>`
    : fine ? `<span class="p-stato">${esc(T("terminato"))}</span>` : `<span class="p-stato">${esc(relativo(d, ora) || fBreveData(d))} · ${fOra(d)}</span>`;
  const tv = `<div class="p-dove"><span class="p-dove-tit">📺 ${esc(T("dove"))}</span><span>${pezziCanale(e.canale).map(c => {
      const free = /\(gratis\)/i.test(c);
      return `<span class="${free ? "free" : ""}">${esc(tr(c.replace(/\s*\(gratis\)/i, "")))}${free ? ` <small>${esc(T("gratis"))}</small>` : ""}</span>`;
    }).join('<span class="sep"> · </span>') || "—"}</span></div>`;
  let centro = "";
  if (due) {
    const punti = puntiPerLato(e, ora);
    const risultato = punti ? (e.sport === "tennis"
        ? `<div class="p-set">${punti[0].split(" ").map((a, i) => `<span><b>${esc(a)}</b><b>${esc(punti[1].split(" ")[i] || "")}</b></span>`).join("")}</div>`
        : `<div class="p-ris${live ? " live" : ""}">${esc(punti[0])}<span>–</span>${esc(punti[1])}</div>`)
      : `<div class="p-ris vs">${fine ? "–" : fOra(d)}</div>`;
    centro = `<div class="p-tabellone">
        <button class="p-squadra" data-squadra="${esc(e.squadre[0])}">${stemma(e, 0, e.squadre[0])}<span>${esc(tr(e.squadre[0]))}</span></button>
        <div class="p-centro">${risultato}${stato}</div>
        <button class="p-squadra" data-squadra="${esc(e.squadre[1])}">${stemma(e, 1, e.squadre[1])}<span>${esc(tr(e.squadre[1]))}</span></button>
      </div>${tv}`;
    if (e.sport === "calcio") {
      const schede = [["riassunto", T("riassunto")], ["statistiche", T("statistiche")], ["formazioni", T("formazioni")]];
      centro += `<div class="p-schede">${schede.map(([k, n]) => `<button class="p-scheda${schedaPartita === k ? " on" : ""}" data-scheda="${k}">${esc(n)}</button>`).join("")}</div>
        <div class="p-contenuto">${schedaPartita === "statistiche" ? statsHTML(e) : schedaPartita === "formazioni" ? formazioniHTML(e) : riassuntoHTML(e, ora)}</div>`;
    }
  } else {
    let info = "";
    if (live && l.giro) info = `<div class="p-grande live">${esc(T("giro"))} ${l.giro}<small>/${l.giri}</small></div><div class="barra-giri"><i style="width:${Math.round(l.giro / l.giri * 100)}%"></i></div>`;
    else if (live && l.fase) info = `<div class="p-grande live">${esc(l.fase)}</div>${l.fineFase ? `<div class="p-nota">${esc(T("finisceTra"))} <b data-fine-fase="${l.fineFase.getTime()}">${mmss(l.fineFase - ora)}</b></div>` : ""}`;
    centro = `<div class="p-motori"><div class="p-sessione">${esc(tr(e.riga))}</div>${info || stato}</div>${tv}`;
    if (e.classifica?.length) {
      const qual = /qualif/i.test(e.riga);
      centro += `<h4>🏁 ${esc(T(qual ? "griglia" : "classifica"))}</h4><div class="classifica">
        <div class="cl-riga cl-testa"><span>${esc(T("pos"))}</span><span></span><span>${esc(T("pilota"))}</span><span>${esc(T(qual ? "tempoMigliore" : "tempo"))}</span></div>
        ${e.classifica.map((x, i) => `<div class="cl-riga${i < 3 ? " podio-" + (i + 1) : ""}">
          <span class="cl-pos">${esc(x[0])}</span><span class="band emoji">${bandiera(x[2])}</span>
          <span class="cl-pil"><b>${esc(x[1])}</b><small>${esc(x[3])}</small></span>
          <span class="cl-tempo">${x[4] ? `<b>${esc(x[4])}</b>` : ""}${x[5] ? `<small>${esc(tr(x[5]))}</small>` : ""}</span></div>`).join("")}
      </div>`;
    } else if (fine) centro += `<p class="p-nota">${esc(T("classificaNd"))}</p>`;
  }
  document.getElementById("p-testa").innerHTML = `<span class="g-ico emoji" style="--c:${s.colore}">${s.emoji}</span>
    <span><b>${esc(tr(e.gruppo))}</b><small>${esc(maiusc(fGiorno(d)))} · ${fOra(d)}${e.turno ? " · " + esc(tr(e.turno)) : ""}</small></span>`;
  document.getElementById("p-corpo").innerHTML = centro +
    (!fine && !live ? `<a class="btn primario p-avvisa" href="eventi/${e.id}.ics">🔔 ${esc(T("avvisami"))}</a>` : "");
  document.getElementById("pannello-partita").hidden = false;
  document.getElementById("velo").hidden = false;
}
function chiudiPartita() {
  document.getElementById("pannello-partita").hidden = true;
  document.getElementById("velo").hidden = true;
  partitaAperta = null;
}
document.getElementById("chiudi-partita").addEventListener("click", chiudiPartita);
document.getElementById("p-corpo").addEventListener("click", ev => {
  const sc = ev.target.closest("[data-scheda]"); if (sc) { schedaPartita = sc.dataset.scheda; return apriPartita(partitaAperta); }
  const sq = ev.target.closest("[data-squadra]"); if (sq) { chiudiPartita(); apriSquadra(sq.dataset.squadra); }
});

/* Pannello filtri */
function disegnaPannello() {
  const miei = eventiMiei();
  document.getElementById("f-sport").innerHTML = ORDINE.filter(k => miei.some(e => e.sport === k)).map(k =>
    `<button class="lega${bozzaFiltri.sport.includes(k) ? " on" : ""}" data-sport="${k}" style="--c:${SPORT[k].colore}">${SPORT[k].emoji} ${esc(nomeSport(k))}</button>`).join("");
  const leghe = [...new Set(miei.filter(e => !bozzaFiltri.sport.length || bozzaFiltri.sport.includes(e.sport)).map(e => e.lega))];
  bozzaFiltri.leghe = bozzaFiltri.leghe.filter(l => leghe.includes(l));
  document.getElementById("f-leghe").innerHTML = leghe.map(l => {
    const s = SPORT[miei.find(e => e.lega === l).sport];
    return `<button class="lega${bozzaFiltri.leghe.includes(l) ? " on" : ""}" data-lega="${esc(l)}" style="--c:${s.colore}">${esc(tr(l))}</button>`;
  }).join("") || `<span class="riassunto">${esc(T("nessuna"))}</span>`;
  document.getElementById("solo-cuore").classList.toggle("on", bozzaFiltri.soloCuore);
  document.getElementById("applica").textContent = T("mostra", miei.filter(e => passaFiltri(e, bozzaFiltri)).length);
}
function pannello(aperto) {
  document.getElementById("pannello").hidden = !aperto;
  document.getElementById("velo").hidden = !aperto;
  if (aperto) { bozzaFiltri = JSON.parse(JSON.stringify(filtri)); disegnaPannello(); }
}
document.getElementById("velo").addEventListener("click", () => { pannello(false); pannelloCal(false); chiudiSquadra(); chiudiPartita(); });
document.getElementById("pannello").addEventListener("click", ev => {
  const s = ev.target.closest("[data-sport]"), l = ev.target.closest("[data-lega]");
  const alterna = (lista, v) => lista.includes(v) ? lista.splice(lista.indexOf(v), 1) : lista.push(v);
  if (s) { alterna(bozzaFiltri.sport, s.dataset.sport); disegnaPannello(); }
  else if (l) { alterna(bozzaFiltri.leghe, l.dataset.lega); disegnaPannello(); }
  else if (ev.target.closest("#solo-cuore")) { bozzaFiltri.soloCuore = !bozzaFiltri.soloCuore; disegnaPannello(); }
  else if (ev.target.id === "azzera") { bozzaFiltri = { ...filtriVuoti(), giorno: filtri.giorno }; disegnaPannello(); }
  else if (ev.target.id === "applica") { filtri = bozzaFiltri; pannello(false); disegna(); }
});

/* ================= Calendario personalizzato ================= */
function rigaCal(emoji, nome, sotto, file) {
  return `<div class="riga-cal"><span class="emoji">${emoji}</span>
    <div class="nome">${esc(nome)}${sotto && sotto !== nome ? `<small>${esc(sotto)}</small>` : ""}</div>
    <a class="btn-iscr" href="${esc(linkCal(file))}">${esc(T("iscr"))}</a></div>`;
}
function disegnaCal() {
  const p = prefsCorrenti() || { sport: [], leghe: {}, squadre: [] };
  document.getElementById("cal-spiega").textContent = T("calSpiega", {{PROMEMORIA}});
  let html = "";
  if (p.squadre.length) html += `<h4>${esc(T("calCuore"))}</h4>` +
    p.squadre.map(q => rigaCal("⭐", q, T("calSub"), `cal/squadra-${slug(q)}.ics`)).join("");
  const leghe = ORDINE.filter(k => p.sport.includes(k)).flatMap(k => (p.leghe[k] || SPORT[k].leghe).map(l => [k, l]));
  if (leghe.length) html += `<h4>${esc(T("calLeghe"))}</h4>` +
    leghe.map(([k, l]) => rigaCal(SPORT[k].emoji, tr(l), nomeSport(k), `cal/lega-${slug(l)}.ics`)).join("");
  html += `<h4>${esc(T("calTutto"))}</h4>` + rigaCal("📺", T("calTuttoNome"), T("calTuttoSub"), "sport.ics");
  document.getElementById("cal-righe").innerHTML = html;
  document.getElementById("cal-nota").innerHTML = T("calNota") + (ANTEPRIMA ? "<br><br>" + T("calAnteprima") : "");
}
function pannelloCal(aperto) {
  document.getElementById("pannello-cal").hidden = !aperto;
  document.getElementById("velo").hidden = !aperto;
  if (aperto) disegnaCal();
}
document.getElementById("apri-cal").addEventListener("click", () => pannelloCal(true));
document.getElementById("chiudi-cal").addEventListener("click", () => pannelloCal(false));

/* ================= Disegno ================= */
function disegna() {
  const ora = new Date();
  document.querySelector(".sezioni .interno").dataset.attiva = sezione;
  document.querySelectorAll(".sezioni button").forEach(b => b.classList.toggle("on", b.dataset.sezione === sezione));
  document.getElementById("n-oggi").textContent = eventiOggi(ora).filter(e => e.fine >= ora).length;
  document.getElementById("n-miei").textContent = eventiMiei().filter(e => e.fine >= ora).length;
  document.getElementById("v-oggi").hidden = sezione !== "oggi";
  document.getElementById("v-miei").hidden = sezione !== "miei";
  sezione === "oggi" ? disegnaOggi(ora) : disegnaMiei(ora);
}
document.querySelector(".sezioni").addEventListener("click", ev => {
  const b = ev.target.closest("button[data-sezione]"); if (b) { sezione = b.dataset.sezione; disegna(); window.scrollTo(0, 0); }
});

applicaTesti();
apri(!sessione() ? "accesso" : !prefsCorrenti() ? "pref" : "home");
setInterval(() => { if (schermoAttuale === "home") { disegna(); if (partitaAperta) apriPartita(partitaAperta); } }, 30000);
</script>
</body>
</html>
"""


def scrivi_calendari(out, eventi, adesso):
    """Un calendario per ogni competizione e per ogni squadra/giocatore: la pagina
    propone a ciascuno solo quelli dei suoi preferiti (docs/cal/lega-*.ics, squadra-*.ics)."""
    cartella = out / "cal"
    shutil.rmtree(cartella, ignore_errors=True)
    cartella.mkdir(parents=True, exist_ok=True)
    leghe = {l for k in SPORT for l in SPORT[k]["leghe"]} | {e["lega"] for e in eventi}
    for l in leghe:
        sel = [e for e in eventi if e["lega"] == l]
        (cartella / f"lega-{slug(l)}.ics").write_text(ics_calendario(sel, adesso, f"Sport in TV · {l}"),
                                                      encoding="utf-8", newline="")
    squadre = set(SQUADRE_NOTE) | set(TENNISTI) | {q for e in eventi for q in e["squadre"]}
    for q in squadre:
        nq = slug(q).replace("-", " ")
        sel = [e for e in eventi if any(nq in slug(x).replace("-", " ") for x in [e["titolo"], *e["squadre"]])]
        (cartella / f"squadra-{slug(q)}.ics").write_text(ics_calendario(sel, adesso, f"Sport in TV · {q}"),
                                                         encoding="utf-8", newline="")


# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--giorni", type=int, default=7, help="quanti giorni in avanti")
    parser.add_argument("--out", default="docs", help="cartella di output")
    parser.add_argument("--extra", default="extra.json", help="file con gli eventi aggiunti a mano")
    parser.add_argument("--passati", type=int, default=PASSATI, help="quanti giorni passati tenere (con i risultati)")
    args = parser.parse_args()

    adesso = datetime.now(timezone.utc)
    oggi = adesso.astimezone(TZ).date()
    # da mezzanotte di oggi: gli eventi già finiti restano visibili fino a fine giornata, con il risultato
    inizio = datetime.combine(oggi - timedelta(days=args.passati), datetime.min.time(), TZ).astimezone(timezone.utc)
    fine = adesso + timedelta(days=args.giorni)

    grezzi = []
    for cfg in COMPETIZIONI:
        if cfg.get("jolpica"):  # F1: Jolpica è la fonte principale, ESPN solo se non risponde
            f1 = da_jolpica(cfg, inizio, fine)
            grezzi += f1 if f1 or ERRORI.get("jolpica") is None else da_espn(cfg, inizio.astimezone(TZ), fine.astimezone(TZ))
            continue
        errori_prima = ERRORI.get("espn_irraggiungibile", 0)
        trovati = da_espn(cfg, inizio.astimezone(TZ), fine.astimezone(TZ))
        if not trovati and ERRORI.get("espn_irraggiungibile", 0) > errori_prima and cfg.get("fd"):
            print(f"[info] ESPN non raggiungibile per {cfg['nome']}: uso FixtureDownload")
            trovati = da_fixturedownload(cfg, inizio, fine)
        grezzi += trovati
    grezzi += da_motogp(inizio, fine)
    grezzi += da_extra(args.extra)

    visti, eventi = set(), []
    for e in sorted(grezzi, key=lambda e: (e["inizio"], list(SPORT).index(e["sport"]), e["titolo"])):
        if inizio <= e["inizio"] <= fine and e["uid"] not in visti:
            visti.add(e["uid"])
            eventi.append(e)

    out = Path(args.out)
    shutil.rmtree(out / "eventi", ignore_errors=True)
    (out / "eventi").mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(pagina(eventi, adesso), encoding="utf-8")
    (out / "sport.ics").write_text(ics_calendario(eventi, adesso), encoding="utf-8", newline="")
    for e in eventi:
        (out / "eventi" / f"{e['uid']}.ics").write_text(ics_calendario([e], adesso), encoding="utf-8", newline="")
    scrivi_calendari(out, eventi, adesso)
    (out / ".nojekyll").write_text("")
    per_sport = {}
    for e in eventi:
        per_sport[e["sport"]] = per_sport.get(e["sport"], 0) + 1
    print(f"Generati {len(eventi)} eventi in {out}/ · per sport: {per_sport}")
    if ERRORI:
        print(f"Richieste fallite per fonte: {ERRORI}")


if __name__ == "__main__":
    main()
