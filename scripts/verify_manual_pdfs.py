"""
Verify manually-downloaded PDFs:
  - Check filename matches the paper_XX.pdf convention
  - Check the file is a real PDF (%PDF magic bytes)
  - Check size is reasonable (> 50 KB)
  - Report which papers are now "covered" vs still missing

Run this after you drop PDFs into audit/pdfs/.

Usage:
  python3 scripts/verify_manual_pdfs.py
"""

import json
import glob
import os
from pathlib import Path

ROOT     = Path(__file__).parent.parent
PDF_DIR  = ROOT / "audit/pdfs"
RESOLVER = ROOT / "audit/resolver_cache"


def is_valid_pdf(path: Path) -> tuple[bool, str]:
    if not path.exists(): return False, "not found"
    size = path.stat().st_size
    if size < 50_000: return False, f"too small ({size // 1024} KB)"
    with open(path, "rb") as f:
        head = f.read(5)
    if not head.startswith(b"%PDF"): return False, f"bad magic: {head[:5]}"
    return True, f"{size // 1024} KB"


def main():
    all_paper_ids = set()
    for cf in sorted(RESOLVER.glob("paper_*.json")):
        all_paper_ids.add(cf.stem)

    present_pdfs = {}
    issues = []
    for p in PDF_DIR.glob("paper_*.pdf"):
        ok, reason = is_valid_pdf(p)
        if ok:
            present_pdfs[p.stem] = reason
        else:
            issues.append((p.stem, reason))

    # Bad filenames?
    weird = [p.name for p in PDF_DIR.glob("*.pdf")
              if not p.name.startswith("paper_")]

    print(f"Valid PDFs in audit/pdfs/: {len(present_pdfs)} / {len(all_paper_ids)}")
    print(f"Coverage: {len(present_pdfs) / len(all_paper_ids) * 100:.0f}%")
    print()
    if issues:
        print(f"⚠️  {len(issues)} invalid PDF(s) (bad size / not PDF magic):")
        for pid, reason in issues:
            print(f"  - {pid}.pdf: {reason}")
        print()
    if weird:
        print(f"⚠️  {len(weird)} file(s) with wrong name (not paper_XX.pdf):")
        for w in weird:
            print(f"  - {w}  ← rename to paper_XX.pdf")
        print()

    # Still missing — show critical ones first
    abs_by_id = {r["paper_id"] for r in
                  json.loads((ROOT / "audit/real_abstracts.json").read_text())
                  if r.get("real_abstract")}
    still_missing = sorted(all_paper_ids - set(present_pdfs.keys()),
                            key=lambda s: int(s.split("_")[1]))
    critical_missing = [p for p in still_missing if p not in abs_by_id]
    nice_missing = [p for p in still_missing if p in abs_by_id]

    print(f"Still missing ({len(still_missing)}):")
    print(f"  🔴 CRITICAL (no abstract either): {len(critical_missing)}")
    if critical_missing:
        print(f"     {', '.join(critical_missing[:20])}"
              + (f" ... +{len(critical_missing)-20} more" if len(critical_missing) > 20 else ""))
    print(f"  🟡 Nice-to-have (abstract available): {len(nice_missing)}")


if __name__ == "__main__":
    main()
