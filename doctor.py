#!/usr/bin/env python3
"""claude-harness kurulum sağlığı. Çıkış: 0 yeşil, 1 kırmızı var, 2 kurulu değil."""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from lib.doctor import checks  # noqa: E402
from lib.doctor.inputs import read_json, state_path  # noqa: E402
from lib.doctor.model import RED, Check, exit_code, format_line  # noqa: E402


def parse_args(argv):
    parser = argparse.ArgumentParser(description="claude-harness kurulum sağlığı")
    parser.add_argument("--home", default=str(Path.home()), help="hedef ev dizini")
    parser.add_argument("--repo", default=str(REPO), help="harness repo kökü (harness.json için)")
    parser.add_argument("--json", action="store_true", help="makine okur çıktı")
    return parser.parse_args(argv)


def emit(items, code, as_json):
    if as_json:
        print(json.dumps({"exit": code, "checks": [c.as_dict() for c in items]}, ensure_ascii=False, indent=2))
    else:
        for item in items:
            print(format_line(item))


def main(argv=None, which=None, run=None):
    args = parse_args(argv)
    path = state_path(args.home)
    if not path.exists():
        emit([Check(RED, "Durum dosyası", f"kurulu değil: {path} yok")], 2, args.json)
        return 2
    state, err = read_json(path)
    if not isinstance(state, dict):
        items = [Check(RED, "Durum dosyası", err or "kök nesne değil")]
        emit(items, 1, args.json)
        return 1
    manifest, merr = read_json(Path(args.repo) / "harness.json")
    if not isinstance(manifest, dict):
        items = [Check(RED, "harness.json", merr or "kök nesne değil")]
        emit(items, 1, args.json)
        return 1
    kwargs = {k: v for k, v in (("which", which), ("run", run)) if v is not None}
    items = [Check("green", "Durum dosyası", "okundu"), *checks.run_all(state, manifest, args.home, **kwargs)]
    code = exit_code(items)
    emit(items, code, args.json)
    return code


if __name__ == "__main__":
    sys.exit(main())
