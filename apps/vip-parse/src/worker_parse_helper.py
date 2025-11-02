import json
import os
import sys
import tempfile
import logging
from pathlib import Path


def _extract_recap(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {}
    recaps = payload.get("recaps_and_summaries") or {}
    if isinstance(recaps, dict) and "recap_by_category" in recaps:
        rb = recaps.get("recap_by_category")
        return rb if isinstance(rb, dict) else {}
    rb = payload.get("recap_by_category")
    return rb if isinstance(rb, dict) else {}


def main(pdf_path: str) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
    os.environ.setdefault("FAST_RECAP_ONLY", "1")

    # Lazy-import heavy parser here so the parent process doesn't retain it
    from parse.xactimate import XactimateRoughDraftParser

    out_dir = Path(tempfile.mkdtemp(prefix="parse-helper-"))
    try:
        parser = XactimateRoughDraftParser(pdf_path, str(out_dir), debug=False)
        parser.run()

        base = out_dir / Path(pdf_path).stem
        recap_file = Path(f"{base}.recap.json")
        if recap_file.exists():
            with recap_file.open("r", encoding="utf-8") as f:
                recap = json.load(f)
            # recap is {"recap_by_category": {...}} per writer
            if isinstance(recap, dict) and "recap_by_category" in recap:
                print(json.dumps(recap["recap_by_category"]))
                return

        json_file = Path(f"{base}.json")
        if json_file.exists():
            with json_file.open("r", encoding="utf-8") as f:
                payload = json.load(f)
            print(json.dumps(_extract_recap(payload)))
            return

        # Nothing produced; emit empty
        print(json.dumps({}))
    finally:
        try:
            for root, _dirs, files in os.walk(out_dir, topdown=False):
                for name in files:
                    try:
                        os.remove(Path(root) / name)
                    except OSError:
                        pass
            os.removedirs(out_dir)
        except OSError:
            pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("{}" )
        sys.exit(0)
    main(sys.argv[1])


