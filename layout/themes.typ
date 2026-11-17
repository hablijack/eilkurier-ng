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
