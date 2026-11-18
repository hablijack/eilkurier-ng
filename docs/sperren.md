# Sperren: Zustimmungswände, Bot-Sperren, Bezahlschranken

Stand: 18.11.2026, gemessen mit je 6 aktuellen Artikeln pro Quelle.
Ohne Volltext druckt der Eilkurier den Anreißer aus dem Feed (Kennzeichen `excerpt`): Die Zeitung erscheint
trotzdem, die Meldung ist dann nur kürzer und der Reporter fasst nichts zusammen.

## Überblick

| Quelle | Sperre | Was der Eilkurier tut | Ergebnis |
|---|---|---|---|
| Golem.de | Zustimmungswand (Cookies/Werbung), danach frei lesbar | stimmt zu wie ein Leser (`consent.py`) | 5 von 6 Volltexte |
| Golem.de, „Golem Plus“ | Bezahlschranke | erkennt sie (`isAccessibleForFree: false`), bleibt beim Anreißer | Anreißer |
| ZEIT ONLINE | Bot-Sperre: HTTP 403 für jeden automatischen Abruf | nichts, Anreißer aus dem Feed | 0 von 6 |
| Frankenpost (alle Lokalteile) | Bezahlschranke „Frankenpost Plus“ auf praktisch jedem Artikel | erkennt sie, bleibt beim Anreißer | 0 von 6 (vorher wurden Anrisse mit 500–600 Zeichen fälschlich als Volltext gezählt) |

## Was umgesetzt ist: Zustimmen statt Umgehen

`src/eilkurier/consent.py` erkennt bekannte Zustimmungsseiten und tut genau das, was der Knopf „Zustimmen“ auf
der Seite tut. Bei Golem ist das ein Aufruf von `golem.de/abo/setconsentcookie.php?type=cmp`, der das Cookie
`golem_consent20` setzt. Danach lädt der Eilkurier den Artikel noch einmal.

- Die Parameter (Cookie-Version, Adresse) kommen jedes Mal von der Zustimmungsseite selbst. Ändert Golem die
  Version, funktioniert es trotzdem.
- Das Cookie lebt nur im Arbeitsspeicher des Workers. Nach einem Neustart stimmt er beim ersten Golem-Artikel
  wieder zu (eine Anfrage).
- Der Eilkurier lädt keine Werbung und keine Tracker. Er ruft nur die Artikelseite ab, wie bisher.
- Weitere Seiten mit Zustimmungswand bekommen bei Bedarf einen eigenen kleinen Handler in `consent.py`.
  Ein eingebetteter Browser (Chromium/Playwright) war die erste Idee. Er ist für Golem aber nicht nötig und
  wäre auf dem Pi teuer: etwa 300–500 MB RAM pro Seite, ein großes Image, und er verträgt sich schlecht mit dem
  schreibgeschützten Container.

## Was offen ist: Entscheidungen für dich

### 1. ZEIT ONLINE (Bot-Sperre)

ZEIT blockt automatische Abrufe bewusst mit HTTP 403. Der User-Agent des Eilkurier nennt sich ehrlich als Bot.
Diese Sperre auszutricksen, etwa mit einem gefälschten Browser-User-Agent, wechselnden IPs oder Headless-Browsern
mit Tarnung, setze ich nicht um: Das hebelt eine Entscheidung des Verlags aus und verstößt gegen seine
Nutzungsbedingungen.

Legitime Möglichkeiten:

- **So lassen wie jetzt:** ZEIT liefert gute Anreißer im Feed, und die Meldung wird gedruckt, nur kurz.
- **ZEIT-Abo mit Login:** Mit einem eigenen Digitalabo ist der Abruf für den privaten Gebrauch der
  Abonnenten durch die Bedingungen eher gedeckt. Die Bot-Sperre gilt aber vermutlich auch für eingeloggte
  Abrufe. Das müsste man ausprobieren, und dafür bräuchte es Zugangsdaten im Eilkurier (siehe Punkt 3).
- **Beim Verlag fragen:** Manche Verlage geben für private, nichtkommerzielle Projekte einen Volltext-Feed
  oder schalten eine IP frei.
- **Quelle ersetzen:** z. B. tagesschau.de oder Deutschlandfunk. Sie liefern Volltext ohne Sperre und decken
  ähnliche Themen ab.

### 2. Frankenpost (Bezahlschranke)

Fast jeder Artikel ist „Frankenpost Plus“. Frei sind nur 300–600 Zeichen Anriss.

- **So lassen:** Die Lokalteile liefern dann nur Kurzmeldungen. Das passt gut zur Rubrik „Aus der Region“, ist
  aber dünn.
- **Eigenes Frankenpost-Digitalabo mit Login:** Das wäre die saubere Lösung, wenn ihr ohnehin ein Abo habt oder
  wollt. Der Eilkurier liest dann, was ihr als Abonnenten ohnehin lesen dürft, nur für die Familie. Den
  Login-Ablauf (Formular, Cookies, ggf. SSO des Verlags) müsste man sich ansehen, bevor man den Aufwand
  abschätzt.
- **Lokale Alternativen ohne Schranke:** Gemeinde- und Landkreis-Seiten, Polizeiberichte (Presseportal),
  Vereins-Feeds.

### 3. Wenn Logins kommen: was dafür nötig wäre

- Zugangsdaten als Umgebungsvariablen (wie das Telegram-Token), nie in der Datenbank oder im Repo.
- Pro Quelle eine Login-Art in der Quelle hinterlegen, analog zu `image_mode`.
- Sitzungs-Cookies nur im Speicher des Workers. Nach einem Neustart meldet er sich neu an. Das passt zum
  zustandslosen Container.
- Nutzungsbedingungen des Abos prüfen: Viele erlauben das Lesen nur für die abonnierende Person oder den
  Haushalt. Eine Familienzeitung für den eigenen Haushalt ist meist gedeckt, eine Weitergabe nach außen nicht.

### 4. Was der Eilkurier grundsätzlich nicht tut

- Bezahlschranken umgehen: Archivdienste, Google-Cache-Tricks, „Reader-Mode“-Proxies, Text aus versteckten
  Seitenteilen oder verwürfeltem Text zurückrechnen.
- Bot-Sperren austricksen: gefälschte User-Agents, rotierende IPs, Tarn-Browser.
