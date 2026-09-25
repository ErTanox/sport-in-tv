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
DEMO = False  # True solo per le anteprime con eventi inventati: gli orari seguono il momento in cui apri la pagina

# ---------------------------------------------------------------------------
# SPORT: ordine, emoji, nome, colore e competizioni tra cui l'utente può scegliere
# ---------------------------------------------------------------------------
SPORT = {
    "calcio": {"emoji": "⚽", "nome": "Calcio", "colore": "#22c55e",
               "leghe": ["Serie A", "Serie B", "Coppa Italia", "Champions League",
                         "Europa League", "Conference League", "Nations League"]},
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
    {"path": "soccer/ita.1", "nome": "Serie A", "sport": "calcio", "durata": 110,
     "canale": "DAZN (3 partite a turno anche Sky Go / NOW)"},
    {"path": "soccer/ita.2", "nome": "Serie B", "sport": "calcio", "durata": 110,
     "canale": "DAZN · Prime Video · LaB Channel"},
    {"path": "soccer/ita.coppa_italia", "nome": "Coppa Italia", "sport": "calcio", "durata": 110,
     "canale": "Mediaset Infinity (gratis)"},
    {"path": "soccer/uefa.champions", "nome": "Champions League", "sport": "calcio", "durata": 110,
     "canale": "Sky Go / NOW (1 partita a turno su Prime Video)"},
    {"path": "soccer/uefa.europa", "nome": "Europa League", "sport": "calcio", "durata": 110,
     "canale": "Sky Go / NOW", "solo_squadre": SQUADRE_ITALIANE},
    {"path": "soccer/uefa.europa.conf", "nome": "Conference League", "sport": "calcio", "durata": 110,
     "canale": "Sky Go / NOW", "solo_squadre": SQUADRE_ITALIANE},
    {"path": "soccer/uefa.nations", "nome": "Nations League", "sport": "calcio", "durata": 110,
     "canale": "Sky Go / NOW o Mediaset Infinity", "solo_squadre": NAZIONALI_TOP,
     "canale_se": {"Italy": "RaiPlay (gratis) · Rai\u00a01"}},
    {"path": "racing/f1", "nome": "Formula 1", "sport": "f1", "durata": 120,
     "canale": "Sky Go / NOW · TV8 in differita"},
    {"path": "tennis/atp", "nome": "ATP", "sport": "tennis", "durata": 120,
     "canale": "Sky Go / NOW o SuperTennix"},
    {"path": "tennis/wta", "nome": "WTA", "sport": "tennis", "durata": 110,
     "canale": "Sky Go / NOW o SuperTennix"},
    {"path": "basketball/nba", "nome": "NBA", "sport": "basket", "durata": 150,
     "canale": "Sky Go / NOW"},
]

MOTOGP_CANALE = "Sky Go / NOW · TV8 in differita"
# Sessioni MotoGP da includere: sigla ufficiale -> (nome, durata in minuti)
MOTOGP_SESSIONI = {"FP1": ("Prove libere 1", 45), "PR": ("Practice", 60), "FP2": ("Prove libere 2", 30),
                   "Q1": ("Qualifiche 1", 15), "Q2": ("Qualifiche 2", 15), "SPR": ("Sprint", 30), "RAC": ("Gara", 45)}
# Sessioni F1 da includere (prove libere escluse)
SESSIONI_F1 = {"qual": ("Qualifiche", 60), "sprint": ("Sprint", 45), "race": ("Gara", 120)}

