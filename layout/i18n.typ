// UI strings printed on the page. Article texts are written by the reporter in the reader's language;
// these are only the fixed labels around them.
#let strings = (
  de: (
    edition-for: "Ausgabe für",
    edition-no: "Nr.",
    price: "Preis: unbezahlbar",
    weather: "Wetter",
    page: "Seite",
    background: "Was bisher geschah",
    new-today: "Neu heute",
    briefs: "Kurz notiert",
    family: "Aus der Familie",
    almanac: "Almanach",
    source: "Quelle",
    teaser-only: "nur Anreißer verfügbar",
    excerpt: "Auszug",
    calendar: "Termine",
    quiet-day: "Heute gibt es keine neuen Meldungen aus deinen Quellen.",
    to-original: "Zum Original",
    qr-alt: "QR-Code zum Originalartikel:",
  ),
  en: (
    edition-for: "Edition for",
    edition-no: "No.",
    price: "Price: priceless",
    weather: "Weather",
    page: "Page",
    background: "The story so far",
    new-today: "New today",
    briefs: "In brief",
    family: "From the family",
    almanac: "Almanac",
    source: "Source",
    teaser-only: "teaser only",
    excerpt: "excerpt",
    calendar: "Upcoming",
    quiet-day: "No new stories from your sources today.",
    to-original: "Read the original",
    qr-alt: "QR code linking to the original article:",
  ),
)

#let tr(lang) = strings.at(lang, default: strings.de)
