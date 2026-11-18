# Änderungen

Alle nennenswerten Änderungen an Eilkurier. Das Format folgt [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionen folgen [Semantic Versioning](https://semver.org/lang/de/): **MAJOR** für Änderungen, nach denen eine
bestehende Installation nicht mehr ohne Zutun läuft (z. B. umbenannte Einstellungen), **MINOR** für neue Funktionen,
**PATCH** für Fehlerbehebungen. Datenbank-Migrationen laufen bei jedem Update automatisch (`migrate`).

Ein Release entsteht mit `scripts/release.py X.Y.Z` (siehe README, Abschnitt „Versionen“).

## [Unreleased]

### Geändert

- Weboberfläche im Look des alten Eilkurier: brauner Kopf mit weißem Reiter in der Mitte, Leitspruch
  „Nachrichten, wie sie sein sollten“, braune und weiße Bänder im Wechsel, Überschriften in Versalien zwischen
  Linien, Schrift Brawler für den Schriftzug. Die Startseite übernimmt Texte und Zeichnungen (Zeitung,
  Weltkugel) der alten Seite. Kein dunkles Design mehr, die Rubriken sind einheitlich braun statt bunt.

### Behoben

- Bestehende Installationen bekommen Bilder: Quellen aus dem Katalog, die vor 0.3.0 angelegt wurden, übernehmen
  die gemessene Bild-Einstellung, und Artikel der letzten 36 Stunden suchen nachträglich ihr Seitenbild
  (Migration `0005`).

## [0.3.0] – 2026-11-18

### Neu

- Bilder in der Zeitung: Aufmacher und große Meldungen bekommen ein Bild mit Bildnachweis, im Druck und in der
  Webansicht (im Stil Retro schwarzweiß). Woher die Bilder kommen, ist pro Quelle einstellbar: automatisch,
  aus dem Feed, von der Artikelseite oder keine (Seite „Quellen“). Für die Katalog-Zeitungen ist der Wert an
  den echten Seiten gemessen. Geladen werden nur Bilder von Artikeln, die wahrscheinlich gedruckt werden
  (Migration `0004`).

### Behoben

- Satz: Passte die erste Meldung nicht mehr unter den Aufmacher, rutschten alle Spalten auf Seite 2 und Seite 1
  blieb halb leer. Außerdem konnte am Ende eine leere Seite entstehen.

## [0.2.1] – 2026-11-18

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

[Unreleased]: https://github.com/hablijack/eilkurier-ng/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/hablijack/eilkurier-ng/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/hablijack/eilkurier-ng/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/hablijack/eilkurier-ng/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/hablijack/eilkurier-ng/releases/tag/v0.1.0
