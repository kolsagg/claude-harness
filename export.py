#!/usr/bin/env python3
"""Kaynak makinede çalışır: canlı Claude Code kurulumundan payload/ üretir.

Scrub sıfır bulgu vermezse payload/ yenilenir; aksi halde eski payload'a dokunulmaz.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from lib.exporter.pipeline import run_export  # noqa: E402


def parse_args(argv):
    p = argparse.ArgumentParser(description="claude-harness export")
    p.add_argument("--local-config", default=str(ROOT / "export.local.json"))
    p.add_argument("--source-home", default=str(Path.home()))
    p.add_argument("--out", default=str(ROOT / "payload"))
    p.add_argument("--check-only", action="store_true", help="mevcut payload'u tara, yazma")
    p.add_argument("--tree", action="store_true",
                   help="git ağacının tamamını tara (tek başına: yalnız ağaç; --check-only ile: payload + ağaç)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    return run_export(
        ROOT, Path(args.source_home), Path(args.out), Path(args.local_config), args.check_only, tree=args.tree
    )


if __name__ == "__main__":
    sys.exit(main())
