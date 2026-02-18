#!/usr/bin/env python3
"""
Directory runner for estimate parsing.

Usage:
  python parse_dir.py --in=documents/historical --out=data/historical
  python parse_dir.py --in=one_file.pdf --out=data/outdir
  python parse_dir.py --in=one_file.pdf --out=data/custom_name.json
  python parse_dir.py --in=docs --out=data --debug
"""

import os
import sys
from vip_parser.xactimate import XactimateRoughDraftParser

def main():
    in_arg = "documents/historical"
    out_arg = "data/historical"
    debug = False

    for a in sys.argv[1:]:
        if a.startswith("--in="):  in_arg = a.split("=", 1)[1].strip()
        elif a.startswith("--out="): out_arg = a.split("=", 1)[1].strip()
        elif a == "--debug": debug = True

    if os.path.isdir(in_arg):
        pdfs = [f for f in os.listdir(in_arg) if f.lower().endswith(".pdf")]
        if not pdfs:
            print("No PDFs found.")
            return
        os.makedirs(out_arg, exist_ok=True)
        for pdf in sorted(pdfs):
            parser = XactimateRoughDraftParser(
                input_file=os.path.join(in_arg, pdf),
                output_path=out_arg,
                debug=debug
            )
            parser.run()
    else:
        if not os.path.exists(in_arg):
            print(f"Input not found: {in_arg}")
            return
        parser = XactimateRoughDraftParser(
            input_file=in_arg,
            output_path=out_arg,
            debug=debug
        )
        parser.run()

if __name__ == "__main__":
    main()
