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
#let deck(t, body) = if t.modern {
  block(width: 100%, above: 0.3em, below: 0.6em, sticky: true, par(justify: false, leading: 0.45em, text(
    font: t.deck-font,
    size: t.body-size * 1.2,
    fill: t.ink,
    body,
  )))
} else { align(center, block(width: 100%, below: 0.7em, sticky: true, stack(
  spacing: t.body-size * 0.9,
  line(length: 28%, stroke: 0.5pt + t.ink),
  par(justify: false, text(font: t.deck-font, style: "italic", size: t.body-size * 1.25, fill: t.ink, body)),
  line(length: 28%, stroke: 0.5pt + t.ink),
))) }

#let label-text(t, body, size: 11pt, fill: none) = text(
  font: t.label-font,
  weight: t.label-weight,
  hyphenate: false,
  // Bebas Neue is a display face; the e-paper's Fira Sans labels are set smaller and tighter.
  size: if t.modern { size * 0.72 } else { size },
  tracking: if t.modern { 0.6pt } else { 0.8pt },
  fill: if fill == none { t.ink } else { fill },
  upper(body),
)

#let meta-line(t, s, l) = {
  let parts = (s.source, s.at("published", default: none)).filter(p => p != none)
  if s.at("teaser_only", default: false) { parts.push(l.teaser-only) }
  // `excerpt`: printed straight from the source text because the reporter (LLM) had no time for it yet.
  if s.at("excerpt", default: false) { parts.push(l.excerpt) }
  if t.modern {
    block(sticky: true, width: 100%, below: 0.6em, text(font: t.label-font, size: t.body-size * 0.8, fill: t.muted, parts.join(" · ")))
  } else {
    block(sticky: true, width: 100%, align(right, text(size: t.body-size * 0.85, fill: t.muted, style: "italic")[(#parts.join(" · "))]))
  }
}

#let section-color(t, name) = t.section-colors.at(name, default: t.accent)

// e-paper: the section above the headline, in the section's colour.
#let kicker(t, s) = if t.modern and s.at("section", default: none) != none {
  block(below: 0.35em, sticky: true, label-text(t, s.section, size: t.body-size * 1.15, fill: section-color(t, s.section)))
}

#let separator(t) = if t.modern {
  line(length: 100%, stroke: 0.5pt + t.rule)
} else {
  align(center, line(length: 40%, stroke: 0.5pt + t.ink))
}

#let paragraphs(ps) = ps.map(p => [#p]).join(parbreak())

// Pictures: the renderer passes their bytes as `sys.inputs.images` ({"<id>": [byte, ...]}, the only way to
// hand binary data to Typst without files); the sample edition refers to files under layout/sample/.
#let picture-data = {
  let raw = sys.inputs.at("images", default: none)
  if raw == none { (:) } else { json(bytes(raw)) }
}

#let picture-source(img) = if "file" in img { img.file } else {
  let data = picture-data.at(str(img.at("id", default: "")), default: none)
  if data == none { none } else { bytes(data) }
}

// From this pixel width a picture may span the whole lead story (otherwise it would print blurry).
#let wide-picture(s) = {
  let img = s.at("image", default: none)
  img != none and img.width >= 1000
}

// A picture with its credit line. `min-ratio` crops tall pictures (centred) so they don't eat the page,
// `max-height` caps very wide layouts.
#let picture(t, s, l, min-ratio: 4 / 3, max-height: 9cm) = {
  let img = s.at("image", default: none)
  let src = if img == none { none } else { picture-source(img) }
  if src != none {
    let ratio = calc.max(img.width / img.height, min-ratio)
    block(width: 100%, above: 0pt, below: 0.6em, sticky: true, layout(size => {
      let height = calc.min(size.width / ratio, max-height)
      stack(
        spacing: 2.5pt,
        image(src, width: size.width, height: height, fit: "cover", alt: img.alt),
        if img.at("credit", default: none) != none {
          align(right, text(
            font: if t.modern { t.label-font } else { t.body-font },
            size: t.body-size * 0.72,
            fill: t.muted,
            l.photo + " " + img.credit,
          ))
        },
      )
    }))
  }
}

// Typst does not balance columns; measure the text in a single column and cap the height.
#let balanced-columns(n, gutter, body) = if n <= 1 { body } else {
  layout(size => {
    let col-width = (size.width - gutter * (n - 1)) / n
    let height = measure(block(width: col-width, body)).height
    block(width: 100%, height: height / n + 2.5em, columns(n, gutter: gutter, body))
  })
}

// Horizontal page margin; shared with balanced-flow, which needs the text width.
#let margin-x = 13mm
#let margin-top = 13mm

