"""Command line entry point: `cvgruplac-json`."""

import argparse

from . import __version__


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="cvgruplac-json",
        description="Link the JSONs of cvlac-json and gruplac-json: one id per product, in both directions.",
    )
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    ap.parse_args(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
