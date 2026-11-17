// Eilkurier print layout. Renders one personal edition from an edition JSON document
// (schema: see docs/architektur.md and layout/sample/edition.json).
#import "@preview/droplet:0.3.1": dropcap
#import "@preview/tiaoma:0.3.0"
#import "themes.typ": themes
#import "i18n.typ": tr

// ---------------------------------------------------------------------------------------------
// Small building blocks
// ---------------------------------------------------------------------------------------------

#let double-rule(t) = stack(
  spacing: 1.6pt,
  line(length: 100%, stroke: 0.7pt + t.ink),
  line(length: 100%, stroke: 0.7pt + t.ink),
)

#let double-box(t, body) = rect(
  width: 100%,
  stroke: 0.7pt + t.ink,
  inset: 1.6pt,
  rect(width: 100%, stroke: 0.7pt + t.ink, inset: 6pt, body),
)

// Italic deck between two short ornament rules (the old `.hl2` style).
#let deck(t, body) = align(center, block(width: 100%, below: 0.7em, sticky: true, stack(
  spacing: t.body-size * 0.9,
  line(length: 28%, stroke: 0.5pt + t.ink),
  par(justify: false, text(font: t.deck-font, style: "italic", size: t.body-size * 1.25, fill: t.ink, body)),
  line(length: 28%, stroke: 0.5pt + t.ink),
)))

#let label-text(t, body, size: 11pt, fill: none) = text(
  font: "Bebas Neue",
  hyphenate: false,
  size: size,
  tracking: 0.8pt,
  fill: if fill == none { t.ink } else { fill },
  upper(body),
)

#let meta-line(t, s, l) = {
  let parts = (s.source, s.at("published", default: none)).filter(p => p != none)
  let teaser = if s.at("teaser_only", default: false) { " · " + l.teaser-only } else { "" }
  block(sticky: true, width: 100%, align(right, text(size: t.body-size * 0.85, fill: t.muted, style: "italic")[(#parts.join(" · ")#teaser)]))
}

#let paragraphs(ps) = ps.map(p => [#p]).join(parbreak())

// Typst does not balance columns; measure the text in a single column and cap the height.
#let balanced-columns(n, gutter, body) = if n <= 1 { body } else {
  layout(size => {
    let col-width = (size.width - gutter * (n - 1)) / n
    let height = measure(block(width: col-width, body)).height
    block(width: 100%, height: height / n + 2.5em, columns(n, gutter: gutter, body))
  })
}

// Drop cap on the first paragraph only: droplet's block is not breakable, so the remaining
// paragraphs must stay outside of it to flow across columns and pages.
#let first-with-dropcap(t, ps, lines) = dropcap(
  height: lines,
  font: t.drop-font,
  fill: t.ink,
  gap: 2pt,
  hyphenate: false,
)[#ps.first()]

#let body-with-dropcap(t, ps, lines) = {
  first-with-dropcap(t, ps, lines)
  if ps.len() > 1 { parbreak(); paragraphs(ps.slice(1)) }
}

#let qr(t, url, l, size: 1.5cm) = if url != none {
  grid(
    columns: (auto, 1fr),
    gutter: 5pt,
    align: horizon,
    box(tiaoma.qrcode(url, width: size, alt: l.qr-alt + " " + url)),
    text(size: t.body-size * 0.8, fill: t.muted, l.to-original),
  )
}

// "Was bisher geschah": the reporter's running memory of a story, printed as a framed box.
#let background-box(t, s, l) = {
  let bg = s.at("background", default: none)
  if bg != none {
    block(width: 100%, above: 0.6em, below: 0.8em, double-box(t)[
      #set par(justify: true)
      #set text(size: t.body-size * 0.92)
      #label-text(t, l.background, size: t.body-size * 1.2) \
      #paragraphs(bg)
    ])
  }
}

// ---------------------------------------------------------------------------------------------
// Stories
// ---------------------------------------------------------------------------------------------

