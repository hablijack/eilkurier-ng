// Visual themes for the printed edition. Each reader picks one in their profile.
// "klassisch" is the evolution of the 2022 Eilkurier print style
// (Chomsky masthead, Bebas Neue headlines, paper #f9f7f1, ink #2f2f2f, double rules, drop caps).
//
// Colour contrast: every text colour is checked against `paper` for WCAG AA (>= 4.5:1).

#let base = (
  paper: rgb("#f9f7f1"),
  ink: rgb("#2f2f2f"),
  muted: rgb("#5c5c5c"), // 6.3:1 on paper (the old #8b8b8b was only ~3.3:1)
  accent: rgb("#2f2f2f"),
  masthead-font: "Chomsky",
  masthead-size: 58pt,
  head-font: "Bebas Neue",
  head-weight: "regular",
  head-upper: true,
  deck-font: "Playfair Display",
  body-font: "Libertinus Serif",
  body-size: 9.5pt,
  leading: 0.62em,
  drop-font: "Chomsky",
  drop-lines: 3,
  lead-size: 30pt,
  story-sizes: (large: 19pt, medium: 16pt, small: 13.5pt),
  columns: 4,
  lead-columns: 2,
  lead-sidebar: true, // "Was bisher geschah" next to the lead story instead of below it
  // "modern" switches the layout to the e-paper look (see `epaper` below)
  modern: false,
  label-font: "Bebas Neue",
  label-weight: "regular",
  rule: rgb("#2f2f2f"),
  tint: rgb("#f1ece0"),
  section-colors: (:),
)

#let themes = (
  klassisch: base,
  feuilleton: base + (
    accent: rgb("#6b2f1b"),
    masthead-font: "Playfair Display",
    masthead-size: 50pt,
    head-font: "Playfair Display",
    head-weight: "bold",
    head-upper: false,
    drop-font: "Playfair Display",
    lead-size: 28pt,
    story-sizes: (large: 18pt, medium: 15pt, small: 12.5pt),
    columns: 3,
  ),
  // Today's e-paper: white page, bold serif headlines set left, coloured section kickers, Fira Sans
  // for everything around the text, thin grey rules, no frames, no drop caps.
  epaper: base + (
    modern: true,
    paper: rgb("#fdfdfb"),
    ink: rgb("#1d1f23"),
    muted: rgb("#565c66"), // 6.6:1 on paper
    accent: rgb("#6b2f1b"), // 10.3:1
    rule: rgb("#c9cdd2"),
    tint: rgb("#f3f4f6"),
    masthead-font: "Playfair Display",
    masthead-size: 40pt,
    head-font: "Playfair Display",
    head-weight: "bold",
    head-upper: false,
    deck-font: "Fira Sans",
    label-font: "Fira Sans",
    label-weight: "semibold",
    body-size: 9.5pt,
    drop-lines: 0,
    lead-size: 26pt,
    story-sizes: (large: 15pt, medium: 13pt, small: 11.5pt),
    columns: 4,
    // the web UI's topic colours; all >= 4.5:1 on paper
    section-colors: (
      "Nachrichten": rgb("#b42318"),
      "Region": rgb("#1d6f38"),
      "IT & Technik": rgb("#1d5aa0"),
      "Selbermachen": rgb("#a6460a"),
      "Musik": rgb("#6a3cb8"),
      "Familie": rgb("#6b2f1b"),
    ),
  ),
  // For readers who prefer large print: bigger body text, fewer columns, darker secondary text.
  grossdruck: base + (
    muted: rgb("#3d3d3d"),
    body-size: 13pt,
    leading: 0.7em,
    drop-lines: 2,
    lead-size: 32pt,
    story-sizes: (large: 26pt, medium: 22pt, small: 19pt),
    columns: 2,
    lead-columns: 2,
    lead-sidebar: false,
  ),
)
