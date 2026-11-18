# Architektur & Fahrplan

## Idee

Jede Person der Familie bekommt täglich ihre eigene Zeitung. Ein „Reporter“ sammelt Nachrichten aus vielen
Quellen, lädt die vollständigen Artikel nach, verfolgt Geschichten über mehrere Tage und schreibt daraus eine
gesetzte Ausgabe im persönlichen Zeitungsstil. Gelesen wird auf Smartphone und iPad (PDF oder HTML-Fassung),
auf Wunsch auch ausgedruckt.

## Rahmenbedingungen

| Thema | Entscheidung |
|---|---|
| Betrieb | Docker Compose auf einem Raspberry Pi (arm64, 8 GB RAM, openmediavault 8). Der Pi ist bereits ausgelastet (Load ≈ 3): sparsam bleiben. Auf dem Pi laufen **keine** Modelle. |
| KI | **Jetson Orin Nano 8 GB** mit **llama.cpp** (`llama-server`, Router-Modus, ein Port): Sprachmodell **Qwen3.5-9B** (IQ4_XS, `qwen3.5-9b`), Embeddings **EmbeddingGemma** (`embeddinggemma`). Zum Ausprobieren optional **captiva** (vLLM, Qwen3.8 27B); captiva zieht mit der 32-GB-Karte rund 800 W und läuft deshalb nicht dauerhaft. Für Entwicklung und Vorführung gibt es einen **Simulator** ohne GPU. |
| Zugriff | Nur Heimnetz. Optional eine Haushalts-PIN für die Weboberfläche. |
| Leser | 6 Personen, jede mit eigenen Interessen, eigenem Stil, eigener Zustellzeit, eigenen Wochentagen und eigenem Kanal. |
| Code & Images | GitHub (`eilkurier-ng`), CircleCI, Docker Hub öffentlich (`hablijack/eilkurier-ng`, arm64 + amd64). |
| Standards | API-first (OpenAPI, typisierter Client daraus generiert), zustandslose Container (12-Factor, Konfiguration per Umgebung, Root-FS schreibgeschützt), I18n (de/en in Web und Druck), A11y (WCAG 2.2 AA im Web, PDF/UA-1 im Druck), Mobile-First für die Weboberfläche. |

## Komponenten

```
                    ┌──────────────── Raspberry Pi (docker compose) ────────────────┐
  Quellen ────────▶ │  worker   Sammeln → Volltext → Reporter → Ausgaben setzen →    │
  (RSS, ICS,        │           Zustellen  (+ Telegram-Bot: Verknüpfen, Leserbriefe) │ ──▶ Telegram / E-Mail
   Wetter, …)       │     │                         ▲                                │
                    │     ▼                         │ OpenAI-kompatible API          │
                    │  postgres + pgvector          │                                │
                    │     ▲                         │                                │
                    │  app   REST-API (FastAPI) + Weboberfläche (SvelteKit, statisch)│ ◀── Smartphone / iPad
                    │  migrate  (einmalig beim Start)                                │
                    └───────────────────────────────┼────────────────────────────────┘
                                                    ▼ (wenn erreichbar)
                     Jetson: llama.cpp, Qwen3.5-9B + EmbeddingGemma
                     (zum Ausprobieren: captiva/vLLM · Entwicklung: Simulator)
```

- **app**, **worker** und **migrate** nutzen dasselbe Image mit unterschiedlichem Startbefehl. Sie halten
  keinen Zustand: Alles Veränderliche liegt in Postgres, auch die fertigen PDFs.
- **postgres + pgvector** ist der einzige Speicher: Stammdaten, Artikel, Embeddings und die Arbeitswarteschlange
  (Statusspalten + `SELECT … FOR UPDATE SKIP LOCKED`). Redis oder einen Broker gibt es nicht.
- **worker** ist eine einzige Schleife mit 30-Sekunden-Takt. Jeder Schritt läuft isoliert (ein Fehler in
  einem Schritt hält die anderen nicht auf), in dieser Reihenfolge: fällige Ausgaben und Zustellungen,
  Telegram abfragen, Quellen sammeln, Volltexte laden, Reporter (mit Zeitbudget), Aufräumen.
- **Das LLM ist ein externer Dienst, der oft nicht da ist.** Das ist der Normalfall, kein Fehler:
  - Bearbeitet wird, **sobald** das Modell erreichbar ist. Bis dahin warten neue Artikel, es geht nichts verloren.
  - Die Ausgabe erscheint **trotzdem pünktlich**. Nicht bearbeitete Artikel werden *extraktiv* gesetzt
    (die ersten Sätze des Volltexts, auf Länge gekürzt) und als „Auszug“ markiert.
  - Erreichbarkeit: `GET /v1/models`, höchstens einmal pro Minute. `429/502/503/504` und Verbindungsfehler
    gelten als „später wieder versuchen“.