TRADUZIONI = {
    "Italy": "Italia", "Spain": "Spagna", "France": "Francia", "England": "Inghilterra",
    "Germany": "Germania", "Belgium": "Belgio", "Croatia": "Croazia",
    "Netherlands": "Olanda", "Turkey": "Turchia", "Türkiye": "Turchia", "Portugal": "Portogallo",
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
def scarica(url):
    req = urllib.request.Request(url, headers={"User-Agent": "sport-in-tv/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.load(r)
    except Exception as e:  # una fonte giù non deve bloccare tutta la pagina
        print(f"[avviso] {url}: {e}")
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
    "in differita": "delayed", "3 partite a turno anche": "3 matches per round also on",
    "1 partita a turno su": "1 match per round on", "Serie A1 Femminile": "Women's Serie A1",
    "Serie A Basket": "Italian Serie A (basket)",
    # nomi propri che non vanno tradotti
    "Coppa Italia": "Coppa Italia", "Rai Sport": "Rai Sport", "Italia 1": "Italia 1",
}


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


def evento(sport, inizio, durata, titolo, competizione, canale, uid, lega=None, squadre=(), risultato=None, live=None):
    """lega = competizione per i filtri delle preferenze; squadre = per la squadra del cuore."""
    return {"sport": sport, "inizio": inizio, "fine": inizio + timedelta(minutes=durata),
            "titolo": titolo, "competizione": competizione, "canale": canale, "uid": uid,
            "lega": lega or competizione.split(" · ")[0], "squadre": [q for q in squadre if q],
            "risultato": risultato, "live": live}


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
def da_espn(cfg, inizio, fine):
    url = f"{ESPN}/{cfg['path']}/scoreboard?dates={inizio:%Y%m%d}-{fine:%Y%m%d}&limit=300"
    dati = scarica(url)
    risultati = []
    for ev in dati.get("events", []):
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
                                            uid_per(cfg["path"], ev.get("id"), sess.get("id", nome)), cfg["nome"]))
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
                    turno_en = m.get("round", {}).get("displayName", "")
                    turno = TURNI.get(turno_en.lower().rstrip("s"), turno_en)
                    importante = turno_en.lower().rstrip("s") in ("final", "semifinal", "semi-final")
                    if not (contiene(giocatori, TENNISTI) or importante):
                        continue
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
                                            giocatori, ris))
            continue

        # Partite a squadre (calcio, basket)
        comp = (ev.get("competitions") or [{}])[0]
        casa = ospite = gol_casa = gol_ospite = None
        for c in comp.get("competitors", []):
            nome = c.get("team", {}).get("displayName")
            if c.get("homeAway") == "away":
                ospite, gol_ospite = nome, c.get("score")
            else:
                casa, gol_casa = nome, c.get("score")
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
        risultati.append(evento(cfg["sport"], parse_data(ev["date"]), cfg["durata"], titolo,
                                cfg["nome"], canale, uid_per(cfg["path"], ev.get("id", titolo)), cfg["nome"],
                                [it(casa), it(ospite)], ris))
    return risultati


def da_motogp(inizio, fine):
    dati = scarica(f"{MOTOGP}/events?seasonYear={inizio.year}&isFinished=false")
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
                                    f"MotoGP · {nome}", MOTOGP_CANALE, uid_per("motogp", ev.get("id"), b.get("shortname"))))
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
            risultati.append(evento(sport, inizio, int(v.get("durata", 90)), v["titolo"],
                                    v.get("competizione", SPORT[sport]["nome"]), v.get("canale", ""),
                                    lega=v.get("lega"), squadre=v.get("squadre", []), live=v.get("live"), uid=
                                    uid_per("extra", v["titolo"], v["inizio"])))
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
    display: flex; align-items: center; gap: 14px; margin: 8px 0 4px; padding: 15px 16px;
    border-radius: 20px; border: 1px solid var(--bordo);
    background: radial-gradient(130% 150% at 0% 0%, color-mix(in srgb, var(--c) 30%, transparent), transparent 62%), var(--superficie);
  }
  .hero .icona { width: 54px; height: 54px; font-size: 30px; border-radius: 17px; }
  .hero .testo { flex: 1; min-width: 0; }
  .hero .etichetta { font-size: 10.5px; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; color: var(--c); }
  .hero .tit { font-size: 19px; font-weight: 800; letter-spacing: -0.02em; line-height: 1.2; margin: 2px 0 1px; }
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
  .quadro.tutti { width: auto; padding: 0 11px; font-size: 12.5px; font-weight: 800; color: var(--tenue); }
  .quadro.tutti.on { color: var(--testo); }
  .quadro.fil { width: auto; gap: 6px; padding: 0 11px; display: inline-flex; font-size: 13px; font-weight: 800; color: var(--testo); margin-left: auto; }
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
      <div class="striscia" id="striscia"></div>
      <div class="quadri" id="sport-miei"></div>
      <div class="riassunto" id="riassunto" hidden></div>
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

