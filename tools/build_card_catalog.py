#!/usr/bin/env python3
"""Create a provenance-first, review-gated candidate catalog from card PDFs.

The PDFs are screenshot exports, so OCR output is deliberately stored as a
candidate.  This script never promotes OCR text to verified card data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path


FACTIONS = {
    "通用.pdf": ("common", "通用"),
    "天廷阵营.pdf": ("tianting", "天廷"),
    "太阳城阵营.pdf": ("sun_city", "太阳城"),
    "奥林匹斯阵营.pdf": ("olympus", "奥林匹斯"),
    "彼界阵营.pdf": ("otherworld", "彼界"),
    "阿斯加德阵营.pdf": ("asgard", "阿斯加德"),
    "高天原阵营.pdf": ("takamagahara", "高天原"),
}
RULES_FILE = "规则手册2.0.pdf"
CARD_CROP = {"x": 0.134, "y": 0.032, "width": 0.732, "height": 0.747}
OFFICIAL_ID = re.compile(r"S\d{2}-[0-9A-Z]{3,8}", re.IGNORECASE)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def page_count(path: Path) -> int:
    output = subprocess.check_output(["pdfinfo", str(path)], text=True)
    match = re.search(r"^Pages:\s+(\d+)$", output, re.MULTILINE)
    if not match:
        raise RuntimeError(f"cannot read page count: {path}")
    return int(match.group(1))


def ocr_page(pdf: Path, page: int, scratch: Path) -> str:
    """Return best-effort local OCR for one card page, without retaining images."""

    prefix = scratch / "page"
    subprocess.run(
        ["pdftoppm", "-f", str(page), "-l", str(page), "-r", "200", "-png", str(pdf), str(prefix)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    image = next(scratch.glob("page-*.png"))
    result = subprocess.run(
        ["tesseract", str(image), "stdout", "-l", "chi_sim+eng", "--psm", "12"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def candidate_card(pdf: Path, page: int, faction: tuple[str, str], text: str) -> dict[str, object]:
    slug, label = faction
    official_match = OFFICIAL_ID.search(text)
    official_id = official_match.group(0).upper() if official_match else None
    # The source-derived ID remains stable even when OCR cannot read the printed ID.
    card_id = official_id or f"candidate-{slug}-{page:03d}"
    return {
        "card_id": card_id,
        "official_card_id": official_id,
        "name": None,
        "faction": {"id": slug, "label": label},
        "card_type": None,
        "cost": None,
        "stats": {},
        "text": None,
        "tags": [],
        "effect": {"dsl_version": "0.1", "implementation_status": "not_started", "operations": []},
        "ocr": {"engine": "tesseract chi_sim+eng psm12", "raw_text": text, "field_confidence": {}},
        "review": {"status": "needs_review", "reviewed_fields": [], "notes": "OCR candidate; not trainable."},
        "source": {
            "pdf_path": str(pdf),
            "pdf_sha256": sha256(pdf),
            "page": page,
            "crop": CARD_CROP,
        },
    }


def build_cards(source_dir: Path, with_ocr: bool, ocr_workers: int) -> list[dict[str, object]]:
    cards: list[dict[str, object]] = []
    jobs: list[tuple[Path, int, tuple[str, str]]] = []
    for filename, faction in FACTIONS.items():
        pdf = source_dir / filename
        if not pdf.exists():
            continue
        for page in range(3, page_count(pdf) + 1):
            jobs.append((pdf, page, faction))

    def read(job: tuple[Path, int, tuple[str, str]]) -> tuple[Path, int, tuple[str, str], str]:
        pdf, page, faction = job
        if not with_ocr:
            return pdf, page, faction, ""
        with tempfile.TemporaryDirectory(prefix="legion12-ocr-") as temp_dir:
            return pdf, page, faction, ocr_page(pdf, page, Path(temp_dir))

    with ThreadPoolExecutor(max_workers=ocr_workers) as executor:
        for pdf, page, faction, text in executor.map(read, jobs):
            cards.append(candidate_card(pdf, page, faction, text))

    duplicates: dict[str, int] = {}
    for card in cards:
        value = str(card["card_id"])
        duplicates[value] = duplicates.get(value, 0) + 1
    for card in cards:
        if duplicates[str(card["card_id"])] > 1:
            source = card["source"]
            card["card_id"] = f"candidate-{card['faction']['id']}-{source['page']:03d}"
            card["official_card_id"] = None
    return cards


def source_manifest(source_dir: Path) -> list[dict[str, object]]:
    manifest = []
    for path in sorted(source_dir.glob("*.pdf")):
        manifest.append(
            {"path": str(path), "sha256": sha256(path), "pages": page_count(path), "kind": "rules" if path.name == RULES_FILE else "card_pool"}
        )
    return manifest


def build_rules(pdf: Path, with_ocr: bool) -> list[dict[str, object]]:
    """Keep page-level rule candidates until a reviewer splits them into clauses."""

    rules = []
    for page in range(1, page_count(pdf) + 1):
        text = ""
        if with_ocr:
            with tempfile.TemporaryDirectory(prefix="legion12-rule-ocr-") as temp_dir:
                text = ocr_page(pdf, page, Path(temp_dir))
        rules.append(
            {
                "rule_id": f"candidate-rules-2.0-page-{page:03d}",
                "title": None,
                "text": None,
                "implementation_status": "not_started",
                "ocr": {"engine": "tesseract chi_sim+eng psm12", "raw_text": text},
                "review": {"status": "needs_review", "reviewed_fields": []},
                "source": {"pdf_path": str(pdf), "pdf_sha256": sha256(pdf), "page": page},
            }
        )
    return rules


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=Path("规则与卡池"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/card_pools/s01"))
    parser.add_argument("--skip-ocr", action="store_true")
    parser.add_argument("--ocr-workers", type=int, default=4)
    parser.add_argument("--rules-only", action="store_true")
    args = parser.parse_args()
    if not shutil.which("pdfinfo"):
        raise SystemExit("pdfinfo is required")
    if not args.skip_ocr and not shutil.which("tesseract"):
        raise SystemExit("tesseract is required unless --skip-ocr is used")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    sources = source_manifest(args.source_dir)
    cards = []
    if not args.rules_only:
        cards = build_cards(args.source_dir, with_ocr=not args.skip_ocr, ocr_workers=args.ocr_workers)
        pool = {"schema_version": "1.0", "pool_id": "s01-source-pdf", "generated_at": generated_at, "sources": sources, "cards": cards}
        (args.output_dir / "card_pool.json").write_text(
            json.dumps(pool, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    rules_pdf = args.source_dir / RULES_FILE
    rules = {
        "schema_version": "1.0",
        "ruleset_id": "rules-2.0-source-pdf",
        "generated_at": generated_at,
        "source": {"pdf_path": str(rules_pdf), "pdf_sha256": sha256(rules_pdf), "pages": page_count(rules_pdf)},
        "rules": build_rules(rules_pdf, with_ocr=not args.skip_ocr),
        "review": {"status": "needs_review", "notes": "Rule extraction awaits page-by-page human review."},
    }
    (args.output_dir / "rules.json").write_text(
        json.dumps(rules, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"cards={len(cards)} sources={len(sources)} output={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