#let story(t, s, l, level: 3) = block(width: 100%, breakable: true, below: 1.4em)[
  // Headline, deck and source line are sticky blocks: they never end up alone at a column foot.
  #{
    set text(size: t.story-sizes.at(s.at("size", default: "medium")))
    heading(level: level, s.headline)
  }
  #if s.at("subhead", default: none) != none { deck(t, s.subhead) }
  #meta-line(t, s, l)
  #body-with-dropcap(t, s.body, t.drop-lines)
  #background-box(t, s, l)
  #qr(t, s.at("url", default: none), l, size: 1.2cm)
  #v(0.2em)
  #align(center, line(length: 40%, stroke: 0.5pt + t.ink))
]

#let lead-story(t, s, l) = block(width: 100%, below: 1em)[
  #{
    set text(size: t.lead-size)
    heading(level: 2, s.headline)
  }
  #if s.at("subhead", default: none) != none { deck(t, s.subhead) }
  #if t.lead-sidebar [
    #grid(
      columns: (2.2fr, 1fr),
      gutter: 6mm,
      [
        #meta-line(t, s, l)
        #balanced-columns(t.lead-columns, 5mm, body-with-dropcap(t, s.body, t.drop-lines + 1))
      ],
      [
        #background-box(t, s, l)
        #qr(t, s.at("url", default: none), l)
      ],
    )
  ] else [
    #meta-line(t, s, l)
    #balanced-columns(t.lead-columns, 7mm, body-with-dropcap(t, s.body, t.drop-lines + 1))
    #background-box(t, s, l)
    #qr(t, s.at("url", default: none), l)
  ]
]

// ---------------------------------------------------------------------------------------------
// Masthead
// ---------------------------------------------------------------------------------------------

#let weather-box(t, w, l) = if w != none {
  double-box(t)[
    #set text(size: 8.5pt)
    #set par(justify: false)
    #label-text(t, l.weather + " · " + w.place, size: 10pt) \
    #text(style: "italic", w.summary) \
    #w.temp_min° / *#w.temp_max°C* · #w.wind
  ]
}

#let edition-box(t, e, l) = double-box(t)[
  #set text(size: 8.5pt)
  #set par(justify: false)
  #label-text(t, l.edition-for + " " + e.reader, size: 10pt) \
  #l.edition-no #e.number \
  #text(style: "italic", l.price)
]

#let masthead(t, ed, l) = {
  let m = ed.masthead
  grid(
    columns: (1fr, 2.8fr, 1fr),
    gutter: 4mm,
    align: (left + horizon, center + horizon, right + horizon),
    weather-box(t, ed.at("weather", default: none), l),
    [
      #image("/assets/brand/rider.svg", height: t.masthead-size * 0.8, alt: "Eilkurier Logo: galoppierender Kurierreiter")
      #v(-0.9em)
      // The newspaper title is the document's level-1 heading (PDF/UA: lead = 2, stories = 3).
      #box(text(font: t.masthead-font, size: t.masthead-size, weight: "black", fill: t.ink, hyphenate: false, heading(level: 1, outlined: false, m.title)))
      #v(-0.8em)
      #label-text(t, m.slogan, size: 15pt)
    ],
    edition-box(t, ed.edition, l),
  )
  v(1mm)
  line(length: 100%, stroke: 0.7pt + t.ink)
  v(-2mm)
  grid(
    columns: (1fr, auto, 1fr),
    align: (left, center, right),
    label-text(t, m.region, size: 10pt), label-text(t, ed.edition.date_label, size: 10pt), label-text(t, m.since, size: 10pt),
  )
  v(-2mm)
  double-rule(t)
  v(-1mm)
  block(width: 100%, fill: t.ink, inset: (y: 5pt), align(center, label-text(
    t,
    "· " + ed.sections.join(" · ") + " ·",
    size: 13pt,
    fill: t.paper,
  )))
  v(3mm)
}

// ---------------------------------------------------------------------------------------------
// Side sections
// ---------------------------------------------------------------------------------------------

#let section-title(t, title) = block(below: 0.5em, width: 100%, {
  double-rule(t)
  v(-2pt)
  align(center, label-text(t, title, size: t.body-size * 1.6))
  v(-6pt)
  line(length: 100%, stroke: 0.7pt + t.ink)
})

