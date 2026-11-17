# Architektur & Fahrplan

## Idee

Jede Person der Familie bekommt täglich ihre eigene Zeitung. Ein „Reporter“ sammelt Nachrichten aus vielen
Quellen, lädt die vollständigen Artikel nach, verfolgt Geschichten über mehrere Tage und schreibt daraus eine
gesetzte Ausgabe im persönlichen Zeitungsstil. Gelesen wird auf Smartphone und iPad (PDF), auf Wunsch auch
ausgedruckt.

## Rahmenbedingungen

| Thema | Entscheidung |
|---|---|
| Betrieb | Docker Compose auf einem Raspberry Pi (arm64, 8 GB RAM, openmediavault 8). Der Pi ist bereits ausgelastet (Load ≈ 3): sparsam bleiben. |
| KI | Primär **captiva** (Intel Arc Pro B70, 32 GB): vLLM mit **Qwen3.8 27B** (Alias `qwen3.8`), OpenAI-kompatibel unter `http://captiva.fritz.box:8080`. captiva ist ein **manuell eingeschalteter Desktop** und wird mit dem Enrichment von guitar-vision geteilt. Später optional der Jetson Orin Nano (derzeit belegt). Auf dem Pi laufen keine Modelle. |
| Zugriff | Nur Heimnetz. Einfache Profilauswahl, optional mit PIN; austauschbar gestaltet. |
| Leser | 6 Personen, jede mit eigenen Interessen, eigenem Stil, eigener Zustellzeit und eigenem Kanal. |
| Code & Images | GitHub (`eilkurier-ng`), CircleCI, Docker Hub öffentlich (`hablijack/eilkurier-ng`, arm64 + amd64). |
| Standards | API-first (OpenAPI), zustandslose Container (12-Factor, Konfiguration per Umgebung), I18n, A11y (WCAG 2.2 AA im Web, PDF/UA-1 im Druck), Mobile-First für die Weboberfläche. |

## Komponenten

```
                    ┌──────────────── Raspberry Pi (docker compose) ────────────────┐
  Quellen ────────▶ │  worker   Sammeln → Volltext → Anreichern → Geschichten →      │
  (RSS, Wetter,     │           Auswahl je Leser → Redigieren → Setzen → Zustellen   │ ──▶ Telegram / E-Mail
   Kalender, …)     │     │                         ▲                                │
                    │     ▼                         │ OpenAI-kompatible API          │
                    │  postgres + pgvector          │                                │
                    │     ▲                         │                                │
                    │  app   REST-API (FastAPI) + Weboberfläche (statisch)           │ ◀── Smartphone / iPad
                    └───────────────────────────────┼────────────────────────────────┘
                                                    ▼ (nur wenn eingeschaltet)
                              captiva: vLLM, Qwen3.8 27B  ·  später optional: Jetson
```

- **app** und **worker** nutzen dasselbe Image mit unterschiedlichem Startbefehl. Sie halten keinen Zustand:
  Alles Veränderliche liegt in Postgres, erzeugte PDFs in Postgres oder einem Volume.
- **postgres + pgvector** ist der einzige Speicher: Stammdaten, Artikel, Embeddings und die Job-Warteschlange
  (über `SELECT … FOR UPDATE SKIP LOCKED`). Redis oder einen Broker gibt es nicht.
- **Das LLM ist ein externer Dienst, der oft nicht da ist.** Das ist der Normalfall, kein Fehler:
  - Angereichert wird, **sobald** captiva erreichbar ist. Bis dahin warten neue Artikel in der Warteschlange,
    es geht nichts verloren.
  - Die Ausgabe erscheint **trotzdem pünktlich**. Nicht angereicherte Artikel werden *extraktiv* gesetzt
    (die ersten Sätze des Volltexts, auf Länge gekürzt) und dezent markiert. Eine Ausgabe wartet nie auf das LLM.
  - Für die Erreichbarkeit fragt der Worker `GET /v1/models` ab, höchstens einmal pro Minute, und nur, solange
    Arbeit ansteht. Bei `429/502/503/504` oder Verbindungsfehlern zieht er sich mit wachsendem Abstand zurück.
- **Rücksicht auf guitar-vision:** captiva bedient auch dessen Enrichment. Eilkurier schickt **eine Anfrage
  zur Zeit**, begrenzt die Tokens pro Anfrage und ändert nie etwas an captiva (vLLM-Konfiguration, Dienste).

