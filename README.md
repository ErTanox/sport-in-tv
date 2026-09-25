# Sport in TV

La tua pagina degli eventi sportivi: cosa c'è oggi in TV e i tuoi eventi della settimana,
con orario italiano e dove vederli. Si apre da PC e iPhone, gli avvisi arrivano dal
calendario del telefono.

## Cosa fa

- **Oggi in TV**: tutti gli eventi di oggi, divisi per fasce orarie, con quelli in onda
  in cima e quelli già finiti in fondo con il risultato.
- **I miei eventi**: la settimana filtrata sui tuoi preferiti (sport, competizioni,
  squadre del cuore ⭐), con striscia dei giorni e filtri.
- **📅 Calendario personale**: ti iscrivi solo a quello che segui (es. "Palermo", "Serie B",
  "Formula 1"). Il calendario si aggiorna da solo e avvisa 30 minuti prima.
- **🔔** su ogni evento: aggiunge al calendario solo quell'evento.
- Tema chiaro/scuro (☀️/🌙), italiano/inglese (IT/EN).

## File del progetto

| File | A cosa serve |
|---|---|
| `sport_bot.py` | Scarica gli eventi e genera pagina e calendari nella cartella `docs` |
| `extra.json` | Eventi aggiunti a mano (Superbike, volley, basket italiano…) |
| `.github/workflows/sport-bot.yml` | Fa girare lo script da solo su GitHub |
| `docs/` | Creata dallo script: è il sito pubblicato. Non modificarla a mano |

## Aggiornamenti automatici

GitHub fa girare lo script:
- ogni mattina alle 7 (6 d'inverno);
- ogni ora dalle 13 a mezzanotte, per avere i risultati aggiornati;
- subito, ogni volta che modifichi `extra.json` o `sport_bot.py`;
- quando vuoi, da **Actions → Sport in TV → Run workflow**.

## Da dove arrivano gli eventi

| Sport | Fonte | Cosa include |
|---|---|---|
| ⚽ Calcio | ESPN (automatico) | Serie A, Serie B, Coppa Italia, Champions; Europa e Conference solo con italiane; Nations League delle big |
| 🏎️ F1 | ESPN (automatico) | Prove libere, qualifiche, sprint, gara |
| 🏍️ MotoGP | API ufficiale MotoGP (automatico) | Prove, qualifiche, sprint, gara |
| 🎾 Tennis | ESPN (automatico) | Partite degli italiani + semifinali e finali ATP/WTA, appena esce l'orario (di solito il giorno prima) |
| 🏀 Basket | ESPN (automatico) | NBA |
| 🏁 Superbike, 🏐 Volley, basket italiano | `extra.json` (a mano) | Quello che aggiungi tu |

### Aggiungere eventi a mano

Su GitHub apri `extra.json` → matita ✏️ → aggiungi una riga → **Commit changes**.
Orari in ora italiana. Gli eventi passati puoi lasciarli: vengono ignorati da soli.

```json
[
  {"sport": "sbk", "titolo": "Round di Cremona", "competizione": "Superbike · Gara 1", "inizio": "2026-09-26 15:30", "durata": 40, "canale": "TV8 (gratis) · Sky Go / NOW"},
  {"sport": "volley", "titolo": "Perugia – Trento", "competizione": "SuperLega", "inizio": "2026-10-11 18:00", "durata": 120, "canale": "Rai Sport (gratis) · VBTV"}
]
```

- Sport validi: `calcio`, `f1`, `motogp`, `sbk`, `tennis`, `basket`, `volley`.
- La parte prima di ` · ` in `competizione` è la competizione usata dai filtri (es. `Superbike`, `SuperLega`).
- Nel canale separa le piattaforme con ` · `. Scrivere `(gratis)` fa comparire la scritta verde "gratis".
- Attenzione alle virgole: ogni riga tranne l'ultima finisce con `,`.

## Personalizzare `sport_bot.py`

- **Canali**: lista `COMPETIZIONI`. Controllali a inizio stagione: i diritti TV cambiano.
- **Squadre suggerite nella ricerca**: lista `SQUADRE_NOTE`.
- **Tennisti seguiti**: lista `TENNISTI`.
- **Colori, emoji, competizioni per sport**: dizionario `SPORT`.
- **Minuti di preavviso**: `PROMEMORIA_MINUTI`.

## Sull'iPhone

1. Apri la pagina in Safari → Condividi → **Aggiungi alla schermata Home**.
2. Tocca 📅 e iscriviti ai calendari che ti interessano.
3. Poi **Impostazioni → Calendario → Account → calendario scelto** e disattiva
   **"Rimuovi avvisi"**, altrimenti iOS toglie i promemoria. Imposta anche "Aggiorna" su "Ogni ora".

## Limiti da sapere

- **Account**: per ora account e preferenze restano sul dispositivo dove li crei.
  Il login Google e la sincronizzazione tra dispositivi arriveranno con Firebase.
- **Password**: il sistema è semplice, non usare la stessa password di altri servizi.
- **Superbike e volley** non hanno una fonte gratuita affidabile: vanno in `extra.json`.
- **Tennis**: le partite compaiono quando esce l'ordine di gioco, di solito il giorno prima.
- **Risultati**: arrivano all'aggiornamento orario successivo alla fine dell'evento.
- Le fonti ESPN e MotoGP non sono servizi ufficiali: possono cambiare senza preavviso.
