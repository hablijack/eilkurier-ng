#!/usr/bin/env python3
"""Cut a release: `scripts/release.py X.Y.Z`.

Sets the version everywhere it is written down (pyproject.toml, uv.lock, frontend/package*.json, the Compose
files), turns the "Unreleased" changelog section into "X.Y.Z – today", commits "Release X.Y.Z" and creates the
annotated tag vX.Y.Z. Nothing is pushed: `git push --follow-tags` afterwards; CircleCI then builds and pushes
the Docker images X.Y.Z, X.Y, X and latest.
"""

import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")
REPO = "https://github.com/hablijack/eilkurier-ng"


def die(message: str) -> None:
    sys.exit(f"release: {message}")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def current_version() -> str:
    match = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.M)
    if not match:
        die("no version in pyproject.toml")
    return match.group(1)


def replace(path: str, pattern: str, new: str, count: int = 1) -> None:
    file = ROOT / path
    text, n = re.subn(pattern, new, file.read_text(), count=count, flags=re.M)
    if n != count:
        die(f"{path}: expected {count} match(es) for {pattern!r}, found {n}")
    file.write_text(text)


def bump_package_json(path: str, version: str) -> None:
    file = ROOT / path
    data = json.loads(file.read_text())
    data["version"] = version
    if "packages" in data and "" in data["packages"]:  # package-lock.json: the root package
        data["packages"][""]["version"] = version
    indent = "\t" if file.read_text().startswith("{\n\t") else 2
    file.write_text(json.dumps(data, indent=indent, ensure_ascii=False) + "\n")


def changelog(version: str, previous: str) -> None:
    file = ROOT / "CHANGELOG.md"
    text = file.read_text()
    unreleased = re.search(r"^## \[Unreleased\]\n(.*?)(?=^## \[)", text, re.M | re.S)
    if not unreleased or not unreleased.group(1).strip():
        die('CHANGELOG.md: the "Unreleased" section is empty – describe the changes first')
    today = datetime.date.today().isoformat()
    text = text.replace("## [Unreleased]\n", f"## [Unreleased]\n\n## [{version}] – {today}\n", 1)
    text = re.sub(
        r"^\[Unreleased\]: .*$",
        f"[Unreleased]: {REPO}/compare/v{version}...HEAD\n"
        f"[{version}]: {REPO}/compare/v{previous}...v{version}",
        text,
        count=1,
        flags=re.M,
    )
    file.write_text(text)


def main() -> None:
    if len(sys.argv) != 2 or not SEMVER.fullmatch(sys.argv[1]):
        die("usage: scripts/release.py X.Y.Z (semantic version, no leading v)")
    version = sys.argv[1]
    previous = current_version()
    as_tuple = lambda v: tuple(int(x) for x in v.split("."))  # noqa: E731
    if as_tuple(version) <= as_tuple(previous):
        die(f"{version} is not newer than the current version {previous}")
    if git("rev-parse", "--abbrev-ref", "HEAD") != "main":
        die("releases are cut on main")
    if git("status", "--porcelain"):
        die("working tree is not clean")
    if git("tag", "--list", f"v{version}"):
        die(f"tag v{version} exists already")

    replace("pyproject.toml", r'^version = "[^"]+"', f'version = "{version}"')
    bump_package_json("frontend/package.json", version)
    bump_package_json("frontend/package-lock.json", version)
    image = "hablijack/eilkurier-ng"
    replace("deploy/omv/eilkurier.yml", rf"{image}:[0-9][^\s]*", f"{image}:{version}")
    replace("docker-compose.yml", r"EILKURIER_VERSION:-[^}]+", f"EILKURIER_VERSION:-{version}")
    changelog(version, previous)
    subprocess.run(["uv", "lock", "--quiet"], cwd=ROOT, check=True)

    git("add", "-A")
    git("commit", "-m", f"Release {version}")
    git("tag", "-a", f"v{version}", "-m", f"Eilkurier {version}")
    print(f"Release {version} committed and tagged v{version}.")
    print("Publish it with:  git push --follow-tags")


if __name__ == "__main__":
    main()
