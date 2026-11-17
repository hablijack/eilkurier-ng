// Entry point. The renderer passes the edition as JSON via `sys.inputs.edition`;
// without it (e.g. when editing the layout) the sample edition is used.
#import "eilkurier.typ": ausgabe

#let raw = sys.inputs.at("edition", default: none)
#let edition = if raw == none { json("sample/edition.json") } else { json(bytes(raw)) }

#ausgabe(edition)