// Multi-page column flow whose LAST page is balanced (Typst fills columns one after another, which
// leaves the last page with full left and empty right columns). A breakable block of total height
// natural/n spreads over the pages, so the last page only gets the remainder, split evenly across the
// columns. Column breaks waste some space (sticky headings, unbreakable boxes): if the text overflows,
// the next layout pass grows the block (twice at most); if it still overflows, plain columns are used
// (they cannot overflow). Typst allows five layout passes, so this must settle quickly.
// Uses fixed labels: once per document.
#let balanced-flow(n, gutter, body) = if n <= 1 { body } else {
  context {
    let em = 1em.to-absolute()
    let col = (page.width - 2 * margin-x - gutter * (n - 1)) / n
    let natural = measure(block(width: col, body)).height
    // State of the previous pass: (mode, extra),
    // mode "balanced" | "grown" | "grown-more" | "shrunk" | "plain".
    // Column breaks waste space (sticky heads move along, boxes don't split); budget for it per page.
    let pages = calc.ceil(natural / n / (page.height - 30mm)) + 1
    let initial = pages * 4 * em // tuned on real editions: settles in the first pass for all themes
    let prev = query(<bflow-state>).at(0, default: (value: ("balanced", initial))).value
    let (mode, extra) = prev
    let ends = query(<bflow-end>)
    let afters = query(<bflow-after>)
    if mode != "plain" and ends.len() > 0 and afters.len() > 0 {
      let e = ends.first().location().position()
      let a = afters.first().location().position()
      // The end marker sits below the block's bottom: the text overflowed in the last column.
      if e.page == a.page and e.y + 0.5 * em > a.y {
        (mode, extra) = if mode == "balanced" {
          ("grown", extra + (e.y - a.y) / n + 3 * em)
        } else if mode == "grown" {
          ("grown-more", extra + (e.y - a.y) + 6 * em)
        } else { ("plain", extra) }
      } else if e.page < a.page and mode != "shrunk" {
        // The text ended a page earlier: the block only spills empty space onto a page of its own.
        // Cut that part off (once; if the text then overflows, plain columns take over).
        (mode, extra) = ("shrunk", extra - (a.y - margin-top) - em)
      }
    }
    [#metadata((mode, extra))<bflow-state>]
    if mode == "plain" {
      columns(n, gutter: gutter, [#body#metadata(none)<bflow-end>])
    } else {
      block(
        height: natural / n + extra + 2 * em,
        breakable: true,
        below: 0pt,
        columns(n, gutter: gutter, [#body#metadata(none)<bflow-end>]),
      )
    }
    [#metadata(none)<bflow-after>]
  }
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

#let body-with-dropcap(t, ps, lines) = if t.drop-lines == 0 { paragraphs(ps) } else {
  first-with-dropcap(t, ps, lines)
  if ps.len() > 1 { parbreak(); paragraphs(ps.slice(1)) }
}

#let qr(t, url, l, size: 1.5cm) = if url != none {
  grid(
    columns: (auto, 1fr),
    gutter: 5pt,
    align: horizon,
    box(tiaoma.qrcode(url, width: size, alt: l.qr-alt + " " + url)),
    text(font: if t.modern { t.label-font } else { t.body-font }, size: t.body-size * 0.8, fill: t.muted, l.to-original),
  )
}

// "Was bisher geschah": the reporter's running memory of a story, printed as a framed box.
#let background-box(t, s, l) = {
  let bg = s.at("background", default: none)
  if bg != none {
    let content = [
      #set par(justify: true)
      #set text(size: t.body-size * 0.92)
      #label-text(t, l.background, size: t.body-size * 1.2, fill: if t.modern { t.accent } else { none }) \
      #paragraphs(bg)
    ]
    if t.modern {
      block(width: 100%, above: 0.6em, below: 0.8em, fill: t.tint, inset: 7pt, stroke: (left: 2.5pt + t.accent), content)
    } else {
      block(width: 100%, above: 0.6em, below: 0.8em, double-box(t, content))
    }
  }
}

// ---------------------------------------------------------------------------------------------
// Stories
// ---------------------------------------------------------------------------------------------

// Picture, headline, deck and source line are sticky blocks: they never end up alone at a column foot.
#let story-head(t, s, l, level: 3) = {
  picture(t, s, l)
  kicker(t, s)
  {
    set text(size: t.story-sizes.at(s.at("size", default: "medium")))
    heading(level: level, s.headline)
  }
  if s.at("subhead", default: none) != none { deck(t, s.subhead) }
  meta-line(t, s, l)
}

#let story(t, s, l, level: 3) = block(width: 100%, breakable: true, below: 1.4em)[
  #story-head(t, s, l, level: level)
  #body-with-dropcap(t, s.body, t.drop-lines)
  #background-box(t, s, l)
  #qr(t, s.at("url", default: none), l, size: 1.2cm)
  #v(0.2em)
  #separator(t)
]

// `wide`: span the picture across the story (see `ausgabe`, which checks that it leaves room below).
#let lead-story(t, s, l, wide: false) = block(width: 100%, below: 1em)[
  #kicker(t, s)
  #{
    set text(size: t.lead-size)
    heading(level: 2, s.headline)
  }
  #if s.at("subhead", default: none) != none { deck(t, s.subhead) }
  // Large pictures span the story; others go to the sidebar (or above the text) at column width.
  #if t.lead-sidebar [
    #grid(
      columns: (2.2fr, 1fr),
      gutter: 6mm,
      [
        #if wide { picture(t, s, l, min-ratio: 16 / 9) }
        #meta-line(t, s, l)
        #balanced-columns(t.lead-columns, 5mm, body-with-dropcap(t, s.body, t.drop-lines + 1))
      ],
      [
        #if not wide { picture(t, s, l) }
        #background-box(t, s, l)
        #qr(t, s.at("url", default: none), l)
      ],
    )
  ] else [
    #if wide { picture(t, s, l, min-ratio: 16 / 9) } else {
      block(width: 60%, picture(t, s, l))
    }
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

