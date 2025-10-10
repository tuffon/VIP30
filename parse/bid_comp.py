#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
bid_comp.py
-----------
Run the StateFarm parser over documents/statefarm/*.pdf and write outputs by default.

Usage:
  python parse/bid_comp.py
  python parse/bid_comp.py --out data/statefarm/ --debug
  python parse/bid_comp.py --path "documents/statefarm/*.pdf"
"""

import os
import sys
import glob
import argparse
from typing import List

from statefarm_parse import StateFarmParser


def _print_summary(file_name: str, payload: dict, debug: bool) -> None:
    print(f"\n▶ {file_name}")
    cov = payload.get("coverage_table", []) or []
    if not cov:
        print("  (no coverage summaries found)")
    else:
        print("  Coverage RCV / Net Payment:")
        for row in cov:
            name = (row.get("coverage") or "Coverage")[:70]
            rcv = row.get("replacement_cost_value")
            net = row.get("net_payment")
            rcv_s = rcv if isinstance(rcv, str) else ("—" if rcv is None else f"{rcv}")
            net_s = net if isinstance(net, str) else ("—" if net is None else f"{net}")
            print(f"    - {name:70s}  RCV: {rcv_s:>12}  Net: {net_s:>12}")

    if debug:
        v = payload.get("validations", {})
        if v:
            print("  Validations:")
            import json as _json
            print(_json.dumps(v, indent=2))


def main():
    ap = argparse.ArgumentParser(description="Run State Farm parser over a folder of PDFs")
    ap.add_argument("--path", default="documents/statefarm/*.pdf", help="Glob path to State Farm PDFs")
    # Default to a directory and include os.sep to make dir intent explicit on all platforms
    ap.add_argument("--out", default=f"data{os.sep}statefarm{os.sep}", help="Directory to write JSON and .out files")
    ap.add_argument("--debug", action="store_true", help="Verbose validations output")
    args = ap.parse_args()

    # Ensure output directory exists (parser also ensures this, but we do it here too)
    if args.out:
        trailing_sep = args.out.endswith("/") or args.out.endswith("\\")
        # If trailing separator OR no file extension -> treat as directory
        if trailing_sep or not os.path.splitext(args.out)[1]:
            os.makedirs(args.out, exist_ok=True)

    files: List[str] = sorted(glob.glob(args.path))
    if not files:
        print(f"No PDFs matched: {args.path}")
        sys.exit(1)

    for pdf in files:
        try:
            parser = StateFarmParser(
                input_file=pdf,
                output_path=args.out,   # Parser writes <name>.statefarm.json and <name>.out
                debug=args.debug,
                skip_header_pages=2
            )
            payload = parser.run()
            _print_summary(os.path.basename(pdf), payload, args.debug)
        except Exception as e:
            print(f"[error] {pdf}: {e}", file=sys.stderr)
            if args.debug:
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    main()