## Pipeline

| Schritt | Was passiert | Wo | Häufigkeit |
|---|---|---|---|
| 1. Sammeln | Feeds und andere Quellen abfragen (ETag/Last-Modified, höflich gedrosselt) | Pi | alle 30–60 min |
| 2. Volltext | Artikelseite laden, Haupttext mit **trafilatura** extrahieren; bei Bezahlschranke `teaser_only` | Pi | pro neuem Artikel |
| 3. Anreichern | **einmal pro Artikel**: Zusammenfassung, Kernfakten, Themen-Tags (strukturiert als JSON-Schema) | captiva | sobald erreichbar |
| 4. Geschichten | Neuen Artikel einer offenen *Story* zuordnen oder eine neue eröffnen; Story-Gedächtnis („Stand der Dinge“) fortschreiben | captiva | sobald erreichbar |
| 5. Auswahl | Je Leser: Themen-Tags × Interessen, Quellenvielfalt, Neuigkeitswert → Seitenplan | Pi (ohne LLM) | vor jeder Ausgabe |
| 6. Redigieren | Texte auf Länge bringen, „Neu heute“ vs. „Was bisher geschah“, Ton je Leser; Ersatz: extraktiv | captiva, sonst Pi | vor jeder Ausgabe |
| 7. Setzen | Ausgabe-JSON → Typst → PDF (PDF/UA-1), zusätzlich eine barrierefreie HTML-Fassung | Pi | vor jeder Ausgabe |
| 8. Zustellen | Telegram-Bot oder SMTP zur gewünschten Uhrzeit | Pi | je Leser |

Die teure LLM-Arbeit (Schritt 3) fällt **einmal pro Artikel** an, nicht pro Leser. Pro Leser bleibt nur wenig
Redaktionsarbeit. So kommt das System auch mit wenigen Stunden captiva-Laufzeit am Tag aus.

## KI-Modelle

- **Sprachmodell:** **Qwen3.8 27B** auf captiva (vLLM, GPTQ-Int4; Alias `qwen3.8`). Ein 27B-Modell schreibt
  deutlich besseres Deutsch als ein 4B-Modell und folgt Geschichten zuverlässiger. Aufrufe wie in
  guitar-vision: `temperature: 0`, Denkmodus aus (`chat_template_kwargs.enable_thinking=false`), strikte
  JSON-Schema-Ausgabe, `finish_reason` muss `stop` sein. Modellname und URL sind nur Konfigurationswerte, so dass
  später auch der Jetson oder ein anderes Modell eingesetzt werden kann.
- **Geschichten ohne Embeddings:** captiva stellt nur das Sprachmodell bereit, der Jetson ist belegt. Deshalb
  ordnet das LLM selbst zu: Es bekommt den neuen Artikel und die offenen Stories (Titel + Stand der Dinge) und
  antwortet strukturiert mit „gehört zu Story X“ oder „neue Story“. Das kann ein 27B-Modell gut. Embeddings
  (pgvector) bleiben eine spätere Option, z. B. zur Vorauswahl, wenn die Zahl offener Stories wächst.
- **Gegen Halluzinationen:** eng gefasste Aufgaben, strukturierte Ausgabe, immer mit Quelltext im Kontext.
  Zahlen und Namen werden gegen den Quelltext geprüft. Jede Meldung trägt Quelle und QR-Code.
- **Hostname:** immer voll qualifiziert `captiva.fritz.box` (in Containern wird die Suchdomäne nicht immer
  angehängt; das ist in guitar-vision mit Alpine bereits schiefgegangen).

## Quellen (Ideen-Speicher)

- **Nachrichten:** RSS/Atom mit Volltext; Presseportal (Polizei/Behörden der Region); Gemeinde- und
  Vereinsseiten; Newsletter über ein eigenes IMAP-Postfach; YouTube-Kanäle (RSS + Transkript).
- **Alltag:** DWD-Wetter und Warnungen (Bright Sky API), Pollenflug, Sonne und Mond, Spritpreise (Tankerkönig),
  Bundesliga (OpenLigaDB), Müllabfuhr (ICS), Bahn-Störungen.