// e-paper masthead: no frames; edition and weather as quiet side notes, thick and thin rule below,
// the sections as a coloured index line.
#let masthead-modern(t, ed, l) = {
  let m = ed.masthead
  let e = ed.edition
  let w = ed.at("weather", default: none)
  let side(body) = par(justify: false, text(font: t.label-font, size: 8pt, fill: t.muted, hyphenate: false, body))
  grid(
    columns: (1fr, auto, 1fr),
    gutter: 4mm,
    align: (left + bottom, center + bottom, right + bottom),
    side[
      #text(weight: "semibold", fill: t.ink)[#l.edition-for #e.reader] \
      #l.edition-no #e.number · #l.price
    ],
    stack(
      dir: ltr,
      spacing: 3mm,
      align(horizon, image("/assets/brand/rider.svg", height: t.masthead-size * 0.85, alt: "Eilkurier Logo: galoppierender Kurierreiter")),
      align(horizon, box(text(font: t.masthead-font, size: t.masthead-size, weight: "black", fill: t.ink, hyphenate: false, heading(level: 1, outlined: false, m.title)))),
    ),
    side(if w != none [
      #text(weight: "semibold", fill: t.ink)[#l.weather #w.place] \
      #w.summary · #w.temp_min° / #w.temp_max° C
    ]),
  )
  v(1mm)
  grid(
    columns: (1fr, auto, 1fr),
    align: (left, center, right),
    label-text(t, e.date_label, size: 11pt),
    label-text(t, m.slogan, size: 11pt, fill: t.accent),
    label-text(t, m.region + " · " + m.since, size: 11pt),
  )
  v(-1mm)
  line(length: 100%, stroke: 2pt + t.ink)
  v(-3.2mm)
  line(length: 100%, stroke: 0.5pt + t.ink)
  v(-1mm)
  align(center, ed.sections.map(sec => label-text(t, sec, size: 12pt, fill: section-color(t, sec))).join(h(5mm)))
  v(-1mm)
  line(length: 100%, stroke: 0.5pt + t.rule)
  v(3mm)
}

#let masthead(t, ed, l) = if t.modern { masthead-modern(t, ed, l) } else {
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

#let section-title(t, title) = if t.modern {
  block(below: 0.6em, width: 100%, sticky: true, {
    line(length: 100%, stroke: 2pt + t.ink)
    v(-1pt)
    label-text(t, title, size: t.body-size * 1.6)
  })
} else { block(below: 0.5em, width: 100%, sticky: true, {
  double-rule(t)
  v(-2pt)
  align(center, label-text(t, title, size: t.body-size * 1.6))
  v(-6pt)
  line(length: 100%, stroke: 0.7pt + t.ink)
}) }

#let briefs(t, items, l) = if items.len() > 0 {
  block(width: 100%, breakable: true, below: 1.4em)[
    #section-title(t, l.briefs)
    #for b in items [
      #block(sticky: true, below: 0.3em, text(font: t.head-font, weight: t.head-weight, size: t.body-size * 1.25, if t.head-upper { upper(b.headline) } else { b.headline }))
      #b.text #text(fill: t.muted, style: "italic", size: t.body-size * 0.85)[(#b.source)]
      #v(0.3em)
    ]
  ]
}

#let family(t, items, l) = if items.len() > 0 {
  block(width: 100%, breakable: true, below: 1.4em)[
    #section-title(t, l.family)
    #for f in items [
      #par(justify: false, text(font: if t.modern { t.head-font } else { t.deck-font }, style: "italic", size: t.body-size * 1.15)[„#f.text“])
      #align(right, text(fill: t.muted, size: t.body-size * 0.9)[— #f.from])
    ]
  ]
}