/* ================= Card ================= */
function canali(testo) {
  return testo.split(/\s+·\s+|\s+o\s+/).filter(Boolean).map(c => {
    const free = /\(gratis\)/i.test(c);
    return `<li>${esc(tr(c.replace(/\s*\(gratis\)/i, "")))}${free ? ` <span class="free">${esc(T("gratis"))}</span>` : ""}</li>`;
  }).join("");
}
const mmss = ms => { const t = Math.max(0, Math.round(ms / 1000)); return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`; };
function liveRiga(e, ora) {
  const l = e.live;
  if (!l || e.inizio > ora || e.fine < ora) return "";
  if (l.giro) {  // gara: giro attuale su totale
    const pct = Math.min(100, Math.round(l.giro / l.giri * 100));
    return `<div class="live-riga giri"><span class="num">${esc(T("giro"))} ${l.giro}<small>/${l.giri}</small></span>
      <span class="barra-giri" role="progressbar" aria-valuenow="${l.giro}" aria-valuemax="${l.giri}"><i style="width:${pct}%"></i></span></div>`;
  }
  if (l.fase) {  // qualifiche Q1-Q3 o prove P1-P3, con conto alla rovescia
    return `<div class="live-riga"><span class="fase">${esc(l.fase)}</span>
      ${l.fineFase ? `<span class="conto" title="${esc(T("finisceTra"))}" aria-label="${esc(T("finisceTra"))}">⏱ <b data-fine-fase="${l.fineFase.getTime()}">${mmss(l.fineFase - ora)}</b></span>` : ""}</div>`;
  }
  if (l.punteggio) {  // calcio, tennis, basket, volley
    const tempo = l.minuto ? esc(l.minuto).replace(/'$/, '<span class="tick">\'</span>') : esc(tr(l.dettaglio || ""));
    return `<div class="live-riga"><span class="punteggio">${esc(l.punteggio)}</span><span class="minuto">${tempo}</span></div>`;
  }
  return "";
}
// Aggiorna ogni secondo solo i conti alla rovescia, senza ridisegnare la pagina
setInterval(() => {
  const ora = Date.now();
  document.querySelectorAll("[data-fine-fase]").forEach(el => {
    const resto = +el.dataset.fineFase - ora;
    el.textContent = resto > 0 ? mmss(resto) : T("inChiusura");
  });
}, 1000);

function card(e, ora) {
  const s = SPORT[e.sport], live = e.inizio <= ora && ora <= e.fine, cuore = delCuore(e), concluso = e.fine < ora;
  const destra = concluso ? `<span class="badge fine">${esc(T("finale"))}</span>`
    : live ? '<span class="badge live">LIVE</span>'
    : `<a class="avvisami emoji" href="eventi/${e.id}.ics" title="${esc(T("avvisami"))}" aria-label="${esc(T("avvisami"))}">🔔</a>`;
  return `
  <article class="card${live ? " in-corso" : ""}${cuore ? " cuore" : ""}${concluso ? " finito" : ""}" style="--c:${s.colore}">
    <div class="icona emoji" aria-label="${esc(nomeSport(e.sport))}">${s.emoji}</div>
    <div class="info">
      <div class="comp">${esc(tr(e.comp))}${cuore ? '<span class="stella">⭐</span>' : ""}</div>
      <h3>${esc(tr(e.titolo))}</h3>
      ${live ? liveRiga(e, ora) : ""}
      ${concluso ? `<span class="risultato">${esc(e.ris || T("terminato"))}</span>` : ""}
    </div>
    <div class="dove"><small>${esc(T("dove"))}</small><ul>${canali(e.canale)}</ul></div>
    <div class="lato">
      <div class="ora">${fOra(e.inizio)}</div>
      ${destra}
    </div>
  </article>`;
}
function quadriSport(lista, attivi, extra = "") {
  const tuttiOn = !attivi.length;
  return `<button class="quadro tutti${tuttiOn ? " on" : ""}" data-q="tutti">${esc(T("tutti"))}</button>` +
    ORDINE.filter(k => lista.some(e => e.sport === k)).map(k =>
      `<button class="quadro emoji${attivi.includes(k) ? " on" : ""}" data-q="${k}" style="--c:${SPORT[k].colore}" title="${esc(nomeSport(k))}" aria-label="${esc(nomeSport(k))}">${SPORT[k].emoji}<span class="n">${lista.filter(e => e.sport === k).length}</span></button>`).join("") + extra;
}
function mantieniScorrimento(el, html) {
  const x = el.scrollLeft; el.innerHTML = html; el.scrollLeft = x;
  const att = el.querySelector(".on:not(.tutti)");
  if (att && (att.offsetLeft < el.scrollLeft || att.offsetLeft + att.offsetWidth > el.scrollLeft + el.clientWidth)) el.scrollLeft = att.offsetLeft - 16;
}

/* ================= Oggi in TV ================= */
let sezione = "oggi", sportOggi = [];
function eventiOggi(ora) { return EVENTI.filter(e => chiave(e.inizio) === chiave(ora)); }
function disegnaOggi(ora) {
  const oggi = eventiOggi(ora);
  sportOggi = sportOggi.filter(k => oggi.some(e => e.sport === k));
  mantieniScorrimento(document.getElementById("sport-oggi"), quadriSport(oggi, sportOggi));
  const tuttiVis = oggi.filter(e => !sportOggi.length || sportOggi.includes(e.sport));
  const vis = tuttiVis.filter(e => e.fine >= ora), finiti = tuttiVis.filter(e => e.fine < ora);

  const hero = document.getElementById("hero"), p = vis[0];
  if (p) {
    const s = SPORT[p.sport], live = p.inizio <= ora;
    hero.hidden = false; hero.style.setProperty("--c", s.colore);
    hero.innerHTML = `
      <div class="icona emoji">${s.emoji}</div>
      <div class="testo">
        <div class="etichetta">${live ? T("inOnda") + (vis.filter(e => e.inizio <= ora).length > 1 ? ` · +${vis.filter(e => e.inizio <= ora).length - 1}` : "") : T("prossimo")}</div>
        <div class="tit">${esc(tr(p.titolo))}</div>
        <div class="meta">${esc(tr(p.comp))} · 📺 ${esc(tr(p.canale.split(/\s+·\s+|\s+o\s+/)[0].replace(/\s*\(gratis\)/i, "")))}</div>
        ${live ? liveRiga(p, ora) : ""}
      </div>
      <div class="quando"><div class="ora">${fOra(p.inizio)}</div><div class="tra">${live ? "LIVE" : T("oggi")}</div></div>`;
  } else hero.hidden = true;

  const FASCE = [["🌙", "notte", 0, 6], ["☀️", "mattina", 6, 13], ["🌤️", "pomeriggio", 13, 19], ["🌆", "sera", 19, 24]];
  let html = "";
  const inOnda = vis.filter(e => e.inizio <= ora);
  if (inOnda.length) html += `<div class="fascia live-ora"><span class="pallino-live"></span>${T("inOndaSez")} · ${inOnda.length}</div>${inOnda.map(e => card(e, ora)).join("")}`;
  for (const [emoji, nome, da, a] of FASCE) {
    const ev = vis.filter(e => e.inizio > ora && (() => { const h = oraRoma(e.inizio); return h >= da && h < a; })());
    if (ev.length) html += `<div class="fascia"><span class="emoji">${emoji}</span>${T(nome)}</div>${ev.map(e => card(e, ora)).join("")}`;
  }
  if (finiti.length) html += `<div class="fascia"><span class="emoji">✅</span>${T("finiti")}</div>${finiti.map(e => card(e, ora)).join("")}`;
  document.getElementById("lista-oggi").innerHTML = html || `<div class="vuoto"><span class="emoji">🛋️</span>${T("vuotoOggi")}</div>`;
}
document.getElementById("sport-oggi").addEventListener("click", ev => {
  const b = ev.target.closest(".quadro"); if (!b) return;
  const k = b.dataset.q;
  sportOggi = k === "tutti" ? [] : sportOggi.includes(k) ? sportOggi.filter(x => x !== k) : [...sportOggi, k];
  disegna();
});

/* ================= I miei eventi ================= */
const filtriVuoti = () => ({ giorno: "tutti", sport: [], leghe: [], soloCuore: false });
let filtri = filtriVuoti(), bozzaFiltri;
const passaFiltri = (e, f, conGiorno = true, conSport = true) =>
  (!conGiorno || f.giorno === "tutti" || chiave(e.inizio) === f.giorno) &&
  (!conSport || !f.sport.length || f.sport.includes(e.sport)) &&
  (!f.leghe.length || f.leghe.includes(e.lega)) &&
  (!f.soloCuore || delCuore(e));
const eventiMiei = ora => EVENTI.filter(e => (e.fine >= ora || chiave(e.inizio) === chiave(ora)) && interessa(e));

function disegnaMiei(ora) {
  const miei = eventiMiei(ora);
  const giorni = [...Array(7)].map((_, i) => new Date(ora.getTime() + i * 864e5));
  mantieniScorrimento(document.getElementById("striscia"),
    `<button class="giorno-btn tutti${filtri.giorno === "tutti" ? " on" : ""}" data-g="tutti"><span class="gs">${esc(T("tutti"))}</span><span class="gn emoji">🗓️</span><span class="punti"></span></button>` +
    giorni.map(d => {
      const k = chiave(d), ev = miei.filter(e => chiave(e.inizio) === k && passaFiltri(e, filtri, false));
      const colori = [...new Set(ev.map(e => SPORT[e.sport].colore))].slice(0, 4);
      return `<button class="giorno-btn${filtri.giorno === k ? " on" : ""}${ev.length ? "" : " vuoto-g"}" data-g="${k}">
        <span class="gs">${esc(chiave(d) === chiave(ora) ? T("oggi") : fSett(d))}</span><span class="gn">${fNum(d)}</span>
        <span class="punti">${colori.map(c => `<i style="--c:${c}"></i>`).join("")}</span></button>`;
    }).join(""));

  const nExtra = filtri.leghe.length + (filtri.soloCuore ? 1 : 0);
  const perGiorno = miei.filter(e => passaFiltri(e, filtri, true, false));
  const btnFiltri = `<span class="separa"></span><button class="quadro fil" id="apri-filtri"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/></svg>${esc(T("filtri"))}${nExtra ? `<span class="n">${nExtra}</span>` : ""}</button>`;
  mantieniScorrimento(document.getElementById("sport-miei"), quadriSport(perGiorno, filtri.sport, btnFiltri));

  const parti = [];
  if (filtri.soloCuore) parti.push(T("soloDelCuore"));
  filtri.leghe.forEach(l => parti.push(tr(l)));
  const rias = document.getElementById("riassunto");
  rias.hidden = !parti.length; rias.textContent = parti.join(" · ");

  const vis = miei.filter(e => passaFiltri(e, filtri));
  const gruppi = new Map();
  vis.forEach(e => { const k = chiave(e.inizio); gruppi.has(k) || gruppi.set(k, []); gruppi.get(k).push(e); });
  let html = "";
  gruppi.forEach(ev => {
    const d = ev[0].inizio, rel = relativo(d, ora);
    html += `<section><div class="giorno-tit"><b>${esc(rel || maiusc(fGiorno(d)))}</b>${rel ? `<span>${esc(fGiorno(d))}</span>` : ""}</div>
      ${ev.map(e => card(e, ora)).join("")}</section>`;
  });
  document.getElementById("lista-miei").innerHTML = html ||
    `<div class="vuoto"><span class="emoji">🗓️</span>${T("vuotoMiei")}<br><br>
     <button class="btn" style="max-width:240px;margin:0 auto" id="mostra-tutto">${esc(T("mostraTutto"))}</button></div>`;
}
document.getElementById("striscia").addEventListener("click", ev => {
  const b = ev.target.closest(".giorno-btn"); if (b) { filtri.giorno = b.dataset.g; disegna(); }
});
document.getElementById("v-miei").addEventListener("click", ev => {
  if (ev.target.closest("#apri-filtri")) return pannello(true);
  if (ev.target.closest("#mostra-tutto")) { filtri = filtriVuoti(); return disegna(); }
  const q = ev.target.closest("#sport-miei .quadro[data-q]"); if (!q) return;
  const k = q.dataset.q;
  filtri.sport = k === "tutti" ? [] : filtri.sport.includes(k) ? filtri.sport.filter(x => x !== k) : [...filtri.sport, k];
  disegna();
});

/* Pannello filtri */
function disegnaPannello() {
  const miei = eventiMiei(new Date());
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
document.getElementById("velo").addEventListener("click", () => { pannello(false); pannelloCal(false); });
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
  document.getElementById("n-miei").textContent = eventiMiei(ora).length;
  document.getElementById("v-oggi").hidden = sezione !== "oggi";
  document.getElementById("v-miei").hidden = sezione !== "miei";
  sezione === "oggi" ? disegnaOggi(ora) : disegnaMiei(ora);
}
document.querySelector(".sezioni").addEventListener("click", ev => {
  const b = ev.target.closest("button[data-sezione]"); if (b) { sezione = b.dataset.sezione; disegna(); window.scrollTo(0, 0); }
});

applicaTesti();
apri(!sessione() ? "accesso" : !prefsCorrenti() ? "pref" : "home");
setInterval(() => { if (schermoAttuale === "home") disegna(); }, 30000);
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
    args = parser.parse_args()

    adesso = datetime.now(timezone.utc)
    oggi = adesso.astimezone(TZ).date()
    # da mezzanotte di oggi: gli eventi già finiti restano visibili fino a fine giornata, con il risultato
    inizio = datetime.combine(oggi, datetime.min.time(), TZ).astimezone(timezone.utc)
    fine = adesso + timedelta(days=args.giorni)

    grezzi = []
    for cfg in COMPETIZIONI:
        grezzi += da_espn(cfg, inizio.astimezone(TZ), fine.astimezone(TZ))
    grezzi += da_motogp(inizio, fine)
    grezzi += da_extra(args.extra)

    visti, eventi = set(), []
    for e in sorted(grezzi, key=lambda e: (e["inizio"], list(SPORT).index(e["sport"]), e["titolo"])):
        di_oggi = e["inizio"].astimezone(TZ).date() == oggi
        if (e["fine"] >= adesso or di_oggi) and e["inizio"] <= fine and e["uid"] not in visti:
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
    print(f"Generati {len(eventi)} eventi in {out}/")


if __name__ == "__main__":
    main()
