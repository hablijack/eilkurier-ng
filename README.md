<p align="center"><img src="assets/brand/rider.svg" width="120" alt="Eilkurier Logo: galoppierender Kurierreiter"></p>

<h1 align="center">Eilkurier</h1>
<p align="center"><em>Nachrichten, wie Sie sein sollten.</em></p>

Eilkurier ist ein persönlicher Zeitungsreporter für die Familie. Er liest RSS-Feeds und andere Quellen,
lädt die vollständigen Artikel nach, verfolgt Geschichten über Tage hinweg („Was bisher geschah“) und setzt
für jede Person jeden Morgen eine eigene **Zeitungsausgabe als PDF**: mit Titelkopf, Spalten, Initialen und
QR-Codes zu den Originalquellen. Zugestellt wird per Telegram oder E-Mail, zu der Zeit, die jede Person selbst wählt.

Alles läuft im Heimnetz. Der Dienst arbeitet in Containern auf einem Raspberry Pi, die Sprach- und
Embedding-Modelle auf einem NVIDIA Jetson. Es werden keine Cloud-Dienste benötigt.

> **Status:** frühe Entwicklung. Vorhanden sind das Drucklayout (drei Stile), die API mit einer
> Beispielausgabe, das Container-Image und die CI. Die Pipeline (Sammeln, Redigieren, Zustellen) folgt; siehe
> [Architektur & Fahrplan](docs/architektur.md).

## Ausprobieren

Voraussetzung: [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run eilkurier render-sample --theme klassisch -o beispiel.pdf   # klassisch | feuilleton | grossdruck
uv run uvicorn eilkurier.app:create_app --factory --reload --port 8080
# → http://localhost:8080/api/v1/docs  und  http://localhost:8080/api/v1/samples/edition.pdf?theme=feuilleton
```

## Betrieb (Docker Compose, z. B. openmediavault-Compose-Plugin)

```bash
cp .env.example .env    # Passwörter setzen
docker compose up -d
```

Das Image `hablijack/eilkurier-ng` wird für `linux/arm64` und `linux/amd64` gebaut.

## Projektaufbau

| Pfad | Inhalt |
|---|---|
| `src/eilkurier/` | Python-Dienst (FastAPI): API, Satz, später Pipeline-Worker |
| `layout/` | Typst-Vorlagen der Druckausgabe, Stile, Beschriftungen (i18n), Beispielausgabe |
| `assets/` | Logo (SVG) und Schriften (alle SIL Open Font License) |
| `docs/` | Architektur, Entscheidungen, Fahrplan |

## Lizenz

GPL-3.0-or-later. Die Schriften in `assets/fonts/` stehen unter der SIL Open Font License 1.1
(Lizenztexte liegen daneben).