#let briefs(t, items, l) = if items.len() > 0 {
  block(width: 100%, breakable: true, below: 1.4em)[
    #section-title(t, l.briefs)
    #for b in items [
      #text(font: t.head-font, weight: t.head-weight, size: t.body-size * 1.25, if t.head-upper { upper(b.headline) } else { b.headline }) \
      #b.text #text(fill: t.muted, style: "italic", size: t.body-size * 0.85)[(#b.source)]
      #v(0.3em)
    ]
  ]
}

#let family(t, items, l) = if items.len() > 0 {
  block(width: 100%, breakable: true, below: 1.4em)[
    #section-title(t, l.family)
    #for f in items [
      #par(justify: false, text(font: t.deck-font, style: "italic", size: t.body-size * 1.15)[„#f.text“])
      #align(right, text(fill: t.muted, size: t.body-size * 0.9)[— #f.from])
    ]
  ]
}

#let almanac(t, a, l) = if a != none {
  block(width: 100%, breakable: false, below: 1.4em)[
    #section-title(t, l.almanac)
    #set par(justify: false)
    #for (k, v) in a [
      #label-text(t, k, size: t.body-size * 1.1): #v \
    ]
  ]
}

// ---------------------------------------------------------------------------------------------
// The edition
// ---------------------------------------------------------------------------------------------

#let ausgabe(ed) = {
  let style = ed.at("style", default: (:))
  let t = themes.at(style.at("theme", default: "klassisch"), default: themes.klassisch)
  t.body-size = t.body-size * style.at("font_scale", default: 1.0)
  let lang = ed.edition.at("lang", default: "de")
  let l = tr(lang)
  let tint = style.at("paper_tint", default: true)

  set document(
    title: ed.masthead.title + " – " + l.edition-for + " " + ed.edition.reader + ", " + ed.edition.date_label,
    author: ed.masthead.title,
    date: auto,
  )
  set page(
    paper: style.at("paper", default: "a4"),
    margin: (x: 13mm, top: 13mm, bottom: 17mm),
    // Paper tint looks lovely on screens and tablets; switch it off when printing on real paper.
    fill: if tint { t.paper } else { none },
    background: {
      place(top + left, dx: 6mm, dy: 6mm, rect(width: 100% - 12mm, height: 100% - 12mm, stroke: 0.8pt + t.ink))
      place(top + left, dx: 7.4mm, dy: 7.4mm, rect(width: 100% - 14.8mm, height: 100% - 14.8mm, stroke: 0.8pt + t.ink))
    },
    footer: context {
      set text(size: 8pt, fill: t.muted)
      line(length: 100%, stroke: 0.5pt + t.ink)
      v(-2mm)
      grid(
        columns: (1fr, auto, 1fr),
        align: (left, center, right),
        [#ed.masthead.title · #l.edition-for #ed.edition.reader],
        [#l.page #counter(page).display()],
        [#ed.edition.date_label],
      )
    },
  )
  set text(font: t.body-font, size: t.body-size, fill: t.ink, lang: lang, hyphenate: true)
  set par(justify: true, leading: t.leading, spacing: t.leading * 1.6)

  show heading.where(level: 1): it => it.body
  show heading.where(level: 2).or(heading.where(level: 3)): it => block(width: 100%, above: 0.4em, below: 0.45em, sticky: true, align(center, par(justify: false, leading: 0.35em, text(
    font: t.head-font,
    weight: t.head-weight,
    fill: t.ink,
    hyphenate: it.level > 2, // never break the lead headline
    if t.head-upper { upper(it.body) } else { it.body },
  ))))

  masthead(t, ed, l)

  if ed.at("lead", default: none) != none {
    lead-story(t, ed.lead, l)
    double-rule(t)
    v(2mm)
  }

  columns(t.columns, gutter: 5mm)[
    // Without a lead story the stories move up one heading level (PDF/UA forbids skipping levels).
    #let level = if ed.at("lead", default: none) == none { 2 } else { 3 }
    #for s in ed.at("stories", default: ()) { story(t, s, l, level: level) }
    #briefs(t, ed.at("briefs", default: ()), l)
    #family(t, ed.at("family", default: ()), l)
    #almanac(t, ed.at("almanac", default: none), l)
  ]
}