- **Familie:** gemeinsamer Kalender (CalDAV/ICS) mit Terminen und Geburtstagen; **Leserbriefe**: Nachrichten
  und Fotos an den Telegram-Bot erscheinen am nächsten Morgen unter „Aus der Familie“; „Vor 5 Jahren“ aus der
  Fotosammlung (z. B. Immich).
- **Unterhaltung:** „Heute vor … Jahren“, Namenstage, Rätselecke (Sudoku programmatisch, nicht per LLM),
  saisonales Rezept.
- **Haus:** Home-Assistant-Werte (PV-Ertrag, Verbrauch) als kleine Infografik.

Jede Quelle ist ein Plugin mit einheitlicher Schnittstelle (`fetch() → Items`), damit neue Quellen ohne
Umbau dazukommen.

## Ausgabe-Dokument (Vertrag zwischen Redaktion und Satz)

Die Redaktion erzeugt pro Leser und Tag ein JSON-Dokument. Der Satz (`layout/`) kennt nur dieses Format.
Referenz ist [`layout/sample/edition.json`](../layout/sample/edition.json):

- `masthead`, `edition` (Nummer, Datum, Leser, `lang`), `style` (`theme`, `paper`, `font_scale`, `paper_tint`)
- `weather`, `sections` (Rubrikenleiste)
- `lead` und `stories[]`: `headline`, `subhead`, `body[]` (Absätze), `source`, `published`, `url`,
  `teaser_only`, `size` (`large|medium|small`), `background[]` („Was bisher geschah“)
- `briefs[]`, `family[]`, `almanac{}`

Später wird daraus ein Pydantic-Modell, und das JSON-Schema wird in die OpenAPI-Beschreibung übernommen.

## Gestaltung

- **Marke:** Name, Slogan („Nachrichten, wie Sie sein sollten“) und Anmutung stammen aus dem Eilkurier von
  2018–2022. Das Logo ist neu gezeichnet ([`assets/brand/rider.svg`](../assets/brand/rider.svg)), weil das alte
  Reiterbild ein Stockfoto mit Wasserzeichen war.
- **Stile:** `klassisch` (Chomsky-Titel, Bebas-Neue-Überschriften, Papierton, Doppellinien, Fraktur-Initialen),
  `feuilleton` (Playfair Display, ruhiger) und `grossdruck` (13 pt, zwei Spalten, dunklerer Nebentext).
  Weitere Stile sind Einträge in `layout/themes.typ`.
- **Papierton** (`paper_tint`) ist für Bildschirme gedacht und lässt sich zum Ausdrucken abschalten.
- **Farben** werden auf Kontrast ≥ 4,5 : 1 gegen den Papierton geprüft. Der alte Grauton `#8b8b8b` (3,3 : 1)
  wurde ersetzt.
- **Bilder** (geplant): werden vor dem Satz serverseitig in Graustufen/Sepia umgerechnet, denn Typst hat keine
  Bildfilter. Alternativtext liefert die Quelle oder das LLM.
- **Weboberfläche** (geplant): SvelteKit, statisch gebaut und vom `app`-Container ausgeliefert. Mobile-First für
  Smartphone und iPad, Paraglide für I18n, API-Client aus der OpenAPI-Beschreibung generiert. Farben aus der
  Marke: Papier `#f9f7f1`, Tinte `#2f2f2f`, Akzent `#6b2f1b`.

## Fahrplan

1. **Meilenstein 0 – Fundament** ✅ Repository, Drucklayout mit drei Stilen, API mit Beispielausgabe,
   Container-Image, CI.
2. **Meilenstein 1 – Erste echte Ausgabe:** Postgres-Schema und Migrationen (Alembic), Feeds sammeln und
   Volltext laden, Anreicherung über captiva mit extraktivem Ersatz, eine Ausgabe für eine Person,
   Zustellung per Telegram, Zeitplan.
3. **Meilenstein 2 – Reporter:** Story-Zuordnung und „Was bisher geschah“, Auswahl nach Interessen.
4. **Meilenstein 3 – Familie:** Weboberfläche (Profile, Interessen, Quellen, Stil, Zustellzeit, Archiv),
   E-Mail-Zustellung, Leserbriefe über den Bot.
5. **Danach:** weitere Quellen (Wetter, Kalender, Sport, …), HTML-Fassung jeder Ausgabe, Bilder,
   Wochenendausgabe.
