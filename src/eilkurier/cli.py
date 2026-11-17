import argparse
from pathlib import Path

from eilkurier.render import EditionRenderer, Theme
from eilkurier.settings import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(prog="eilkurier")
    commands = parser.add_subparsers(dest="command", required=True)

    sample = commands.add_parser("render-sample", help="Typeset the sample edition into a PDF")
    sample.add_argument("--theme", type=Theme, choices=list(Theme), default=Theme.KLASSISCH)
    sample.add_argument("--output", "-o", type=Path, default=Path("eilkurier-beispiel.pdf"))

    args = parser.parse_args()
    if args.command == "render-sample":
        renderer = EditionRenderer(get_settings().resource_root)
        args.output.write_bytes(renderer.render_pdf(renderer.sample_edition(args.theme)))
        print(f"{args.output} ({args.theme.value})")


if __name__ == "__main__":
    main()