#let calendar-section(t, items, l) = if items.len() > 0 {
  block(width: 100%, breakable: true, below: 1.4em)[
    #section-title(t, l.calendar)
    #set par(justify: false)
    #for c in items [
      #label-text(t, c.when, size: t.body-size * 1.1) \
      #c.what
      #v(0.2em)
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
    margin: (x: margin-x, top: margin-top, bottom: 17mm),
    // Paper tint looks lovely on screens and tablets; switch it off when printing on real paper.
    fill: if tint { t.paper } else { none },
    background: if not t.modern {
      place(top + left, dx: 6mm, dy: 6mm, rect(width: 100% - 12mm, height: 100% - 12mm, stroke: 0.8pt + t.ink))
      place(top + left, dx: 7.4mm, dy: 7.4mm, rect(width: 100% - 14.8mm, height: 100% - 14.8mm, stroke: 0.8pt + t.ink))
    },
    footer: context {
      set text(size: 8pt, fill: t.muted)
      set text(font: t.label-font) if t.modern
      line(length: 100%, stroke: 0.5pt + if t.modern { t.rule } else { t.ink })
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
  show heading.where(level: 2).or(heading.where(level: 3)): it => block(width: 100%, above: 0.4em, below: 0.45em, sticky: true, align(if t.modern { left } else { center }, par(justify: false, leading: if t.modern { 0.3em } else { 0.35em }, text(
    font: t.head-font,
    weight: t.head-weight,
    fill: t.ink,
    hyphenate: it.level > 2 and not t.modern, // never break the lead headline; e-paper heads never
    if t.head-upper { upper(it.body) } else { it.body },
  ))))

  masthead(t, ed, l)

  if ed.at("lead", default: none) != none {
    // A full-width lead picture only when a strip for the columns stays free below the lead,
    // otherwise the columns would start on page 2 (the sidebar has room to spare anyway).
    context {
      let wide = wide-picture(ed.lead)
      if wide {
        let height = measure(block(width: page.width - 2 * margin-x, lead-story(t, ed.lead, l, wide: true))).height
        // e-paper heads are short (no drop caps), so a narrower strip still takes a story.
        wide = page.height - 17mm - here().position().y - height >= if t.modern { 4.5cm } else { 8cm }
      }
      lead-story(t, ed.lead, l, wide: wide)
    }
    if t.modern { line(length: 100%, stroke: 1pt + t.ink) } else { double-rule(t) }
    v(2mm)
  }

  // Without a lead story the stories move up one heading level (PDF/UA forbids skipping levels).
  let level = if ed.at("lead", default: none) == none { 2 } else { 3 }
  let stories = ed.at("stories", default: ())
  // Typst moves the whole column flow to the next page when its first sticky head (picture + headline)
  // does not fit below the lead. Then a story without a picture opens the columns, like on a real page.
  // The room is measured at a marker before the flow (inside it, the flow's own jump would hide it).
  // A zero-height block: a bare marker would travel along with the flow when that moves.
  block(height: 0pt, above: 0pt, below: 0pt)[#metadata(none)<flow-start>]
  let stories = context {
    let col = (page.width - 2 * margin-x - 5mm * (t.columns - 1)) / t.columns
    let start = query(<flow-start>).first().location().position()
    let room = page.height - 17mm - start.y
    let order = stories
    if stories.len() > 1 and "image" in stories.first() {
      // The head sticks to the first paragraph; with a drop cap that whole paragraph is unbreakable.
      let first = stories.first()
      let opening = if t.drop-lines > 0 { first-with-dropcap(t, first.body, t.drop-lines) } else { v(4 * t.body-size) }
      let head = measure(block(width: col, { story-head(t, first, l, level: level); opening })).height
      if head + t.body-size > room {
        // Stories without a picture fill the strip below the lead (every column of it), then the rest.
        let (front, rest, used) = ((), (), 0pt)
        for s in stories {
          if "image" not in s and used < t.columns * room {
            front.push(s)
            used += measure(block(width: col, story(t, s, l, level: level))).height
          } else { rest.push(s) }
        }
        order = front + rest
      }
    }
    for s in order { story(t, s, l, level: level) }
  }
  balanced-flow(t.columns, 5mm)[
    #stories
    #if ed.at("lead", default: none) == none and ed.at("stories", default: ()).len() == 0 {
      text(style: "italic", fill: t.muted, l.quiet-day)
    }
    #briefs(t, ed.at("briefs", default: ()), l)
    #calendar-section(t, ed.at("calendar", default: ()), l)
    #family(t, ed.at("family", default: ()), l)
    #almanac(t, ed.at("almanac", default: none), l)
  ]
}
