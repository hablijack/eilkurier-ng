<p align="center"><img src="assets/brand/rider.svg" width="120" alt="Eilkurier Logo: galoppierender Kurierreiter"></p>

<h1 align="center">Eilkurier</h1>
<p align="center"><em>Nachrichten, wie Sie sein sollten.</em></p>

Eilkurier ist ein persönlicher Zeitungsreporter für die Familie. Er liest RSS-Feeds, Kalender und andere
Quellen, lädt die vollständigen Artikel nach, verfolgt Geschichten über Tage hinweg („Was bisher geschah“)
und setzt für jede Person eine eigene **Zeitungsausgabe als PDF**: mit Titelkopf, Spalten, Initialen, Wetter,
Terminen, Leserbriefen und QR-Codes zu den Originalquellen. Zugestellt wird per Telegram oder E-Mail, zu der
Zeit und an den Tagen, die jede Person selbst wählt.

Alles läuft im Heimnetz: der Dienst in Containern auf einem Raspberry Pi, das Sprachmodell (Qwen3.5-9B) und
die Embeddings (EmbeddingGemma) mit llama.cpp auf einem NVIDIA Jetson Orin Nano. Cloud-Dienste sind nicht nötig.
Ist das Modell gerade nicht erreichbar, erscheint die Zeitung trotzdem; die Texte sind dann Auszüge.

Details: [Architektur & Fahrplan](docs/architektur.md).

## Betrieb (Docker Compose, z. B. openmediavault-Compose-Plugin)

**openmediavault / einfachster Weg:** den Inhalt von [`deploy/omv/eilkurier.yml`](deploy/omv/eilkurier.yml) ins
Compose-Plugin kopieren, die mit `ÄNDERN` markierten Werte anpassen, hochfahren. Die Datei enthält alle
Einstellungen und startet so auch mit `docker compose -f eilkurier.yml up -d`.

Aus dem Repository (Entwicklung, Demo):

```bash
cp .env.example .env      # Passwort, Ort, Sprachmodell, Telegram/SMTP eintragen
docker compose up -d      # postgres → migrate → app + worker
# Weboberfläche: http://<pi>:8080
```

Auf dem Jetson läuft `llama-server` (llama.cpp) als Compose-Dienst. Einrichtung, Modelle und Messwerte:
[deploy/jetson/README.md](deploy/jetson/README.md).

Ohne Sprachmodell-Hardware, mit simuliertem Modell und Beispielhaushalt:

```bash
# in .env: EILKURIER_LLM_URL=http://simulator:11434
docker compose --profile demo up -d
docker compose run --rm app eilkurier seed-demo
```

Das Image `hablijack/eilkurier-ng` wird für `linux/arm64` und `linux/amd64` gebaut.

### Versionen

Eilkurier folgt [Semantic Versioning](https://semver.org/lang/de/). Code (`pyproject.toml`), Git-Tag (`vX.Y.Z`)
und Docker-Image (`X.Y.Z`) tragen immer dieselbe Nummer; was sich geändert hat, steht in
[CHANGELOG.md](CHANGELOG.md). Images gibt es nur für Releases, jeweils als `X.Y.Z`, `X.Y`, `X` und `latest`.
Die Compose-Dateien nennen die genaue Version.

**Update auf dem Pi:** in der Compose-Datei die Nummer bei `image: hablijack/eilkurier-ng:…` erhöhen, im Plugin
„Pull“ und danach „Up“ (erst „Up“ ersetzt die laufenden Container). Migrationen laufen dabei von selbst.

**Release erstellen** (auf `main`, sauberer Arbeitsstand, Änderungen unter „Unreleased“ im Changelog):

```bash
scripts/release.py 0.3.0     # Version überall setzen, Changelog datieren, Commit „Release 0.3.0“, Tag v0.3.0
git push --follow-tags       # CircleCI testet und baut die Images 0.3.0, 0.3, 0 und latest
```

## Entwicklung

Voraussetzungen: [uv](https://docs.astral.sh/uv/), Node 22, Docker (für Postgres).

```bash
uv sync
docker run -d --name ek-pg -e POSTGRES_PASSWORD=test -e POSTGRES_USER=test -p 55432:5432 pgvector/pgvector:pg17
export EILKURIER_TEST_DATABASE_URL=postgresql+psycopg://test:test@localhost:55432/test
uv run pytest                     # ohne die Variable laufen nur die Tests ohne Datenbank
uv run eilkurier render-sample --theme grossdruck -o beispiel.pdf

cd frontend && npm ci && npm run dev   # Weboberfläche mit Proxy auf die API (Port 8080)
```

## Projektaufbau

| Pfad | Inhalt |
|---|---|
| `src/eilkurier/` | Python-Dienst: API (FastAPI), Worker-Pipeline, Reporter, Satz, Zustellung, Simulator |
| `frontend/` | Weboberfläche (SvelteKit, statisch gebaut) |
| `layout/` | Typst-Vorlagen der Druckausgabe, Stile, Beschriftungen (i18n), Beispielausgabe |
| `prompts/` | Anweisungen an das Sprachmodell (de/en) |
| `assets/` | Logo (SVG) und Schriften (alle SIL Open Font License) |
| `docs/` | Architektur, Entscheidungen, Fahrplan |

## Lizenz

GPL-3.0-or-later. Die Schriften in `assets/fonts/` stehen unter der SIL Open Font License 1.1
(Lizenztexte liegen daneben).