## Pipeline

| Schritt | Was passiert | Wo | Häufigkeit |
|---|---|---|---|
| 1. Sammeln | RSS/Atom (ETag/Last-Modified, höflich gedrosselt), ICS-Kalender (14 Tage voraus) | Pi | alle 30 min |
| 2. Volltext | Artikelseite laden, Haupttext mit **trafilatura**; Cookie-/Paywall-Seiten und verwürfelter Paywall-Text werden erkannt, dann bleibt es beim Anreißer | Pi | pro neuem Artikel |
| 3. Anreichern | **einmal pro Artikel**: Überschrift, Unterzeile, Zusammenfassung, Ereignis in einem Satz, Themen, Wichtigkeit (strikte JSON-Schema-Ausgabe). Zuerst kommen die Artikel, die ein Leser wahrscheinlich gedruckt bekommt (gleiche Bewertung wie bei der Auswahl), danach der Rest. | Jetson | sobald erreichbar |
| 4. Geschichten | Kandidaten über Embedding-Ähnlichkeit (ohne Embeddings: Themen-Überlappung), das LLM wählt eine laufende Geschichte oder „neu“ | Jetson | sobald erreichbar |
| 5. Auswahl | Je Leser: Interessen × Themen, Wichtigkeit, Aktualität, Quellenvielfalt, eine Meldung pro Geschichte, nichts doppelt aus den letzten Ausgaben | Pi (ohne LLM) | vor jeder Ausgabe |
| 6. Setzen | Ausgabe-JSON → Typst → PDF (PDF/UA-1); die Weboberfläche zeigt dasselbe JSON als barrierefreie HTML-Fassung | Pi | vor jeder Ausgabe |
| 7. Zustellen | Telegram-Bot oder SMTP zur gewünschten Uhrzeit an den gewählten Wochentagen, mit Wiederholungen | Pi | je Leser |

Die teure LLM-Arbeit fällt **einmal pro Artikel** an, nicht pro Leser. Qwen3.5-9B braucht auf dem Jetson rund
20–30 Sekunden pro Artikel (etwa 150 pro Stunde); captiva ist nur für Vergleiche nötig.

## KI-Modelle

- **Sprachmodell:** Qwen3.5-9B (IQ4_XS) über llama.cpp auf dem Jetson, Denkmodus im Server aus. Die Aufgaben
  sind klein und eng gefasst, mit Quelltext im Kontext (höchstens 6000 Zeichen) und strikter
  JSON-Schema-Ausgabe; `finish_reason` muss `stop` sein. Gewählt nach einem Vergleich an 15 echten Artikeln
  mit Gemma 3 4B und Qwen3.5-4B (am genauesten bei Zahlen und Namen, alle Antworten gültig, unterscheidet die
  Wichtigkeit). Ollama und vLLM scheiden aus: Ollama nutzt unter JetPack 7.2 die GPU nicht, vLLM braucht zu viel
  des gemeinsamen 8-GB-Speichers. Einrichtung und Messwerte: `deploy/jetson/README.md`.
- **Embeddings:** EmbeddingGemma, ebenfalls auf dem Jetson (auf der CPU, spart Speicher), in pgvector
  gespeichert. Ohne Embedding-Modell
  (z. B. mit captiva) ordnet Eilkurier Geschichten über Themen-Überlappung vor.
- **captiva (optional):** vLLM mit Qwen3.8 27B, `http://captiva.fritz.box:8080` (immer voll qualifiziert),
  Denkmodus aus über `EILKURIER_LLM_EXTRA_BODY={"chat_template_kwargs":{"enable_thinking":false}}`. captiva wird
  mit guitar-vision geteilt: eine Anfrage zur Zeit, nichts an captiva ändern.
- **Simulator:** `eilkurier simulator` spricht dieselbe API und antwortet regelbasiert. Damit laufen Tests,
  Entwicklung und die Demo (`docker compose --profile demo up`) ohne GPU.
- **Gegen Halluzinationen:** Zahlen in der Antwort müssen im Quelltext vorkommen, sonst wird die Antwort
  verworfen (nach drei Versuchen bleibt der Artikel ein Auszug). Jede Meldung trägt Quelle und QR-Code.
- Modelle, URLs und Zusatzparameter sind reine Konfiguration (`.env.example`).

## Telegram-Bot

- Jeder Leser hat in der Weboberfläche einen 6-stelligen **Verknüpfungscode**. Schickt man ihn dem Bot, ist
  der Chat mit dem Leser verbunden.
- Andere Nachrichten an den Bot werden **Leserbriefe** und erscheinen in der nächsten Ausgabe unter „Aus der
  Familie“. `/ausgabe` schickt die neueste Ausgabe noch einmal.
