"""Check that a Builder or Fixer pull request only touches one Actor's folder.

    python -m factory.builder.scope --base origin/main          # files from git diff base...HEAD
    python -m factory.builder.scope --files a.py actors/x/y.py  # explicit list (tests)

Exits 1 and names the offending files when anything outside a single
actors/<name>/ folder changed, so the PR shows a failing check before review.
"""

import argparse
import subprocess
import sys


def check_scope(files: list[str]) -> tuple[str | None, list[str]]:
    """Return (actor name, files outside it). The name is None when no Actor folder was touched."""
    actor_dirs = {f.split("/")[1] for f in files if f.startswith("actors/") and f.count("/") >= 2}
    if len(actor_dirs) != 1:
        return None, sorted(files) if len(actor_dirs) > 1 or not actor_dirs else []
    name = actor_dirs.pop()
    outside = sorted(f for f in files if not f.startswith(f"actors/{name}/"))
    return name, outside


def changed_files(base: str) -> list[str]:
    out = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"], capture_output=True, text=True, check=True)
    return [line for line in out.stdout.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m factory.builder.scope", description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--files", nargs="*")
    args = parser.parse_args(argv)
    files = args.files if args.files is not None else changed_files(args.base)
    name, outside = check_scope(files)
    if name is None:
        print("::error title=Scope::A Builder pull request must change exactly one actors/<name>/ folder.")
        for f in outside:
            print(f"  {f}")
        return 1
    if outside:
        print(f"::error title=Scope::Only actors/{name}/ may change; these files are outside it:")
        for f in outside:
            print(f"  {f}")
        return 1
    print(f"Scope OK: only actors/{name}/ changed ({len(files)} files).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
