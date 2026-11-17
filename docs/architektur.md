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
| KI | NVIDIA Jetson Orin Nano 8 GB im Heimnetz, Ollama mit OpenAI-kompatibler API. Sprachmodell und Embeddings laufen **nur** dort. |
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
                                                    ▼
                                    Jetson Orin Nano: Ollama (LLM + Embeddings)
```

- **app** und **worker** nutzen dasselbe Image mit unterschiedlichem Startbefehl. Sie halten keinen Zustand:
  Alles Veränderliche liegt in Postgres, erzeugte PDFs in Postgres oder einem Volume.
- **postgres + pgvector** ist der einzige Speicher: Stammdaten, Artikel, Embeddings und die Job-Warteschlange
  (über `SELECT … FOR UPDATE SKIP LOCKED`). Redis oder einen Broker gibt es nicht.
- **Jetson** ist ein externer Dienst, konfiguriert über eine URL. Ist er nicht erreichbar, bleiben Artikel
  „unredigiert“ in der Warteschlange und werden nachgeholt; eine Ausgabe fällt notfalls auf Anreißer zurück.

## Pipeline

| Schritt | Was passiert | Wo | Häufigkeit |
|---|---|---|---|
| 1. Sammeln | Feeds und andere Quellen abfragen (ETag/Last-Modified, höflich gedrosselt) | Pi | alle 30–60 min |
| 2. Volltext | Artikelseite laden, Haupttext mit **trafilatura** extrahieren; bei Bezahlschranke `teaser_only` | Pi | pro neuem Artikel |
| 3. Anreichern | **einmal pro Artikel**: Zusammenfassung, Kernfakten, Schlagworte (strukturiert als JSON), Embedding | Jetson | laufend, Warteschlange |
| 4. Geschichten | Artikel per Embedding-Ähnlichkeit + Zeitfenster zu *Stories* bündeln; Story-Gedächtnis („Stand der Dinge“) fortschreiben | Pi + Jetson | laufend |
| 5. Auswahl | Je Leser: Interessen-Embeddings × Artikel, Quellenvielfalt, Neuigkeitswert → Seitenplan | Pi (ohne LLM) | vor jeder Ausgabe |
| 6. Redigieren | Aufmacher wählen, Texte auf Länge bringen, „Neu heute“ vs. „Was bisher geschah“, Ton je Leser | Jetson | vor jeder Ausgabe |
| 7. Setzen | Ausgabe-JSON → Typst → PDF (PDF/UA-1), zusätzlich eine barrierefreie HTML-Fassung | Pi | vor jeder Ausgabe |
| 8. Zustellen | Telegram-Bot oder SMTP zur gewünschten Uhrzeit | Pi | je Leser |

Die teure LLM-Arbeit (Schritt 3) fällt **einmal pro Artikel** an, nicht pro Leser. Pro Leser bleibt nur wenig
Redaktionsarbeit. Damit reicht ein kleines Modell auf dem Jetson auch für sechs Ausgaben.

## KI-Modelle (Jetson Orin Nano, 8 GB geteilter Speicher)

- **Sprachmodell:** Startpunkt **Gemma 3 4B** (QAT-Variante, int4, ≈ 3–4 GB). Begründung: sehr gutes Deutsch
  für die Größe; Qwen-Modelle gleicher Größe sind stark im Schlussfolgern, schreiben aber weniger natürliches
  Deutsch. 12B-Modelle passen nicht neben die Embeddings. Das Modell ist nur ein Konfigurationswert. Vor
  Meilenstein 2 vergleichen wir 2–3 aktuelle Modelle mit echten Artikeln (Qualität, Halluzinationen, Tokens/s).
- **Embeddings:** **EmbeddingGemma** (≈ 300 M Parameter, mehrsprachig) über denselben Ollama-Dienst.
- **Gegen Halluzinationen:** kurze, eng gefasste Aufgaben, strukturierte Ausgabe (JSON-Schema), immer mit
  Quelltext im Kontext. Zahlen und Namen werden gegen den Quelltext geprüft. Jede Meldung trägt Quelle und QR-Code.

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
   Volltext laden, Anreicherung über den Jetson, eine Ausgabe für eine Person, Zustellung per Telegram, Zeitplan.
3. **Meilenstein 2 – Reporter:** Story-Bündelung und „Was bisher geschah“, Modellvergleich auf dem Jetson,
   Auswahl nach Interessen.
4. **Meilenstein 3 – Familie:** Weboberfläche (Profile, Interessen, Quellen, Stil, Zustellzeit, Archiv),
   E-Mail-Zustellung, Leserbriefe über den Bot.
5. **Danach:** weitere Quellen (Wetter, Kalender, Sport, …), HTML-Fassung jeder Ausgabe, Bilder,
   Wochenendausgabe.
