import argparse
import json
import logging
import warnings
from importlib import resources
from pathlib import Path

from eilkurier.render import EditionRenderer, Theme
from eilkurier.settings import get_settings

# trafilatura pulls in urllib3's optional SOCKS support; we never use it.
warnings.filterwarnings("ignore", message=".*SOCKS support.*")


def _seed_demo() -> None:
    """A demo household: two readers and a few classic feeds, so the system has something to do."""
    from sqlalchemy import select

    from eilkurier.db import Interest, Reader, Source, session_scope
    from eilkurier.deliver import new_link_code

    catalog = json.loads(resources.files("eilkurier").joinpath("catalog.json").read_text("utf-8"))
    wanted = {
        "Tagesschau",
        "heise online News",
        "Golem.de News",
        "Hackaday",
        "GITARRE & BASS",
        "Onetz Weiden",
    }
    with session_scope() as session:
        if session.scalar(select(Reader.id).limit(1)):
            print("database already has readers, nothing seeded")
            return
        sources = [Source(**entry) for entry in catalog if entry["name"] in wanted]
        session.add_all(sources)
        papa = Reader(name="Papa", telegram_link_code=new_link_code(), sources=sources)
        papa.interests = [
            Interest(term=t, weight=w) for t, w in [("Linux", 2), ("Gitarre", 2), ("Raspberry", 1)]
        ]
        oma = Reader(
            name="Oma",
            theme="grossdruck",
            font_scale=1.1,
            story_count=5,
            telegram_link_code=new_link_code(),
            sources=[s for s in sources if s.category in ("Nachrichten", "Region")],
        )
        oma.interests = [Interest(term=t, weight=1) for t in ("Weiden", "Garten", "Wetter")]
        session.add_all([papa, oma])
    print(f"seeded 2 readers and {len(sources)} sources")


def main() -> None:
    parser = argparse.ArgumentParser(prog="eilkurier")
    parser.add_argument("--log-level", default="INFO")
    commands = parser.add_subparsers(dest="command", required=True)

    sample = commands.add_parser("render-sample", help="Typeset the sample edition into a PDF")
    sample.add_argument("--theme", type=Theme, choices=list(Theme), default=Theme.KLASSISCH)
    sample.add_argument("--output", "-o", type=Path, default=Path("eilkurier-beispiel.pdf"))

    commands.add_parser("migrate", help="Apply database migrations (run once before app and worker)")
    commands.add_parser("worker", help="Run the pipeline loop: collect, enrich, build and deliver")
    commands.add_parser("tick", help="Run one pipeline pass and exit (debugging)")
    commands.add_parser("seed-demo", help="Create a demo household (only on an empty database)")
    commands.add_parser("openapi", help="Print the OpenAPI document (for the web UI's generated client)")
    sim = commands.add_parser("simulator", help="Run the language-model simulator (no GPU needed)")
    sim.add_argument("--host", default="0.0.0.0")
    sim.add_argument("--port", type=int, default=11434)

    args = parser.parse_args()
    logging.basicConfig(
        level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("trafilatura").setLevel(logging.WARNING)
    settings = get_settings()

    if args.command == "render-sample":
        renderer = EditionRenderer(settings.resource_root)
        args.output.write_bytes(renderer.render_pdf(renderer.sample_edition(args.theme)))
        print(f"{args.output} ({args.theme.value})")
    elif args.command == "migrate":
        from eilkurier.migrate import upgrade

        upgrade(settings.database_url)
    elif args.command in ("worker", "tick"):
        from eilkurier.worker import Worker

        worker = Worker(settings)
        worker.run_forever() if args.command == "worker" else worker.tick()
    elif args.command == "openapi":
        from eilkurier.app import create_app

        print(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2))
    elif args.command == "seed-demo":
        _seed_demo()
    elif args.command == "simulator":
        import uvicorn

        from eilkurier.simulator import create_app

        uvicorn.run(create_app(), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
