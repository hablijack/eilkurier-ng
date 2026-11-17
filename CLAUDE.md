# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Eilkurier-NG: a personal newspaper reporter for one family (6 readers). It collects sources, fetches full article
text, lets a small local LLM summarise and track stories ("Was bisher geschah"), and typesets one PDF edition per
reader per day, delivered via Telegram/e-mail. Design, decisions and roadmap: `docs/architektur.md` (German).
The project language is German (docs, UI, editions). Code, identifiers and code comments are English.

## Commands

```bash
uv sync                                         # install (Python 3.13, uv-managed)
uv run pytest                                   # all tests
uv run pytest tests/test_render.py::test_english_edition_renders   # single test
uv run ruff check . && uv run ruff format .     # lint + format (CI runs `ruff format --check`)
uv run eilkurier render-sample --theme grossdruck -o out.pdf        # typeset the sample edition
uv run uvicorn eilkurier.app:create_app --factory --reload --port 8080   # API, docs at /api/v1/docs
docker build -t eilkurier-ng:dev .              # image; the build pre-fetches Typst packages
```

## Architecture

- **Pipeline (planned, see docs):** collect → full text (trafilatura) → enrich once per article on the Jetson
  (summary/facts/embedding) → bundle into stories → per-reader selection (embeddings, no LLM) → per-reader
  editing (LLM) → typeset → deliver. Only steps 3 and 6 use the LLM. Keep LLM tasks small and structured
  (JSON output, source text in context), because the target model is ~4B parameters.
- **Deployment constraints:** Docker Compose on a Raspberry Pi (arm64, 8 GB, already under load) plus an
  NVIDIA Jetson Orin Nano 8 GB running Ollama (OpenAI-compatible API) for the LLM and embeddings. Never run
  models on the Pi. Home network only. `app` and the future `worker` share one image. Containers are stateless
  and run with a read-only root FS as UID 10001: any state goes to Postgres (pgvector, also used as the job
  queue). Don't add Redis or a broker. Images must build for `linux/arm64` and `linux/amd64`.
- **Edition JSON is the contract** between editing and typesetting. `layout/sample/edition.json` is the
  reference document. `layout/main.typ` reads it from `sys.inputs.edition` (falling back to the sample), and
  `src/eilkurier/render.py` passes it in via `typst.compile(..., sys_inputs=...)`. If you change the schema,
  update the sample, the docs section and the tests together.
- **Typesetting** uses the `typst` Python package (no Typst CLI needed). Compile root is the repo root (or
  `EILKURIER_RESOURCE_ROOT`), so layout paths like `/assets/brand/rider.svg` are root-absolute. Fonts come
  only from `assets/fonts/`. Typst Universe packages (`droplet` for drop caps, `tiaoma` for QR codes) are
  downloaded on first compile; the Dockerfile warms that cache.
- **Themes** are dicts in `layout/themes.typ` (`klassisch`, `feuilleton`, `grossdruck`), each derived from
  `base`. Fixed print labels live in `layout/i18n.typ` per language (`edition.lang`).

## Layout gotchas (Typst)

- Every PDF is rendered as **PDF/UA-1**, and Typst fails the compile on violations. Every image needs `alt`.
  Heading levels must not skip: the masthead title is level 1, the lead story level 2, stories level 3 (level 2
  when there is no lead). The tests cover the edition without optional sections for this reason.
- Typst does not balance columns; `balanced-columns` measures the content and caps the height.
- `droplet`'s drop cap block is unbreakable, so only the first paragraph goes into `dropcap` and the rest
  flows normally. Story headline, deck and source line are `sticky` blocks so they stay with the text.
- Text colours must keep ≥ 4.5:1 contrast against the paper tint `#f9f7f1`.
- To check a layout change visually, render PNGs:
  `typst.compile("layout/main.typ", root=".", font_paths=["assets/fonts"], format="png", ppi=110, output="page-{p}.png")`.

## Repo & CI

GitHub `eilkurier-ng`. CircleCI runs ruff and pytest on every branch. On `main` it builds the multi-arch image
via buildx/QEMU and pushes `hablijack/eilkurier-ng:latest` and `:<sha7>` (needs project env vars
`DOCKERHUB_USERNAME` and `DOCKERHUB_PASSWORD`). The sibling directories `../eilkurier*` are the legacy
2018–2022 implementation. They are reference material only: the masthead and newspaper styles came from
`../eilkurier-backend/src/main/resources/META-INF/resources/css/newspaper.css`.
