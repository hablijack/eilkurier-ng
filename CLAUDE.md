# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Eilkurier-NG: a personal newspaper reporter for one family (6 readers). It collects sources, fetches full article
text, lets a small local LLM summarise and track stories ("Was bisher geschah"), and typesets one PDF edition per
reader per day, delivered via Telegram/e-mail. Design, decisions and roadmap: `docs/architektur.md` (German).
The project language is German (docs, UI, editions). Code, identifiers and code comments are English.

## Commands

```bash
uv sync                                         # install (Python 3.13, uv-managed)
# DB tests need Postgres+pgvector; without this variable they are skipped:
docker run -d --name ek-pg -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test -p 55432:5432 pgvector/pgvector:pg17
export EILKURIER_TEST_DATABASE_URL=postgresql+psycopg://test:test@localhost:55432/test
uv run pytest                                   # all tests
uv run pytest tests/test_render.py::test_english_edition_renders   # single test
uv run ruff check . && uv run ruff format .     # lint + format (CI runs `ruff format --check`)
uv run eilkurier render-sample --theme grossdruck -o out.pdf        # typeset the sample edition
uv run eilkurier simulator --port 11434         # fake OpenAI-compatible LLM (no GPU), for dev/demo
uv run eilkurier tick                           # one worker pass (collect, fulltext, reporter, editions)
uv run uvicorn eilkurier.app:create_app --factory --reload --port 8080   # API, docs at /api/v1/docs
cd frontend && npm ci && npm run check && npm run dev   # web UI (proxies /api to :8080)
docker build -t eilkurier-ng:dev .              # image (web UI + Python); pre-fetches Typst packages
```

After changing the API: `uv run eilkurier openapi > frontend/openapi.json && (cd frontend && npm run api)`.
`tests/test_api.py::test_web_ui_client_matches_api` fails until you do.

## Architecture

- **Processes:** one image; `app` (FastAPI REST API under `/api/v1` + the static SvelteKit build from
  `EILKURIER_WEB_ROOT`), `worker` (`eilkurier worker`: one loop, 30 s tick, isolated steps: editions/deliveries,
  Telegram poll, collect, fulltext, reporter with a time budget, housekeeping), `migrate` (Alembic, one-shot).
  Compose: `docker-compose.yml`; profile `demo` adds the LLM simulator.
- **Pipeline modules:** `collect.py` (RSS/ICS, trafilatura full text, consent/paywall/scrambled-text rejection)
  → `reporter.py` (enrich once per article; story assignment: embedding/topic candidates, LLM picks one or 0)
  → `edition.py` (per-reader selection without LLM, compose edition JSON) → `render.py` → `deliver.py`
  (Telegram sendDocument / SMTP; bot link codes and letters via getUpdates).
- **The LLM is usually unavailable, and the design must treat that as normal.** Target: Jetson Orin Nano with
  Ollama (`gemma3:4b`, embeddings `embeddinggemma`). Work queues until `GET /v1/models` answers. Editions are
  never delayed: un-enriched articles are typeset extractively and flagged `excerpt`. Strict `json_schema`
  response format, `finish_reason == "stop"`, 429/502/503/504 and transport errors mean "retry later". Numbers
  in LLM output must occur in the source text (`validate_enrichment`). Tests and the demo use the simulator.
- **captiva** (vLLM, Qwen3.8 27B, `http://captiva.fritz.box:8080`, FQDN always) is only an optional trial backend:
  it draws ~800 W and is usually off. It is shared with guitar-vision: **announce to the user before any access
  to captiva** (HTTP or SSH), one request at a time, never change it. Needs
  `EILKURIER_LLM_EXTRA_BODY={"chat_template_kwargs":{"enable_thinking":false}}` and no embedding model.
- **Deployment constraints:** Docker Compose on a Raspberry Pi (arm64, 8 GB, already under load). Never run
  models (or embeddings) on the Pi. Home network only. `app`, `worker` and `migrate` share one image.
  Containers are stateless and run with a read-only root FS as UID 10001: any state goes to Postgres (pgvector, also used as the job
  queue). Don't add Redis or a broker. Images must build for `linux/arm64` and `linux/amd64`.
- **Edition JSON is the contract** between editing, typesetting and the web UI's HTML view
  (`frontend/src/lib/edition.ts`). `layout/sample/edition.json` is the
  reference document. `layout/main.typ` reads it from `sys.inputs.edition` (falling back to the sample), and
  `src/eilkurier/render.py` passes it in via `typst.compile(..., sys_inputs=...)`. If you change the schema,
  update the sample, `edition.ts`, the docs section and the tests together.
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

## Web UI

- `frontend/`: SvelteKit 2 + Svelte 5 runes, adapter-static SPA, typed client via openapi-fetch.
  Strings in `src/lib/i18n.svelte.ts` (de/en, keys typed). Keep it mobile-first and WCAG 2.2 AA: labels on every
  control, ≥ 44 px targets, colour tokens in `app.css` (light + dark). `npm run check` fails on a11y warnings.
  Brand assets are copied from `assets/` by `scripts/sync-assets.mjs`; don't commit copies.

## Repo & CI

GitHub `eilkurier-ng`. CircleCI runs ruff and pytest (with a pgvector service) plus `npm run check`/build on
every branch. On `main` it builds the multi-arch image
via buildx/QEMU and pushes `hablijack/eilkurier-ng:latest` and `:<sha7>` (needs project env vars
`DOCKERHUB_USERNAME` and `DOCKERHUB_PASSWORD`). The sibling directories `../eilkurier*` are the legacy
2018–2022 implementation. They are reference material only: the masthead and newspaper styles came from
`../eilkurier-backend/src/main/resources/META-INF/resources/css/newspaper.css`.
