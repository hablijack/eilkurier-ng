# Änderungen

Alle nennenswerten Änderungen an Eilkurier. Das Format folgt [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionen folgen [Semantic Versioning](https://semver.org/lang/de/): **MAJOR** für Änderungen, nach denen eine
bestehende Installation nicht mehr ohne Zutun läuft (z. B. umbenannte Einstellungen), **MINOR** für neue Funktionen,
**PATCH** für Fehlerbehebungen. Datenbank-Migrationen laufen bei jedem Update automatisch (`migrate`).

Ein Release entsteht mit `scripts/release.py X.Y.Z` (siehe README, Abschnitt „Versionen“).

## [Unreleased]

### Behoben

- CI: Der Abgleich von `frontend/openapi.json` mit der API ignoriert die App-Version, sonst schlägt jedes
  Release fehl. 0.2.0 wurde deshalb nie als Image gebaut; 0.2.1 enthält dieselben Funktionen.

## [0.2.0] – 2026-11-18

### Neu

- Weboberfläche ohne Login: Die Startseite fragt „Wer liest?“, das Gerät merkt sich die Wahl.
- Einrichtungs-Assistent in vier Schritten: Interessen → Zeitungen → Wichtigkeit sortieren → Zustellung und Stil.
  Der Katalog hat dafür Themen mit Beschreibung, Symbol und Farbe sowie Beschreibungen und Empfehlungen je Zeitung.
- „Meine Zeitung“: sortierbare Zeitungsliste, besondere Wünsche, Zustellung und Aussehen auf einer Seite.
- Die Reihenfolge der Zeitungen zählt: Die wichtigste Quelle eines Lesers bekommt bei der Auswahl bis zu
  1,5 Punkte Bonus (Migration `0003`).
- Neuer Zeitungsstil `epaper` (moderne Tageszeitung mit farbigen Rubriken) als Standard für neue Leser, auch in der
  HTML-Ansicht der Ausgabe. Der bisherige Stil `klassisch` heißt in der Oberfläche jetzt „Retro“.
- Semantische Versionierung: Git-Tags `vX.Y.Z`, Docker-Images `X.Y.Z`, `X.Y`, `X` und `latest`.

### Geändert

- Heller, ruhiger Look nach Art von posteo.de statt Papierbraun; Braun nur noch als Akzent.
- Logo: größerer Reiter, der Schweif fällt nach hinten statt aufzuflackern.
- API: `GET /catalog` liefert jetzt `{topics, sources}`; neu ist `POST /catalog/sources`.
- Docker-Images entstehen nur noch aus Release-Tags, nicht mehr aus jedem Commit auf `main`.
  Die OMV-Compose-Datei nennt die genaue Version.

## [0.1.0] – 2026-11-18

Erster lauffähiger Stand (ohne Release-Tag-Image; auf Docker Hub als `:cc0dc62` bis `:1150955`):
Sammeln, Volltext, Reporter mit Qwen3.5-9B auf dem Jetson, Ausgaben als PDF/UA-1, Zustellung per Telegram und
E-Mail, Weboberfläche, Compose-Datei für openmediavault.

[Unreleased]: https://github.com/hablijack/eilkurier-ng/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/hablijack/eilkurier-ng/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/hablijack/eilkurier-ng/releases/tag/v0.1.0