- Der Bot fragt per `getUpdates` ab; er braucht keine Erreichbarkeit von außen.

## Quellen (Ideen-Speicher)

Umgesetzt: RSS/Atom mit Volltext, ICS-Kalender, DWD-Wetter (Bright Sky), Sonne und Mond, „Heute vor … Jahren“
(Wikipedia), Leserbriefe. Der Katalog in der Weboberfläche enthält die geprüften Feeds aus dem alten Eilkurier.

Ideen: Presseportal (Polizei/Behörden der Region), Newsletter über ein IMAP-Postfach, YouTube (RSS +
Transkript), Pollenflug, Spritpreise (Tankerkönig), Bundesliga (OpenLigaDB), Müllabfuhr, Fotos an den Bot,
„Vor 5 Jahren“ aus Immich, Rätselecke (Sudoku programmatisch), Home-Assistant-Werte als Infografik.

## Ausgabe-Dokument (Vertrag zwischen Redaktion und Satz)

Die Redaktion (`edition.py`) erzeugt pro Leser und Tag ein JSON-Dokument. Der Satz (`layout/`) und die
HTML-Fassung kennen nur dieses Format. Referenz ist [`layout/sample/edition.json`](../layout/sample/edition.json):

- `masthead`, `edition` (Nummer, Datum, Leser, `lang`), `style` (`theme`, `paper`, `font_scale`, `paper_tint`)
- `weather`, `sections` (Rubrikenleiste)
- `lead` und `stories[]`: `headline`, `subhead`, `body[]` (Absätze), `source`, `published`, `url`,
  `teaser_only`, `excerpt`, `size` (`large|medium|small`), `background[]` („Was bisher geschah“)
- `briefs[]`, `calendar[]`, `family[]`, `almanac{}`

## Gestaltung

- **Marke:** Name, Slogan („Nachrichten, wie Sie sein sollten“) und Anmutung stammen aus dem Eilkurier von
  2018–2022. Das Logo ist neu gezeichnet ([`assets/brand/rider.svg`](../assets/brand/rider.svg)), weil das alte
  Reiterbild ein Stockfoto mit Wasserzeichen war.
- **Stile:** `klassisch` (Chomsky-Titel, Bebas-Neue-Überschriften, Papierton, Doppellinien, Fraktur-Initialen),
  `feuilleton` (Playfair Display, ruhiger) und `grossdruck` (13 pt, zwei Spalten, dunklerer Nebentext).
  Weitere Stile sind Einträge in `layout/themes.typ`.
- **Spalten:** Die letzte Seite wird ausgeglichen gesetzt, Rubrik- und Artikelköpfe bleiben beim Text.
- **Papierton** (`paper_tint`) ist für Bildschirme gedacht und lässt sich zum Ausdrucken abschalten.
- **Farben** halten Kontrast ≥ 4,5 : 1, im Druck und in beiden Farbschemata der Weboberfläche.
- **Weboberfläche:** SvelteKit (Svelte 5), statisch gebaut und vom `app`-Container ausgeliefert. Mobile-First,
  Hell/Dunkel nach Systemeinstellung, Touch-Ziele ≥ 44 px, sichtbarer Fokus, Sprunglink, Live-Regionen für
  Meldungen, `prefers-reduced-motion`. Texte de/en in `frontend/src/lib/i18n.svelte.ts`. Der API-Client ist aus
  `frontend/openapi.json` generiert; ein Test stellt sicher, dass diese Datei zur API passt.

## Fahrplan

1. **Meilenstein 0 – Fundament** ✅ Repository, Drucklayout mit drei Stilen, API, Container-Image, CI.
2. **Meilenstein 1 – Erste echte Ausgabe** ✅ Schema und Migrationen, Sammeln, Volltext, Anreicherung mit
   extraktivem Ersatz, Ausgaben je Leser, Zustellung per Telegram und E-Mail, Zeitplan.
3. **Meilenstein 2 – Reporter** ✅ Geschichten und „Was bisher geschah“, Auswahl nach Interessen, Simulator.
4. **Meilenstein 3 – Familie** ✅ Weboberfläche (Leser, Stil, Zustellung, Interessen, Quellen, Archiv,
   HTML-Fassung, Leserbriefe, Systemstatus), Haushalts-PIN, Telegram-Verknüpfung.
5. **Als Nächstes:** Inbetriebnahme auf dem Pi (Jetson-Dienst läuft); Prompts mit Qwen3.5-9B an echten
   Artikeln nachschärfen (Maßstab: Probelauf mit Qwen3.8 auf captiva).
6. **Danach:** weitere Quellen (siehe oben), Bilder (serverseitig in Graustufen/Sepia), Wochenendausgabe.
